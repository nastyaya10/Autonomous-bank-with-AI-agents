from datetime import datetime
from llm_agent import LLMAgent
from models import Decision
from utils import write_report, logger


class DepositClient(LLMAgent):
    def __init__(self, name: str, config_list: list, min_rate_willing: float = 0.05):
        system_prompt = (
            f"Ты клиент-вкладчик. Твой минимально приемлемый процент по депозиту: {min_rate_willing * 100:.1f}% годовых. "
            f"Ты хочешь максимально высокую ставку.\n"
            f"ПРАВИЛА (строго соблюдай):\n"
            f"1. Если предложенная ставка БОЛЬШЕ или РАВНА твоему минимуму, ты обязан согласиться. Отвечай: {{\"decision\":\"accept\"}}\n"
            f"2. Если ставка НИЖЕ минимума, ты должен предложить встречную ставку (counter), которая на 1-2% выше твоего минимума. "
            f"Отвечай: {{\"decision\":\"counter\",\"rate\":<число>}}\n"
            f"3. Запрещено отвечать reject, если ставка >= минимума.\n"
            f"4. Отвечай только JSON, без пояснений."
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

        write_report(
            f"[{self.name}] Предложение депозита: {amount} руб., {term} мес., ставка {rate_percent:.2f}%, ПКР={credit_score}")

        prompt = (
            f"Предложен депозит: сумма {amount} руб., срок {term} мес., ставка {rate_percent:.2f}% годовых. "
            f"Твой минимум {self.min_rate_willing * 100:.1f}%. Твоё решение (только JSON)."
        )

        llm_out = self._call_llm_json(deal_id, prompt)
        decision, counter_rate_percent = self.parse_decision(llm_out)

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
            })
        elif decision == Decision.REJECT:
            write_report(f"[{self.name}] Отказ")
            self.send(from_agent, {
                "type": "client_response",
                "decision": Decision.REJECT,
                "deal_id": deal_id,
                "current_date": current_date,
            })
        elif decision == Decision.COUNTER and counter_rate_percent is not None:
            counter_rate_dec = counter_rate_percent / 100.0
            write_report(f"[{self.name}] Просим ставку выше: {counter_rate_percent:.2f}%")
            self.send(from_agent, {
                "type": "client_response",
                "decision": Decision.COUNTER,
                "deal_id": deal_id,
                "amount": amount,
                "term": term,
                "counter_rate": counter_rate_dec,
                "credit_score": credit_score,
                "current_date": current_date,
            })
