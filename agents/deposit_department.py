import uuid
from datetime import datetime
from models import Deal, DealType, Decision, Portfolio
from llm_agent import LLMAgent
from utils import write_report


class DepositDepartment(LLMAgent):
    def __init__(self, name: str, portfolio: Portfolio, treasury_name: str,
                 risk_name: str, config_list: list, all_deposits: list = None):
        system_prompt = """Ты — депозитное отделение."""
        super().__init__(name, config_list, system_prompt)
        self.portfolio = portfolio
        self.treasury_name = treasury_name
        self.risk_name = risk_name
        self.all_deposits = all_deposits if all_deposits is not None else []

    def propose_deposit(self, client_name: str, amount: float, term_months: int,
                        credit_score: int, current_date: datetime,
                        risk_free_rate: float) -> str:
        deal_id = str(uuid.uuid4())
        self.send(self.treasury_name, {
            "type": "rate_request",
            "deal_id": deal_id,
            "amount": amount,
            "term": term_months,
            "client": client_name,
            "credit_score": credit_score,
            "current_date": current_date.isoformat(),
            "risk_free_rate": risk_free_rate
        })
        return deal_id

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "rate_response":
            current_date = datetime.fromisoformat(message.get("current_date", datetime.now().isoformat()))
            rf = message.get("risk_free_rate", 0.21)
            dep_msg = {
                "type": "deposit_proposal",
                "deal_id": message["deal_id"],
                "amount": message["amount"],
                "term": message["term"],
                "rate": message["allowed_rate"],
                "credit_score": message.get("credit_score"),
                "current_date": current_date.isoformat(),
                "risk_free_rate": rf
            }
            self.send(message["client"], dep_msg)
        elif msg_type == "client_response":
            deal_id = message["deal_id"]
            decision = message["decision"]
            current_date = datetime.fromisoformat(message.get("current_date", datetime.now().isoformat()))
            if decision == Decision.ACCEPT:
                self._create_deposit(message, from_agent, current_date, rate=message["rate"])
            elif decision == Decision.COUNTER:
                self.send(self.treasury_name, {
                    "type": "counter_request",
                    "deal_id": deal_id,
                    "amount": message["amount"],
                    "term": message["term"],
                    "requested_rate": message["counter_rate"],
                    "client": from_agent,
                    "credit_score": message.get("credit_score"),
                    "current_date": current_date.isoformat(),
                    "risk_free_rate": message.get("risk_free_rate", 0.21)
                })
            else:
                write_report(f"[{self.name}] Клиент {from_agent} отклонил депозит {deal_id[:8]}")
        elif msg_type == "counter_response":
            current_date = datetime.fromisoformat(message.get("current_date", datetime.now().isoformat()))
            if message["allowed"]:
                self._create_deposit(message, message["client"], current_date, rate=message["rate"])
            else:
                self.send(message["client"], {"type": "reject_counter", "deal_id": message["deal_id"]})

    def _create_deposit(self, message, client_name, current_date, rate):
        deal = Deal(
            deal_id=message["deal_id"],
            type=DealType.DEPOSIT,
            amount=message["amount"],
            term_months=message["term"],
            rate=rate,
            client_id=client_name,
            credit_score=message.get("credit_score", 500),
            status="active",
            created_at=current_date,
        )
        self.portfolio.add_deposit(deal)
        self.all_deposits.append(deal)  # сохраняем для графика
        write_report(
            f"[{self.name}] Депозит {deal.deal_id[:8]} принят: {deal.amount} руб. на {deal.term_months} мес. под {deal.rate * 100:.2f}%")
        self.send(client_name, {"type": "deal_confirmed", "deal_id": deal.deal_id})
        self.send(self.treasury_name, {"type": "portfolio_updated", "current_date": current_date.isoformat()})
