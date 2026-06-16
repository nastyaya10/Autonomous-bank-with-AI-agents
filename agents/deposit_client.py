from datetime import datetime
from llm_agent import LLMAgent
from models import Decision
from utils import write_report, logger
import random


class DepositClient(LLMAgent):
    def __init__(self, name: str, config_list: list, min_rate_willing: float = 0.10):
        system_prompt = (
            f"Ты клиент-вкладчик. Твой минимум ставки: {min_rate_willing * 100:.1f}% годовых.\n"
            f"Если предложенная ставка >= {min_rate_willing * 100:.1f}%, отвечай {{\"decision\":\"accept\"}}.\n"
            f"Иначе отвечай {{\"decision\":\"reject\"}} (мы сами предложим встречную ставку).\n"
            f"Отвечай только JSON."
        )
        super().__init__(name, config_list, system_prompt, temperature=0.2)
        self.min_rate_willing = min_rate_willing

    def receive(self, from_agent: str, message: dict):
        if message.get("type") != "deposit_proposal":
            return

        deal_id = message["deal_id"]
        amount = message["amount"]
        term = message["term"]
        rate_dec = message["rate"]
        rate_percent = rate_dec * 100
        credit_score = message.get("credit_score", 500)
        current_date = message.get("current_date")
        risk_free_rate = message.get("risk_free_rate", None)

        rf_str = ""
        if risk_free_rate is not None:
            rf_str = f" Безрисковая ставка: {risk_free_rate * 100:.2f}%."

        write_report(
            f"[{self.name}] Предложение депозита: {amount} руб., {term} мес., ставка {rate_percent:.2f}%, ПКР={credit_score}")

        prompt = (
            f"Предложен депозит: {amount} руб., {term} мес., ставка {rate_percent:.2f}% годовых.{rf_str} "
            f"Твой минимум {self.min_rate_willing * 100:.1f}%. Твоё решение (JSON)."
        )

        llm_out = self._call_llm_json(deal_id, prompt)
        decision, _ = self.parse_decision(llm_out)

        if decision == Decision.REJECT and rate_percent < self.min_rate_willing * 100:
            # Генерируем встречную ставку на 1-2% выше порога, но не более 20%
            counter_percent = min(20.0, self.min_rate_willing * 100 + random.uniform(1.0, 2.0))
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
                "current_date": current_date,
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
                "current_date": current_date,
            })
        else:
            write_report(f"[{self.name}] Отказ")
            self.send(from_agent, {
                "type": "client_response",
                "decision": Decision.REJECT,
                "deal_id": deal_id,
                "current_date": current_date,
            })
