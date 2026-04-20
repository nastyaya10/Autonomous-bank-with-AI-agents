import uuid
from datetime import datetime
from models import Deal, DealType, Decision, Portfolio
from llm_agent import LLMAgent
from utils import write_report


class DepositDepartment(LLMAgent):
    def __init__(self, name: str, portfolio: Portfolio, treasury_name: str,
                 risk_name: str, config_list: list):
        system_prompt = """Ты — Принимающее отделение (депозиты). Ты передаёшь сообщения между клиентом и казначейством."""
        super().__init__(name, config_list, system_prompt)
        self.portfolio = portfolio
        self.treasury_name = treasury_name
        self.risk_name = risk_name

    def propose_deposit(self, client_name: str, amount: float, term_months: int,
                        credit_score: int, current_date: datetime) -> str:
        deal_id = str(uuid.uuid4())
        write_report(
            f"[{self.name}] Запрашиваю у Казначейства ставку для депозита: {amount} руб., {term_months} мес., ПКР={credit_score}")
        self.send(self.treasury_name, {
            "type": "rate_request",
            "deal_id": deal_id,
            "amount": amount,
            "term": term_months,
            "client": client_name,
            "credit_score": credit_score,
            "current_date": current_date.isoformat(),
        })
        return deal_id

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "rate_response":
            current_date = datetime.fromisoformat(message.get("current_date", datetime.now().isoformat()))
            write_report(
                f"[{self.name}] Получил от Казначейства ставку {message['allowed_rate'] * 100:.2f}%. Отправляю предложение клиенту {message['client']}")
            self.send(message["client"], {
                "type": "deposit_proposal",
                "deal_id": message["deal_id"],
                "amount": message["amount"],
                "term": message["term"],
                "rate": message["allowed_rate"],
                "credit_score": message.get("credit_score"),
                "current_date": current_date.isoformat(),
            })
        elif msg_type == "client_response":
            deal_id = message["deal_id"]
            decision = message["decision"]
            current_date = datetime.fromisoformat(message.get("current_date", datetime.now().isoformat()))
            if decision == Decision.ACCEPT:
                deal = Deal(
                    deal_id=deal_id,
                    type=DealType.DEPOSIT,
                    amount=message["amount"],
                    term_months=message["term"],
                    rate=message["rate"],
                    client_id=from_agent,
                    credit_score=message.get("credit_score", 500),
                    status="active",
                    created_at=current_date,
                )
                self.portfolio.add_deposit(deal)
                write_report(
                    f"[{self.name}] Депозит {deal_id[:8]} принят: {deal.amount} руб. на {deal.term_months} мес. под {deal.rate * 100:.2f}%")
                self.send(from_agent, {"type": "deal_confirmed", "deal_id": deal_id})
                self.send(self.treasury_name, {"type": "portfolio_updated", "current_date": current_date.isoformat()})
            elif decision == Decision.REJECT:
                write_report(f"[{self.name}] Клиент {from_agent} отклонил депозит {deal_id[:8]}")
            elif decision == Decision.COUNTER:
                write_report(
                    f"[{self.name}] Клиент {from_agent} предлагает контрставку {message['counter_rate'] * 100:.2f}% по депозиту {deal_id[:8]}")
                self.send(self.treasury_name, {
                    "type": "counter_request",
                    "deal_id": deal_id,
                    "amount": message["amount"],
                    "term": message["term"],
                    "client": from_agent,
                    "requested_rate": message["counter_rate"],
                    "credit_score": message.get("credit_score"),
                    "current_date": current_date.isoformat(),
                })
        elif msg_type == "counter_response":
            current_date = datetime.fromisoformat(message.get("current_date", datetime.now().isoformat()))
            if message["allowed"]:
                deal = Deal(
                    deal_id=message["deal_id"],
                    type=DealType.DEPOSIT,
                    amount=message["amount"],
                    term_months=message["term"],
                    rate=message["rate"],
                    client_id=message["client"],
                    credit_score=message.get("credit_score", 500),
                    status="active",
                    created_at=current_date,
                )
                self.portfolio.add_deposit(deal)
                write_report(
                    f"[{self.name}] Депозит {message['deal_id'][:8]} принят после контрпредложения под {message['rate'] * 100:.2f}%")
                self.send(message["client"], {"type": "deal_confirmed", "deal_id": message["deal_id"]})
                self.send(self.treasury_name, {"type": "portfolio_updated", "current_date": current_date.isoformat()})
            else:
                write_report(
                    f"[{self.name}] Казначейство отклонило контрпредложение по депозиту {message['deal_id'][:8]}")
                client = message.get("client")
                if client:
                    self.send(client, {"type": "reject_counter", "deal_id": message["deal_id"]})
