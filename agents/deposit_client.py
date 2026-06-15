from datetime import datetime
from llm_agent import LLMAgent
from models import Decision, ClientSegment
from utils import write_report, logger


class DepositClient(LLMAgent):
    def __init__(self, name: str, config_list: list, segment: ClientSegment = ClientSegment.MASS,
                 min_rate_willing: float = 0.10):
        self.segment = segment
        if segment == ClientSegment.VIP:
            system_prompt = (
                f"Ты VIP-клиент, крупный вкладчик. Твой минимально приемлемый процент по депозиту: {min_rate_willing * 100:.1f}% годовых.\n"
                f"Ты можешь торговаться. Если ставка ниже твоего минимума, предложи встречную ставку (counter), которая на 1-2% выше минимума.\n"
                f"В остальных случаях: если ставка >= минимума – accept, иначе – counter.\n"
                f"Отвечай только JSON: {{\"decision\":\"accept\"}} или {{\"decision\":\"reject\"}} или {{\"decision\":\"counter\",\"rate\":число}} (проценты)."
            )
        else:
            system_prompt = (
                f"Ты клиент-вкладчик – физическое лицо. Твой минимально приемлемый процент по депозиту: {min_rate_willing * 100:.1f}% годовых.\n"
                f"Ты не торгуешься. Если ставка >= минимума – accept, иначе – reject.\n"
                f"Отвечай только JSON: {{\"decision\":\"accept\"}} или {{\"decision\":\"reject\"}}."
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
        segment = ClientSegment(message.get("segment", "mass"))

        rf_str = ""
        if risk_free_rate is not None:
            rf_str = f" Текущая безрисковая ставка на {term} мес. составляет {risk_free_rate * 100:.2f}%."

        write_report(
            f"[{self.name}] Предложение депозита: {amount} руб., {term} мес., ставка {rate_percent:.2f}%, ПКР={credit_score}, сегмент={segment.value}")

        prompt = (
            f"Предложен депозит: сумма {amount} руб., срок {term} мес., ставка {rate_percent:.2f}% годовых.{rf_str} "
            f"Твой минимум {self.min_rate_willing * 100:.1f}%. Твоё решение (только JSON)."
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
                "current_date": current_date,
                "segment": segment.value
            })
        elif decision == Decision.REJECT:
            write_report(f"[{self.name}] Отказ")
            self.send(from_agent, {
                "type": "client_response",
                "decision": Decision.REJECT,
                "deal_id": deal_id,
                "current_date": current_date,
                "segment": segment.value
            })
        elif decision == Decision.COUNTER and counter_rate is not None:
            if segment != ClientSegment.VIP:
                write_report(f"[{self.name}] Массовый клиент не может торговаться, отказ")
                self.send(from_agent, {
                    "type": "client_response",
                    "decision": Decision.REJECT,
                    "deal_id": deal_id,
                    "current_date": current_date,
                    "segment": segment.value
                })
                return
            write_report(f"[{self.name}] Просим ставку выше: {counter_rate * 100:.2f}%")
            self.send(from_agent, {
                "type": "client_response",
                "decision": Decision.COUNTER,
                "deal_id": deal_id,
                "amount": amount,
                "term": term,
                "counter_rate": counter_rate,
                "credit_score": credit_score,
                "current_date": current_date,
                "segment": segment.value
            })
