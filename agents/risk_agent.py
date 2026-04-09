from models import BaseAgent, Portfolio


class RiskAgent(BaseAgent):
    def __init__(self, name: str, portfolio: Portfolio):
        super().__init__(name)
        self.portfolio = portfolio

    def receive(self, from_agent: str, message: dict):
        if message.get("type") == "gap_report":
            # Данные уже обработаны в main.py, здесь ничего не пишем
            pass
