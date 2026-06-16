from datetime import datetime
from models import BaseAgent, Portfolio
from utils import write_report


class Treasury(BaseAgent):
    def __init__(self, name: str, portfolio: Portfolio, risk_agent_name: str,
                 base_rate: float = 0.15, cost_of_funds: float = 0.05):
        super().__init__(name)
        self.portfolio = portfolio
        self.risk_name = risk_agent_name
        self.base_rate = base_rate
        self.cost_of_funds = cost_of_funds

    def allowed_deposit_rate(self, amount: float, term_months: int) -> float:
        net = self.portfolio.net_position()
        if net > 0:
            premium = min(0.03, net / (self.portfolio.total_deposits() + 1e-6) * 0.01)
        else:
            premium = -0.01
        term_premium = 0.01 * (term_months / 12.0)
        rate = self.base_rate + premium + term_premium
        return max(0.01, min(0.20, rate))

    def minimum_loan_rate(self, term_months: int) -> float:
        term_premium = 0.01 * (term_months / 12.0)
        min_rate = self.cost_of_funds + term_premium + 0.02
        return max(0.05, min_rate)

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "rate_request":
            amount = message["amount"]
            term = message["term"]
            if message.get("purpose") == "loan":
                min_rate = self.minimum_loan_rate(term)
                write_report(f"[{self.name}] Минимальная ставка по кредиту на {term} мес. = {min_rate * 100:.2f}%")
                self.send(from_agent, {
                    "type": "rate_response",
                    "deal_id": message["deal_id"],
                    "min_rate": min_rate,
                    "purpose": "loan"
                })
            else:
                allowed = self.allowed_deposit_rate(amount, term)
                write_report(f"[{self.name}] Ставка для депозита {amount} руб. на {term} мес. = {allowed * 100:.2f}%")
                self.send(from_agent, {
                    "type": "rate_response",
                    "deal_id": message["deal_id"],
                    "allowed_rate": allowed,
                    "amount": amount,
                    "term": term,
                    "client": message["client"],
                    "credit_score": message.get("credit_score", 500),
                    "current_date": message.get("current_date", datetime.now().isoformat()),
                })
        elif msg_type == "counter_request":
            requested_rate = message["requested_rate"]
            amount = message["amount"]
            term = message["term"]
            allowed = self.allowed_deposit_rate(amount, term)
            allowed_flag = requested_rate <= allowed
            write_report(
                f"[{self.name}] Запрошена встречная ставка {requested_rate * 100:.2f}% (допустимо {allowed * 100:.2f}%) – {'одобрено' if allowed_flag else 'отклонено'}")
            self.send(from_agent, {
                "type": "counter_response",
                "allowed": allowed_flag,
                "deal_id": message["deal_id"],
                "rate": requested_rate if allowed_flag else allowed,
                "amount": amount,
                "term": term,
                "client": message["client"],
                "credit_score": message.get("credit_score", 500),
                "current_date": message.get("current_date", datetime.now().isoformat()),
            })
        elif msg_type == "portfolio_updated":
            gap = self.portfolio.gap_by_remaining_term(datetime.now())
            self.send(self.risk_name, {"type": "gap_report", "gap": gap})
