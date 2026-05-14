from models import BaseAgent, Portfolio


class RiskAgent(BaseAgent):
    def __init__(self, name: str, portfolio: Portfolio):
        super().__init__(name)
        self.portfolio = portfolio

    def receive(self, from_agent: str, message: dict):
        # Вся аналитика выполняется в main.py
        pass
