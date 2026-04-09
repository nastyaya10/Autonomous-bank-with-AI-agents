from dotenv import load_dotenv

load_dotenv()

import os
import random
from datetime import datetime
from models import (
    Portfolio, MessageBus, LoanType, YieldCurve,
    PnL, RiskMetrics, GapHistory
)
from agents import (
    LendingDepartment, CreditClient,
    DepositDepartment, DepositClient,
    Treasury, RiskAgent
)
from utils import write_report

config_list = [
    {
        'model': 'gpt-4o-mini',
        'api_key': os.getenv('AIPIPE_TOKEN'),
        'base_url': os.getenv('OPENAI_BASE_URL', 'https://aipipe.org/openai/v1'),
    }
]

yield_curve = YieldCurve(key_rate=0.21)
pnl = PnL()
risk_metrics = RiskMetrics()
gap_history = GapHistory()


def random_credit_score() -> int:
    return random.randint(1, 999)


def run_simulation(num_deals: int = 8):
    with open("report.txt", "w", encoding="utf-8") as f:
        f.write("=== ОТЧЁТ ПО СДЕЛКАМ ===\n\n")

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
        write_report(f"\n--- СДЕЛКА {i + 1} ---")
        if random.choice(["loan", "deposit"]) == "loan":
            amount = random.randint(10000, 500000)
            term = random.choice([3, 6, 12, 24])
            score = random_credit_score()
            loan_type = random.choice([LoanType.FIXED, LoanType.FLOATING])
            write_report(
                f"Инициируем кредит: сумма {amount} руб., срок {term} мес., ПКР={score}, тип={loan_type.value}")
            lending.propose_loan("CreditClient", amount, term, score, loan_type)
        else:
            amount = random.randint(5000, 300000)
            term = random.choice([1, 3, 6, 12])
            score = random_credit_score()
            write_report(f"Инициируем депозит: сумма {amount} руб., срок {term} мес., ПКР={score}")
            deposit_dept.propose_deposit("DepositClient", amount, term, score)

        pnl.update(portfolio, yield_curve, period_months=1)
        risk_metrics.calculate(portfolio, yield_curve)
        current_gap = portfolio.gap_by_term()
        gap_history.record(datetime.now(), current_gap)

        report = "\n=== ОТЧЁТ ===\n"
        report += f"💰 PnL: доход {pnl.total_interest_income:.2f}, расход {pnl.total_interest_expense:.2f}, NII {pnl.net_interest_income:.2f}\n"
        report += f"⚠️ Риск: VaR(95%) = {risk_metrics.var_95:.2f}, чувствительность NII к +1% = {risk_metrics.nii_sensitivity:.2f}\n"
        report += f"📊 Портфель: кредиты {portfolio.total_loans():,.2f} руб., депозиты {portfolio.total_deposits():,.2f} руб., нетто-позиция {portfolio.net_position():,.2f} руб.\n"
        report += "📉 Процентный GAP по срокам (активы - пассивы):\n"
        for bucket, value in current_gap.items():
            report += f"  {bucket}: {value:,.2f} руб.\n"
        report += "💱 Валютный GAP: 0 руб. (все операции в рублях)\n"
        report += "========================"
        write_report(report)

        treasury.send("RiskAgent", {"type": "gap_report", "gap": current_gap})

    write_report("\n=== ЭВОЛЮЦИЯ GAP ===")
    for entry in gap_history.entries:
        write_report(f"  {entry['timestamp']}: {entry['gap']}")


if __name__ == "__main__":
    run_simulation(8)
