from datetime import datetime
import random
from llm_agent import LLMAgent
from models import Decision, LoanType
from utils import write_report, logger


class CreditClient(LLMAgent):
    def __init__(self, name: str, config_list: list, max_rate_willing: float = 0.40):
        system_prompt = (
            f"Ты клиент-заёмщик. Твой максимум ставки: {max_rate_willing * 100:.1f}% годовых.\n"
            f"Если предложенная ставка <= {max_rate_willing * 100:.1f}%, отвечай {{\"decision\":\"accept\"}}.\n"
            f"Иначе отвечай {{\"decision\":\"reject\"}} (мы сами предложим встречную ставку).\n"
            f"Отвечай только JSON."
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
        risk_free_rate = message.get("risk_free_rate", None)

        rf_str = ""
        if risk_free_rate is not None:
            rf_str = f" Безрисковая ставка: {risk_free_rate * 100:.2f}%."

        write_report(
            f"[{self.name}] Предложение кредита: {amount} руб., {term} мес., ставка {rate_percent:.2f}%, ПКР={credit_score}")

        prompt = (
            f"Предложен кредит: {amount} руб., {term} мес., ставка {rate_percent:.2f}% годовых.{rf_str} "
            f"Твой максимум {self.max_rate_willing * 100:.1f}%. Твоё решение (JSON)."
        )

        llm_out = self._call_llm_json(deal_id, prompt)
        decision, _ = self.parse_decision(llm_out)

        # FALLBACK: если LLM не дала ответа, применяем простое правило
        if decision is None:
            logger.warning(f"[{self.name}] LLM не вернула решение, применяю fallback")
            if rate_percent <= self.max_rate_willing * 100:
                decision = Decision.ACCEPT
            else:
                decision = Decision.REJECT

        if decision == Decision.REJECT and rate_percent > self.max_rate_willing * 100:
            counter_percent = max(1.0, self.max_rate_willing * 100 - random.uniform(1.0, 2.0))
            counter_rate = counter_percent / 100.0
            write_report(f"[{self.name}] Встречное предложение: {counter_percent:.2f}%")
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
                "schedule": message.get("schedule", "annuity"),
                "commission_rate": message.get("commission_rate", 0.0)
            })
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
                "schedule": message.get("schedule", "annuity"),
                "commission_rate": message.get("commission_rate", 0.0)
            })
        else:
            write_report(f"[{self.name}] Отказ")
            self.send(from_agent, {
                "type": "client_response",
                "decision": Decision.REJECT,
                "deal_id": deal_id,
                "current_date": current_date,
            })
