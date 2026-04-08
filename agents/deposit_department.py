import uuid
from models import Deal, DealType, Decision, Portfolio
from llm_agent import LLMAgent


class DepositDepartment(LLMAgent):
    def __init__(self, name: str, portfolio: Portfolio, treasury_name: str,
                 risk_name: str, config_list: list,
                 min_rate: float = 0.05, max_rate: float = 0.15):
        system_prompt = f"""Ты — Принимающее отделение (депозиты). Ты предлагаешь клиентам ставки по депозитам.
Лимиты ставок: от {min_rate * 100:.2f}% до {max_rate * 100:.2f}% годовых.
Ты не устанавливаешь ставку самостоятельно — ты запрашиваешь её у Казначейства.
При получении ответа от Казначейства ты передаёшь предложение клиенту.
При контрпредложении клиента ты снова обращаешься в Казначейство.
"""
        super().__init__(name, config_list, system_prompt)
        self.portfolio = portfolio
        self.treasury_name = treasury_name
        self.risk_name = risk_name
        self.min_rate = min_rate
        self.max_rate = max_rate

    def propose_deposit(self, client_name: str, amount: float, term_months: int) -> str:
        deal_id = str(uuid.uuid4())
        print(f"[{self.name}] Запрашиваю у Казначейства ставку для депозита: {amount} руб., {term_months} мес.")
        self.send(self.treasury_name, {
            "type": "rate_request", "deal_id": deal_id,
            "amount": amount, "term": term_months, "client": client_name,
        })
        return deal_id

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "rate_response":
            print(
                f"[{self.name}] Получил от Казначейства ставку {message['allowed_rate'] * 100:.2f}%. Отправляю предложение клиенту {message['client']}")
            self.send(message["client"], {
                "type": "deposit_proposal", "deal_id": message["deal_id"],
                "amount": message["amount"], "term": message["term"],
                "rate": message["allowed_rate"],
            })
        elif msg_type == "client_response":
            deal_id = message["deal_id"]
            if message["decision"] == Decision.ACCEPT:
                deal = Deal(
                    deal_id=deal_id, type=DealType.DEPOSIT,
                    amount=message["amount"], term_months=message["term"],
                    rate=message["rate"], client_id=from_agent, status="agreed"
                )
                self.portfolio.add_deposit(deal)
                print(
                    f"[{self.name}] Депозит {deal_id} принят: {deal.amount} руб. на {deal.term_months} мес. под {deal.rate * 100:.2f}%")
                self.send(from_agent, {"type": "deal_confirmed", "deal_id": deal_id})
                self.send(self.treasury_name, {"type": "portfolio_updated"})
            elif message["decision"] == Decision.REJECT:
                print(f"[{self.name}] Клиент {from_agent} отклонил депозит {deal_id}")
            elif message["decision"] == Decision.COUNTER:
                print(
                    f"[{self.name}] Клиент {from_agent} предлагает контрставку {message['counter_rate'] * 100:.2f}% по депозиту {deal_id}. Запрашиваю разрешение у Казначейства.")
                self.send(self.treasury_name, {
                    "type": "counter_request", "deal_id": deal_id,
                    "amount": message["amount"], "term": message["term"],
                    "client": from_agent, "requested_rate": message["counter_rate"],
                })
        elif msg_type == "counter_response":
            if message["allowed"]:
                deal = Deal(
                    deal_id=message["deal_id"], type=DealType.DEPOSIT,
                    amount=message["amount"], term_months=message["term"],
                    rate=message["rate"], client_id=message["client"], status="agreed"
                )
                self.portfolio.add_deposit(deal)
                print(
                    f"[{self.name}] Депозит {message['deal_id']} принят после контрпредложения под {message['rate'] * 100:.2f}%")
                self.send(message["client"], {"type": "deal_confirmed", "deal_id": message["deal_id"]})
                self.send(self.treasury_name, {"type": "portfolio_updated"})
            else:
                print(f"[{self.name}] Казначейство отклонило контрпредложение по депозиту {message['deal_id']}")
                client = message.get("client")
                if client:
                    self.send(client, {"type": "reject_counter", "deal_id": message["deal_id"]})
