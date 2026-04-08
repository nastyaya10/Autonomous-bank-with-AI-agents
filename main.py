import os
import random
from models import Portfolio, MessageBus
from agents import (
    LendingDepartment, CreditClient,
    DepositDepartment, DepositClient,
    Treasury, RiskAgent
)

from dotenv import load_dotenv
load_dotenv()

config_list = [
    {
        'model': 'gpt-4o-mini',
        'api_key': os.getenv('AIPIPE_TOKEN'),
        'base_url': os.getenv('OPENAI_BASE_URL', 'https://aipipe.org/openai/v1'),
    }
]


def run_simulation(num_deals: int = 10):
    portfolio = Portfolio()
    bus = MessageBus()

    lending = LendingDepartment("LendingDept", portfolio, config_list)
    credit_client = CreditClient("CreditClient", config_list)
    deposit_dept = DepositDepartment("DepositDept", portfolio, "Treasury", "RiskAgent", config_list)
    deposit_client = DepositClient("DepositClient", config_list)
    treasury = Treasury("Treasury", portfolio, "RiskAgent")
    risk = RiskAgent("RiskAgent", portfolio)

    for agent in [lending, credit_client, deposit_dept, deposit_client, treasury, risk]:
        bus.register(agent)

    for i in range(num_deals):
        print(f"\n--- СДЕЛКА {i + 1} ---")
        if random.choice(["loan", "deposit"]) == "loan":
            amount = random.randint(10000, 500000)
            term = random.choice([3, 6, 12, 24])
            print(f"Инициируем кредит: сумма {amount} руб., срок {term} мес.")
            lending.propose_loan("CreditClient", amount, term)
        else:
            amount = random.randint(5000, 300000)
            term = random.choice([1, 3, 6, 12])
            print(f"Инициируем депозит: сумма {amount} руб., срок {term} мес.")
            deposit_dept.propose_deposit("DepositClient", amount, term)

        treasury.send("RiskAgent", {"type": "gap_report", "gap": portfolio.gap_by_term()})

    print("\n=== ИТОГОВЫЙ ПОРТФЕЛЬ ===")
    print(f"Всего кредитов: {len(portfolio.loans)} на сумму {portfolio.total_loans():,.2f} руб.")
    print(f"Всего депозитов: {len(portfolio.deposits)} на сумму {portfolio.total_deposits():,.2f} руб.")
    print(f"Нетто-позиция: {portfolio.net_position():,.2f} руб.")
    final_gap = portfolio.gap_by_term()
    print("Процентный GAP по срокам:")
    for bucket, val in final_gap.items():
        print(f"  {bucket}: {val:,.2f} руб.")


if __name__ == "__main__":
    run_simulation(8)
