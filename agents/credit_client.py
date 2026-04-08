from llm_agent import LLMAgent
from models import Decision


class CreditClient(LLMAgent):
    def __init__(self, name: str, config_list: list,
                 max_rate_willing: float = 0.18):
        system_prompt = f"""Ты — клиент-кредитор (заёмщик). Твоя максимальная приемлемая ставка — {max_rate_willing * 100:.2f}% годовых.
Ты хочешь получить кредит как можно дешевле. Если предложенная ставка ниже твоего максимума, ты можешь согласиться, но лучше попробовать снизить ставку на 1-3%.
Если ставка выше твоего максимума, ты обязательно делаешь контрпредложение со ставкой на 1-2% ниже твоего максимума.
Отвечай ТОЛЬКО JSON: {{"decision": "accept"/"reject"/"counter", "rate": число (если counter)}}.
Ставку указывай в процентах годовых (например, 15.5 для 15.5%).
Старайся торговаться! Не соглашайся сразу, если есть возможность снизить ставку.
"""
        super().__init__(name, config_list, system_prompt)
        self.max_rate_willing = max_rate_willing

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "loan_proposal":
            deal_id = message["deal_id"]
            amount = message["amount"]
            term = message["term"]
            rate_dec = message["rate"]
            rate_percent = rate_dec * 100
            print(f"[{self.name}] Предложение кредита: {amount} руб., {term} мес., ставка {rate_percent:.2f}%")
            prompt = f"Банк предлагает кредит {amount} руб. на {term} мес. под {rate_percent:.2f}%. Твой максимум {self.max_rate_willing * 100:.2f}%. Твоё решение? Ответь JSON. Если ставка выше твоего максимума, предложи контрставку на 1-2% ниже максимума. Если ставка ниже максимума, всё равно попробуй запросить на 1-2% меньше."
            llm_out = self._call_llm(deal_id, prompt)
            decision, counter_rate_percent = self.parse_decision(llm_out)
            if decision == Decision.ACCEPT:
                print(f"[{self.name}] Соглашаемся на ставку {rate_percent:.2f}%")
                self.send(from_agent, {
                    "type": "client_response", "decision": Decision.ACCEPT,
                    "deal_id": deal_id, "amount": amount, "term": term, "rate": rate_dec
                })
            elif decision == Decision.REJECT:
                print(f"[{self.name}] Отказ (слишком высокая ставка)")
                self.send(from_agent, {
                    "type": "client_response", "decision": Decision.REJECT, "deal_id": deal_id
                })
            elif decision == Decision.COUNTER and counter_rate_percent is not None:
                print(f"[{self.name}] Контрпредложение: ставка {counter_rate_percent * 100:.2f}%")
                self.send(from_agent, {
                    "type": "client_response", "decision": Decision.COUNTER,
                    "deal_id": deal_id, "amount": amount, "term": term,
                    "counter_rate": counter_rate_percent
                })
        elif msg_type == "deal_confirmed":
            print(f"[{self.name}] Сделка {message['deal_id']} подтверждена")
        elif msg_type == "reject_counter":
            print(f"[{self.name}] Банк отклонил наше контрпредложение")
