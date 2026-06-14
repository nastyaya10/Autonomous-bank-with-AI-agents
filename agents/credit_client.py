from datetime import datetime
from llm_agent import LLMAgent
from models import Decision, LoanType
from utils import write_report, logger


class CreditClient(LLMAgent):
    def __init__(self, name: str, config_list: list, max_rate_willing: float = 0.15):
        system_prompt = (
            f"Ты клиент-заёмщик. Твой максимально допустимый процент по кредиту: {max_rate_willing * 100:.1f}% годовых. "
            f"Ты хочешь кредит на лучших условиях.\n"
            f"ПРАВИЛА (строго соблюдай):\n"
            f"1. Если предложенная ставка МЕНЬШЕ или РАВНА твоему максимуму, ты обязан согласиться. Отвечай: {{\"decision\":\"accept\"}}\n"
            f"2. Если ставка ВЫШЕ максимума, ты должен предложить встречную ставку (counter), которая на 1-2% ниже твоего максимума. "
            f"Отвечай: {{\"decision\":\"counter\",\"rate\":<число>}}\n"
            f"   Число – это ставка в ПРОЦЕНТАХ годовых (например, 12.5).\n"
            f"3. Запрещено отвечать reject, если ставка <= максимума.\n"
            f"4. Отвечай только JSON, без пояснений."
        )
        super().__init__(name, config_list, system_prompt, temperature=0.2)
        self.max_rate_willing = max_rate_willing

    def receive(self, from_agent: str, message: dict):
        if message.get("type") != "loan_proposal":
            return

        deal_id = message["deal_id"]
        amount = message["amount"]
        term = message["term"]
        rate_dec = message["rate"]
        rate_percent = rate_dec * 100
        credit_score = message.get("credit_score", 500)
        loan_type = LoanType(message.get("loan_type", "fixed"))
        current_date = message.get("current_date")
        risk_free_rate = message.get("risk_free_rate", None)  # безрисковая ставка для данного срока

        rf_str = ""
        if risk_free_rate is not None:
            rf_str = f" Текущая безрисковая ставка на {term} мес. составляет {risk_free_rate * 100:.2f}%."

        write_report(
            f"[{self.name}] Предложение кредита: {amount} руб., {term} мес., ставка {rate_percent:.2f}%, ПКР={credit_score}")

        prompt = (
            f"Предложен кредит: сумма {amount} руб., срок {term} мес., ставка {rate_percent:.2f}% годовых.{rf_str} "
            f"Твой максимум {self.max_rate_willing * 100:.1f}%. Твоё решение (только JSON)."
        )

        llm_out = self._call_llm_json(deal_id, prompt)
        decision, counter_rate = self.parse_decision(llm_out)

        if decision is None:
            logger.warning(f"[{self.name}] Не удалось распарсить решение LLM, сделка игнорируется")
            return

        if decision == Decision.ACCEPT:
            write_report(f"[{self.name}] Соглашаемся на ставку {rate_percent:.2f}%")
            self.send(from_agent, {
                "type": "client_response",
                "decision": Decision.ACCEPT,
                "deal_id": deal_id,
                "amount": amount,
                "term": term,
                "rate": rate_dec,
                "credit_score": credit_score,
                "loan_type": loan_type.value,
                "current_date": current_date,
            })
        elif decision == Decision.REJECT:
            write_report(f"[{self.name}] Отказ")
            self.send(from_agent, {
                "type": "client_response",
                "decision": Decision.REJECT,
                "deal_id": deal_id,
                "current_date": current_date,
            })
        elif decision == Decision.COUNTER and counter_rate is not None:
            write_report(f"[{self.name}] Контрпредложение: {counter_rate * 100:.2f}%")
            self.send(from_agent, {
                "type": "client_response",
                "decision": Decision.COUNTER,
                "deal_id": deal_id,
                "amount": amount,
                "term": term,
                "counter_rate": counter_rate,
                "credit_score": credit_score,
                "loan_type": loan_type.value,
                "current_date": current_date,
            })
