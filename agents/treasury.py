from datetime import datetime
from models import BaseAgent, Portfolio
from utils import write_report


class Treasury(BaseAgent):
    def __init__(self, name: str, portfolio: Portfolio, risk_agent_name: str,
                 deposit_discount: float = 0.03):
        super().__init__(name)
        self.portfolio = portfolio
        self.risk_name = risk_agent_name
        self.deposit_discount = deposit_discount  # скидка от ОФЗ для депозитов (3%)

    def allowed_deposit_rate(self, risk_free_rate: float) -> float:
        """Депозитная ставка = ОФЗ – дисконт."""
        return max(0.01, risk_free_rate - self.deposit_discount)

    def minimum_loan_rate(self, risk_free_rate: float) -> float:
        """Минимальная кредитная ставка = ОФЗ (казначейство не разрешает ниже безриска)."""
        return risk_free_rate

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "rate_request":
            amount = message["amount"]
            term = message["term"]
            # Безрисковую ставку берём из кривой (должна передаваться в сообщении или доступна здесь)
            # Так как у Treasury нет ссылки на yield_curve, будем получать risk_free_rate из сообщения
            rf = message.get("risk_free_rate", 0.21)
            if message.get("purpose") == "loan":
                min_rate = self.minimum_loan_rate(rf)
                write_report(f"[{self.name}] Минимальная ставка по кредиту на {term} мес. = {min_rate * 100:.2f}%")
                self.send(from_agent, {
                    "type": "rate_response",
                    "deal_id": message["deal_id"],
                    "min_rate": min_rate,
                    "purpose": "loan"
                })
            else:
                allowed = self.allowed_deposit_rate(rf)
                write_report(
                    f"[{self.name}] Ставка для депозита {amount} руб. на {term} мес. = {allowed * 100:.2f}% (ОФЗ {rf * 100:.2f}% - {self.deposit_discount * 100:.0f}%)")
                self.send(from_agent, {
                    "type": "rate_response",
                    "deal_id": message["deal_id"],
                    "allowed_rate": allowed,
                    "amount": amount,
                    "term": term,
                    "client": message["client"],
                    "credit_score": message.get("credit_score", 500),
                    "current_date": message.get("current_date", datetime.now().isoformat()),
                    "risk_free_rate": rf
                })
        elif msg_type == "counter_request":
            requested_rate = message["requested_rate"]
            rf = message.get("risk_free_rate", 0.21)
            allowed = self.allowed_deposit_rate(rf)
            allowed_flag = requested_rate <= allowed
            write_report(
                f"[{self.name}] Встречная ставка {requested_rate * 100:.2f}% (допустимо {allowed * 100:.2f}%) – {'одобрено' if allowed_flag else 'отклонено'}")
            self.send(from_agent, {
                "type": "counter_response",
                "allowed": allowed_flag,
                "deal_id": message["deal_id"],
                "rate": requested_rate if allowed_flag else allowed,
                "amount": message["amount"],
                "term": message["term"],
                "client": message["client"],
                "credit_score": message.get("credit_score", 500),
                "current_date": message.get("current_date", datetime.now().isoformat()),
            })
        elif msg_type == "portfolio_updated":
            gap = self.portfolio.gap_by_remaining_term(datetime.now())
            self.send(self.risk_name, {"type": "gap_report", "gap": gap})
