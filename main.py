from time import process_time

import autogen
from agents.trader import create_trader_agent, generate_proposal
from agents.treasury import create_treasury_agent, check_liquidity
from agents.risk import create_risk_agent, check_limits
from models.schemas import TradeProposal, TradeVerdict, Balance
import json
import re
from dotenv import load_dotenv
import os
import tools.convert_currency
from tools.convert_currency import convert_currency
from tools.proposal_delta import evaluate_trade

load_dotenv()


def extract_json(text):
    """Извлекает JSON из текста"""
    if not isinstance(text, str):
        return None
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except:
            return None
    return None


def extract_agent_response(chat_result, function_name=None):
    """
    Извлекает ответ агента из истории чата.
    Сначала ищет результат вызова инструмента (tool), затем текст ассистента.
    """
    for msg in reversed(chat_result.chat_history):
        return msg["content"]
    return None


def parse_verdict(agent_name, proposal_id, verdict_text):
    """Парсит ответ агента (APPROVED/REJECTED)"""
    if not verdict_text:
        return TradeVerdict(
            agent=agent_name,
            proposal_id=proposal_id,
            decision="REJECTED",
            reason="Нет ответа от агента"
        )
    if "APPROVED" in verdict_text.upper():
        return TradeVerdict(
            agent=agent_name,
            proposal_id=proposal_id,
            decision="APPROVED"
        )
    else:
        reason = verdict_text
        if "REJECTED:" in verdict_text:
            reason = verdict_text.split("REJECTED:")[1].strip()
        elif "отклонен" in verdict_text.lower():
            reason = verdict_text
        else:
            reason = "Причина не указана"
        return TradeVerdict(
            agent=agent_name,
            proposal_id=proposal_id,
            decision="REJECTED",
            reason=reason
        )


def is_termination_msg(msg):
    """Определяет, когда диалог можно завершить (при получении валидного JSON с proposal_id)"""
    if isinstance(msg.get("content"), str):
        try:
            data = json.loads(msg["content"])
            if "proposal_id" in data:
                return True
        except:
            pass
    return False


