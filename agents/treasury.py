from models import BaseAgent, Portfolio
from utils import write_report


class Treasury(BaseAgent):
    def __init__(self, name: str, portfolio: Portfolio, risk_agent_name: str,
                 base_rate: float = 0.07, spread: float = 0.02):
        super().__init__(name)
        self.portfolio = portfolio
        self.risk_name = risk_agent_name
        self.base_rate = base_rate
        self.spread = spread

    def allowed_deposit_rate(self, amount: float, term_months: int, credit_score: int) -> float:
        net = self.portfolio.net_position()
        if net > 0:
            premium = min(0.03, net / (self.portfolio.total_deposits() + 1e-6) * 0.01)
        else:
            premium = -0.01
        rate = self.base_rate + premium
        norm = (credit_score - 1) / 998
        bonus = norm * 0.03
        rate += bonus
        return max(0.01, min(0.20, rate))

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "rate_request":
            score = message["credit_score"]
            allowed = self.allowed_deposit_rate(message["amount"], message["term"], score)
            write_report(
                f"[{self.name}] Ставка для депозита {message['amount']} руб. на {message['term']} мес. = {allowed * 100:.2f}% (ПКР={score})")
            self.send(from_agent, {
                "type": "rate_response", "deal_id": message["deal_id"],
                "allowed_rate": allowed, "amount": message["amount"],
                "term": message["term"], "client": message["client"],
                "credit_score": score,
            })
        elif msg_type == "counter_request":
            requested = message["requested_rate"]
            score = message.get("credit_score", 500)
            allowed = self.allowed_deposit_rate(message["amount"], message["term"], score)
            if requested <= allowed:
                write_report(f"[{self.name}] Разрешаю контрпредложение: {requested * 100:.2f}%")
                self.send(from_agent, {
                    "type": "counter_response", "allowed": True,
                    "deal_id": message["deal_id"], "rate": requested,
                    "amount": message["amount"], "term": message["term"],
                    "client": message["client"], "credit_score": score,
                })
            else:
                write_report(f"[{self.name}] Отклоняю контрпредложение: {requested * 100:.2f}% > {allowed * 100:.2f}%")
                self.send(from_agent, {
                    "type": "counter_response", "allowed": False,
                    "deal_id": message["deal_id"], "client": message["client"],
                    "credit_score": score,
                })
        elif msg_type == "portfolio_updated":
            gap = self.portfolio.gap_by_term()
            self.send(self.risk_name, {"type": "gap_report", "gap": gap})
