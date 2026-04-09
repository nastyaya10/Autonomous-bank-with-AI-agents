from llm_agent import LLMAgent
from models import Decision
from utils import write_report


class DepositClient(LLMAgent):
    def __init__(self, name: str, config_list: list, min_rate_willing: float = 0.08):
        system_prompt = f"""Ты — клиент-вкладчик. Твоя минимальная приемлемая ставка — {min_rate_willing * 100:.2f}% годовых.
Ты хочешь получить как можно более высокую ставку по депозиту. Если предложенная ставка выше твоего минимума, ты можешь согласиться, но лучше попробовать повысить ставку на 1-3%.
Если ставка ниже твоего минимума, ты обязательно делаешь контрпредложение со ставкой на 1-2% выше минимума.
Отвечай ТОЛЬКО JSON: {{"decision": "accept"/"reject"/"counter", "rate": число (если counter)}}.
Ставку указывай в процентах годовых."""
        super().__init__(name, config_list, system_prompt)
        self.min_rate_willing = min_rate_willing

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "deposit_proposal":
            deal_id = message["deal_id"]
            amount = message["amount"]
            term = message["term"]
            rate_dec = message["rate"]
            rate_percent = rate_dec * 100
            credit_score = message.get("credit_score", 500)
            write_report(
                f"[{self.name}] Предложение депозита: {amount} руб., {term} мес., ставка {rate_percent:.2f}%, ПКР={credit_score}")
            prompt = f"Банк предлагает депозит {amount} руб. на {term} мес. под {rate_percent:.2f}%. Твой минимум {self.min_rate_willing * 100:.2f}%. Твоё решение? Ответь JSON."
            llm_out = self._call_llm(deal_id, prompt)
            decision, counter_rate_percent = self.parse_decision(llm_out)
            if decision == Decision.ACCEPT:
                write_report(f"[{self.name}] Соглашаемся на ставку {rate_percent:.2f}%")
                self.send(from_agent, {
                    "type": "client_response", "decision": Decision.ACCEPT,
                    "deal_id": deal_id, "amount": amount, "term": term, "rate": rate_dec,
                    "credit_score": credit_score,
                })
            elif decision == Decision.REJECT:
                write_report(f"[{self.name}] Отказ")
                self.send(from_agent, {"type": "client_response", "decision": Decision.REJECT, "deal_id": deal_id})
            elif decision == Decision.COUNTER and counter_rate_percent is not None:
                write_report(f"[{self.name}] Просим ставку выше: {counter_rate_percent * 100:.2f}%")
                self.send(from_agent, {
                    "type": "client_response", "decision": Decision.COUNTER,
                    "deal_id": deal_id, "amount": amount, "term": term,
                    "counter_rate": counter_rate_percent,
                    "credit_score": credit_score,
                })
        elif msg_type == "deal_confirmed":
            write_report(f"[{self.name}] Депозит {message['deal_id'][:8]} подтверждён")
        elif msg_type == "reject_counter":
            write_report(f"[{self.name}] Банк отклонил наше контрпредложение")