def main():
    print("\n" + "=" * 50)
    print("🏦 БАНКОВСКАЯ МУЛЬТИАГЕНТНАЯ СИСТЕМА")
    print("=" * 50 + "\n")

    config_list = [
        {
            'model': 'gpt-4o-mini',
            'api_key': os.getenv('AIPIPE_TOKEN'),
            'base_url': os.getenv('OPENAI_BASE_URL', 'https://aipipe.org/openai/v1'),
        }
    ]

    print("🔄 Создание агентов...")
    trader = create_trader_agent(config_list)
    treasury = create_treasury_agent(config_list)
    risk = create_risk_agent(config_list)

    user_proxy = autogen.UserProxyAgent(
        name="Orchestrator",
        human_input_mode="NEVER",
        code_execution_config=False,
        max_consecutive_auto_reply=10,
        is_termination_msg=is_termination_msg  # <-- добавляем условие завершения
    )

    # Регистрируем функции
    autogen.register_function(
        generate_proposal,
        caller=trader,
        executor=user_proxy,
        name="generate_proposal",
        description="Сгенерировать предложение по сделке и вернуть JSON"
    )
    autogen.register_function(
        check_liquidity,
        caller=treasury,
        executor=user_proxy,
        name="check_liquidity",
        description="Проверить наличие ликвидности"
    )
    autogen.register_function(
        check_limits,
        caller=risk,
        executor=user_proxy,
        name="check_limits",
        description="Проверить лимиты на контрагента и влияние на капитал"
    )

    balance = Balance(
        amount=100.0,
        currency="RUB"
    )
    book = []
    print("Введите количество сделок:")
    cnt = int(input())

    while cnt:
        cnt -= 1

        # user_request = input("\n💬 Введите запрос для трейдера (например, сгенерировать сделку на 10 млн рублей):\n> ")

        print("\n" + "-" * 50)
        print("ШАГ 1: Трейдер генерирует предложение")
        print("-" * 50)

        chat_result = user_proxy.initiate_chat(
            trader,
            message="",
            max_turns=2,
            silent=False
        )

        # Извлекаем результат выполнения функции generate_proposal
        trader_response = extract_agent_response(chat_result, function_name="generate_proposal")

        if trader_response is None:
            print("❌ Не удалось получить ответ трейдера. История чата:")
            for i, msg in enumerate(chat_result.chat_history):
                print(f"{i}: {msg}")
            raise ValueError("Трейдер не вернул ответ")

        print(f"\n📊 Ответ трейдера (результат функции):\n{trader_response}")

        proposal_dict = extract_json(trader_response)
        if not proposal_dict:
            print("❌ Ошибка: Трейдер не сгенерировал валидный JSON")
            print(trader_response)
            return
        proposal = TradeProposal(**proposal_dict)
        print(f"\n✅ Предложение сгенерировано: {proposal.proposal_id}")
        print(f"   {proposal.trade_type.value} | {proposal.notional}M {proposal.currency} | {proposal.counterparty}")

        for old_proposal in book:
            verdict = evaluate_trade(old_proposal, proposal.created_at)
            if not verdict:
                continue
            nom = convert_currency(balance.amount, balance.currency, proposal.currency)
            balance.amount = nom
            balance.currency = proposal.currency
            balance += verdict["pnl"]

        print("\n" + "-" * 50)
        print("ШАГ 2: Проверка Казначейством и Рисками")
        print("-" * 50)

        proposal_json = json.dumps(proposal.model_dump(), default=str)

        # Казначейство
        print("\n🏦 Запрос к Казначейству...")
        chat_result = user_proxy.initiate_chat(
            treasury,
            message=proposal_json,
            max_turns=2,
            silent=False
        )
        treasury_response = extract_agent_response(chat_result, function_name="check_liquidity")
        if treasury_response is None:
            treasury_response = "REJECTED: нет ответа от казначейства"
        print(f"📬 Ответ Казначейства: {treasury_response}")

        # Риски
        print("\n⚠️ Запрос к Отделу рисков...")
        chat_result = user_proxy.initiate_chat(
            risk,
            message=proposal_json,
            max_turns=2,
            silent=False
        )
        risk_response = extract_agent_response(chat_result, function_name="check_limits")
        if risk_response is None:
            risk_response = "REJECTED: нет ответа от отдела рисков"
        print(f"📬 Ответ Рисков: {risk_response}")

        treasury_verdict = parse_verdict("Treasury", proposal.proposal_id, treasury_response)
        risk_verdict = parse_verdict("Risk", proposal.proposal_id, risk_response)

        print("\n" + "=" * 50)
        print("ШАГ 3: ИТОГОВОЕ РЕШЕНИЕ")
        print("=" * 50)

        if treasury_verdict.decision == "APPROVED" and risk_verdict.decision == "APPROVED":
            print("\n✅✅✅ СДЕЛКА ОДОБРЕНА! ✅✅✅")
            print(f"   ID сделки: {proposal.proposal_id}")
            print(f"   Тип: {proposal.trade_type.value}")
            print(f"   Номинал: {proposal.notional}M {proposal.currency}")
            print(f"   Контрагент: {proposal.counterparty}")
            print("\n   📝 Сделка будет исполнена в расчётной системе.")
            book.append(proposal)
        else:
            print("\n❌❌❌ СДЕЛКА ОТКЛОНЕНА ❌❌❌")
            print(f"   ID предложения: {proposal.proposal_id}\n")
            if treasury_verdict.decision == "REJECTED":
                print(f"   🏦 Казначейство: {treasury_verdict.reason}")
            if risk_verdict.decision == "REJECTED":
                print(f"   ⚠️ Отдел рисков: {risk_verdict.reason}")

        for prop in book:
            delta = evaluate_trade(prop, proposal.created_at)
            if not delta:
                continue
            num_delta = convert_currency(delta["pnl"], delta["currency"], balance.currency)
            balance.amount += num_delta

        print(f"Капитал: {balance.amount}M {balance.currency}")
        print("Процентный GAP:")
        print("Валютный GAP:")
        print("Портфель:")
        for prop in book:
            print(prop)
        print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
