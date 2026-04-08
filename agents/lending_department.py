from models import Deal, DealType, Decision, Portfolio
from llm_agent import LLMAgent


class LendingDepartment(LLMAgent):
    def __init__(self, name: str, portfolio: Portfolio, config_list: list,
                 rate_limit_min: float = 0.10, rate_limit_max: float = 0.25):
        system_prompt = f"""Ты — Выдающее отделение банка. Твоя задача — предлагать кредиты и реагировать на контрпредложения.
У тебя есть лимиты: ставка кредита должна быть между {rate_limit_min * 100:.2f}% и {rate_limit_max * 100:.2f}% годовых.
Если клиент предлагает контрставку, ты можешь согласиться (accept), если она в лимитах, иначе откажи (reject).
При первом предложении сделай ставку в середине диапазона, но можешь чуть выше, чтобы оставить空间 для торга.
Отвечай ТОЛЬКО JSON: {{"decision": "accept"/"reject"/"counter", "rate": число (если counter)}}.
Ставку указывай в процентах годовых.
"""
        super().__init__(name, config_list, system_prompt)
        self.portfolio = portfolio
        self.rate_limit_min = rate_limit_min
        self.rate_limit_max = rate_limit_max

    def propose_loan(self, client_name: str, amount: float, term_months: int) -> str:
        import uuid
        deal_id = str(uuid.uuid4())
        # Сделаем начальную ставку в середине диапазона, чуть выше среднего, чтобы был торг
        proposed_rate = round((self.rate_limit_min + self.rate_limit_max) / 2 + 0.02, 4)
        proposed_rate = max(self.rate_limit_min, min(self.rate_limit_max, proposed_rate))
        message = {
            "type": "loan_proposal",
            "deal_id": deal_id,
            "amount": amount,
            "term": term_months,
            "rate": proposed_rate,
        }
        print(
            f"[{self.name}] Предлагаю клиенту {client_name} кредит: {amount} руб., {term_months} мес., ставка {proposed_rate * 100:.2f}%")
        self.send(client_name, message)
        return deal_id

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "client_response":
            deal_id = message["deal_id"]
            decision = message["decision"]
            if decision == Decision.ACCEPT:
                deal = Deal(
                    deal_id=deal_id, type=DealType.LOAN,
                    amount=message["amount"], term_months=message["term"],
                    rate=message["rate"], client_id=from_agent, status="agreed"
                )
                self.portfolio.add_loan(deal)
                print(
                    f"[{self.name}] Кредит {deal_id} одобрен: {deal.amount} руб. на {deal.term_months} мес. под {deal.rate * 100:.2f}%")
                self.send(from_agent, {"type": "deal_confirmed", "deal_id": deal_id})
            elif decision == Decision.REJECT:
                print(f"[{self.name}] Клиент {from_agent} отклонил кредит {deal_id}")
            elif decision == Decision.COUNTER:
                client_rate = message["counter_rate"]
                print(f"[{self.name}] Получено контрпредложение от клиента: ставка {client_rate * 100:.2f}%")
                # Проверяем, входит ли в лимиты
                if self.rate_limit_min <= client_rate <= self.rate_limit_max:
                    # Можно сразу согласиться или ещё поторговаться, но для простоты соглашаемся
                    print(f"[{self.name}] Принимаем контрпредложение: ставка {client_rate * 100:.2f}%")
                    deal = Deal(
                        deal_id=deal_id, type=DealType.LOAN,
                        amount=message["amount"], term_months=message["term"],
                        rate=client_rate, client_id=from_agent, status="agreed"
                    )
                    self.portfolio.add_loan(deal)
                    self.send(from_agent, {"type": "deal_confirmed", "deal_id": deal_id})
                else:
                    print(f"[{self.name}] Отклоняем контрпредложение {client_rate * 100:.2f}% (выход за лимиты)")
                    self.send(from_agent, {"type": "reject_counter", "deal_id": deal_id})
