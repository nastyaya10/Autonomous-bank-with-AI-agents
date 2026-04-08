from models import BaseAgent, Portfolio


class Treasury(BaseAgent):
    def __init__(self, name: str, portfolio: Portfolio, risk_agent_name: str,
                 base_rate: float = 0.07, spread: float = 0.02):
        super().__init__(name)
        self.portfolio = portfolio
        self.risk_name = risk_agent_name
        self.base_rate = base_rate
        self.spread = spread

    def allowed_deposit_rate(self, amount: float, term_months: int) -> float:
        """Рассчитывает максимальную ставку по депозиту исходя из текущего портфеля"""
        net = self.portfolio.net_position()
        # Если кредитов больше, чем депозитов (net > 0), банку нужна ликвидность → повышаем ставку
        if net > 0:
            premium = min(0.03, net / (self.portfolio.total_deposits() + 1e-6) * 0.01)
        else:
            premium = -0.01  # избыток депозитов → понижаем ставку
        rate = self.base_rate + premium
        # Ограничиваем разумными пределами
        return max(0.01, min(0.20, rate))

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "rate_request":
            # Запрос на предложение депозита
            amount = message["amount"]
            term = message["term"]
            allowed = self.allowed_deposit_rate(amount, term)
            print(f"[{self.name}] Рассчитал ставку для депозита {amount} руб. на {term} мес.: {allowed * 100:.2f}%")
            self.send(from_agent, {
                "type": "rate_response",
                "deal_id": message["deal_id"],
                "allowed_rate": allowed,
                "amount": amount,
                "term": term,
                "client": message["client"],
            })
        elif msg_type == "counter_request":
            # Контрпредложение клиента: проверяем, можем ли дать запрошенную ставку
            requested = message["requested_rate"]
            amount = message["amount"]
            term = message["term"]
            allowed = self.allowed_deposit_rate(amount, term)
            if requested <= allowed:
                print(
                    f"[{self.name}] Разрешаю контрпредложение: ставка {requested * 100:.2f}% (максимум {allowed * 100:.2f}%)")
                self.send(from_agent, {
                    "type": "counter_response",
                    "allowed": True,
                    "deal_id": message["deal_id"],
                    "rate": requested,
                    "amount": amount,
                    "term": term,
                    "client": message["client"],
                })
            else:
                print(
                    f"[{self.name}] Отклоняю контрпредложение: ставка {requested * 100:.2f}% выше лимита {allowed * 100:.2f}%")
                self.send(from_agent, {
                    "type": "counter_response",
                    "allowed": False,
                    "deal_id": message["deal_id"],
                    "client": message["client"],
                })
        elif msg_type == "portfolio_updated":
            # Запрос пересчёта рисков – отправляем агенту риски для отображения GAP
            gap = self.portfolio.gap_by_term()
            self.send(self.risk_name, {"type": "gap_report", "gap": gap})
