from dotenv import load_dotenv

load_dotenv()
import os
import random
from datetime import datetime, timedelta
from models import (
    Portfolio, MessageBus, LoanType, YieldCurve,
    PnL, RiskMetrics, TimeSnapshot
)
from agents import (
    LendingDepartment, CreditClient,
    DepositDepartment, DepositClient,
    Treasury, RiskAgent
)
from utils import write_report
from visualizer import plot_time_series

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


def random_credit_score() -> int:
    return random.randint(1, 999)


def run_simulation(simulation_days: int = 180):
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

    current_date = datetime.now()
    end_date = current_date + timedelta(days=simulation_days)

    snapshots = []

    while current_date <= end_date:
        # С вероятностью 0.4 происходит новая сделка (чтобы портфель не рос слишком быстро)
        if random.random() < 0.4:
            write_report(f"\n--- СДЕЛКА {current_date.strftime('%Y-%m-%d')} ---")
            if random.choice(["loan", "deposit"]) == "loan":
                amount = random.randint(10000, 500000)
                term = random.choice([3, 6, 12, 24])
                score = random_credit_score()
                loan_type = random.choice([LoanType.FIXED, LoanType.FLOATING])
                write_report(
                    f"Инициируем кредит: сумма {amount} руб., срок {term} мес., ПКР={score}, тип={loan_type.value}")
                lending.propose_loan("CreditClient", amount, term, score, loan_type, current_date)
            else:
                amount = random.randint(5000, 300000)
                term = random.choice([1, 3, 6, 12])
                score = random_credit_score()
                write_report(f"Инициируем депозит: сумма {amount} руб., срок {term} мес., ПКР={score}")
                deposit_dept.propose_deposit("DepositClient", amount, term, score, current_date)

        # Ежедневное начисление процентов
        pnl.accrue_daily(portfolio, yield_curve, days=1)

        # Удаление погашенных сделок
        portfolio.remove_matured(current_date)

        # Расчёт метрик
        current_gap = portfolio.gap_by_remaining_term(current_date)
        risk_metrics.calculate(portfolio, yield_curve)

        # Снимок для истории
        snapshot = TimeSnapshot(
            date=current_date,
            loans=portfolio.total_loans(),
            deposits=portfolio.total_deposits(),
            net=portfolio.net_position(),
            gap=current_gap,
            nii=pnl.net_interest_income,
            var=risk_metrics.var_95
        )
        snapshots.append(snapshot)

        # Отчёт за день (только в файл)
        daily_report = f"\n=== ОТЧЁТ за {current_date.strftime('%Y-%m-%d')} ===\n"
        daily_report += f"💰 PnL: доход {pnl.total_interest_income:.2f}, расход {pnl.total_interest_expense:.2f}, NII {pnl.net_interest_income:.2f}\n"
        daily_report += f"⚠️ Риск: VaR(95%) = {risk_metrics.var_95:.2f}, чувствительность NII к +1% = {risk_metrics.nii_sensitivity:.2f}\n"
        daily_report += f"📊 Портфель: кредиты {portfolio.total_loans():,.2f} руб., депозиты {portfolio.total_deposits():,.2f} руб., нетто-позиция {portfolio.net_position():,.2f} руб.\n"
        daily_report += "📉 Процентный GAP по оставшемуся сроку:\n"
        for bucket, value in current_gap.items():
            daily_report += f"  {bucket}: {value:,.2f} руб.\n"
        daily_report += "💱 Валютный GAP: 0 руб.\n"
        daily_report += "========================"
        write_report(daily_report)

        # Переход к следующему дню
        current_date += timedelta(days=1)

    # Итоговый отчёт
    write_report("\n=== ИТОГОВЫЙ ОТЧЁТ ПО ВСЕМУ ПЕРИОДУ ===")
    write_report(f"Всего дней симуляции: {simulation_days}")
    write_report(f"Итоговый PnL: {pnl.net_interest_income:.2f} руб.")
    write_report(f"Итоговый VaR(95%): {risk_metrics.var_95:.2f} руб.")

    # Визуализация
    plot_time_series(snapshots)


if __name__ == "__main__":
    run_simulation(simulation_days=180)
