from models import BaseAgent, Portfolio


class RiskAgent(BaseAgent):
    def __init__(self, name: str, portfolio: Portfolio):
        super().__init__(name)
        self.portfolio = portfolio

    def receive(self, from_agent: str, message: dict):
        if message.get("type") == "gap_report":
            gap = message["gap"]
            print("\n=== ОТЧЁТ О РИСКАХ ===")
            print("Процентный GAP по срокам (активы - пассивы):")
            for bucket, value in gap.items():
                print(f"  {bucket}: {value:,.2f} руб.")
            print("Валютный GAP: 0 руб. (все операции в рублях)")
            net = self.portfolio.net_position()
            print(f"Чистая позиция (кредиты - депозиты): {net:,.2f} руб.")
            print("========================\n")
