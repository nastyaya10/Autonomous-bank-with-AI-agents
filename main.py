import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from models import (
    Portfolio, MessageBus, LoanType, RealYieldCurve, StressedYieldCurve, KeyRate,
    PnL, RiskMetrics, TimeSnapshot, RepaymentSchedule
)
from agents import (
    LendingDepartment, CreditClient,
    DepositDepartment, DepositClient,
    Treasury, RiskAgent
)
from utils import write_report
from visualizer import (
    plot_time_series, plot_rates_vs_curve,
    plot_stress_test_curve, plot_gap_barchart,
    plot_comparison_bars, plot_comparison_lines
)

api_key = os.getenv('OPENAI_API_KEY') or os.getenv('AIPIPE_TOKEN')
if not api_key:
    raise ValueError("Установите переменную окружения OPENAI_API_KEY или AIPIPE_TOKEN")

config_list = [
    {
        'model': 'gpt-4o-mini',
        'api_key': api_key,
        'base_url': os.getenv('OPENAI_BASE_URL', 'https://aipipe.org/openai/v1'),
    }
]

# Загрузка базовой кривой
try:
    base_curve = RealYieldCurve("ofz_curve.csv")
    print("Загружена кривая ОФЗ из ofz_curve.csv")
except FileNotFoundError:
    print("Файл ofz_curve.csv не найден. Используется упрощённая кривая.")
    from models import YieldCurve

    base_curve = YieldCurve(key_rate=0.21, term_premium=0.015)

# Кривая для стресс-теста с "поломками" 2022 года
stress_shifts = {12: 5.0, 36: 3.0, 120: 1.0}
stress_curve = StressedYieldCurve(base_curve, stress_shifts)


def random_credit_score() -> int:
    return random.randint(1, 999)


def run_one_simulation(yield_curve, label):
    """Запуск симуляции с заданной кривой ОФЗ, возвращает pnl, portfolio, snapshots, all_loans, all_deposits."""
    print(f"\n=== Запуск симуляции: {label} ===")
    portfolio = Portfolio()
    bus = MessageBus()
    all_loans, all_deposits = [], []

    treasury = Treasury("Treasury", portfolio, "RiskAgent", deposit_discount=0.05)
    lending = LendingDepartment("LendingDept", portfolio, config_list, PnL(), "Treasury",
                                all_loans=all_loans,
                                credit_spread_low=0.06, credit_spread_high=0.08)
    credit_client = CreditClient("CreditClient", config_list, max_rate_willing=0.40)
    deposit_client = DepositClient("DepositClient", config_list, min_rate_willing=0.10)
    deposit_dept = DepositDepartment("DepositDept", portfolio, "Treasury", "RiskAgent", config_list,
                                     all_deposits=all_deposits)
    risk = RiskAgent("RiskAgent", portfolio, config_list)

    for agent in [lending, credit_client, deposit_dept, deposit_client, treasury, risk]:
        bus.register(agent)

    current_date = datetime(2026, 1, 1)
    start_date = current_date
    end_date = current_date + timedelta(days=365)

    pnl = PnL()
    key_rate = KeyRate(current=0.21)
    snapshots = []

    while current_date <= end_date:
        if (current_date - start_date).days % 60 == 0 and current_date != start_date:
            key_rate.set(key_rate.current + 0.005)

        leverage = portfolio.total_loans() / (portfolio.total_deposits() + 1)
        credit_prob = max(0.1, 0.4 - 0.05 * (leverage - 1))
        deposit_prob = 0.65
        if leverage > 5.0 and (current_date - start_date).days > 30:
            pass  # кредитование приостановлено
        else:
            if random.random() < 0.55:
                if random.random() < credit_prob / (credit_prob + deposit_prob):
                    amount = random.randint(10000, 500000)
                    term = random.choice([3, 6, 12, 24, 36, 48, 60, 72, 84])
                    score = random_credit_score()
                    loan_type = random.choice([LoanType.FIXED, LoanType.FLOATING])
                    schedule = random.choice([RepaymentSchedule.ANNUITY, RepaymentSchedule.DIFFERENTIATED])
                    commission_rate = random.uniform(0, 0.02)
                    rf = yield_curve.rate(term)
                    lending.propose_loan("CreditClient", amount, term, score, loan_type, current_date,
                                         risk_free_rate=rf, schedule=schedule, commission_rate=commission_rate)
                else:
                    amount = random.randint(5000, 300000)
                    term = random.choice([1, 3, 6, 12, 24, 36, 48, 60])
                    score = random_credit_score()
                    rf = yield_curve.rate(term)
                    deposit_dept.propose_deposit("DepositClient", amount, term, score, current_date, risk_free_rate=rf)

        if current_date.day == 1 and (current_date - start_date).days >= 30:
            for loan in portfolio.loans:
                loan.apply_payment()
        pnl.accrue_daily(portfolio, key_rate.current, days=1)

        if (current_date - start_date).days > 30:
            portfolio.apply_prepayments(current_date)
            portfolio.prepaid_loans.clear()

        portfolio.remove_matured(current_date)

        current_gap = portfolio.gap_by_remaining_term(current_date)
        risk_metrics = RiskMetrics()
        risk_metrics.calculate(portfolio, yield_curve)

        if (current_date - start_date).days % 30 == 0 and current_date != start_date:
            # логгирование опущено для краткости
            pass

        snapshots.append(TimeSnapshot(
            date=current_date,
            loans=portfolio.total_loans(),
            deposits=portfolio.total_deposits(),
            net=portfolio.net_position(),
            gap=current_gap,
            nii=pnl.net_interest_income,
            expected_loss=risk_metrics.expected_loss
        ))
        current_date += timedelta(days=1)

    print(f"Завершена симуляция {label}: ЧПД = {pnl.net_interest_income:.2f}")
    return pnl, portfolio, snapshots, all_loans, all_deposits


def main():
    # Базовая симуляция
    base_pnl, base_portfolio, base_snapshots, base_loans, base_deposits = run_one_simulation(base_curve, "базовый")
    # Стрессовая симуляция
    stress_pnl, stress_portfolio, stress_snapshots, stress_loans, stress_deposits = run_one_simulation(stress_curve,
                                                                                                       "стресс")

    # Визуализация для каждого сценария отдельно
    plot_time_series(base_snapshots, label="базовый", suffix="base")
    plot_rates_vs_curve(base_curve, base_loans, base_deposits, label="базовый", suffix="base")
    plot_gap_barchart(base_portfolio.gap_by_remaining_term(datetime(2026, 12, 31)), " (базовый, конец периода)")

    plot_time_series(stress_snapshots, label="стресс", suffix="stress")
    plot_rates_vs_curve(stress_curve, stress_loans, stress_deposits, label="стресс", suffix="stress")
    plot_gap_barchart(stress_portfolio.gap_by_remaining_term(datetime(2026, 12, 31)), " (стресс, конец периода)")

    # Сравнительные графики
    plot_comparison_bars(base_pnl, stress_pnl,
                         base_portfolio.gap_by_remaining_term(datetime(2026, 12, 31)),
                         stress_portfolio.gap_by_remaining_term(datetime(2026, 12, 31)))
    plot_comparison_lines(base_snapshots, stress_snapshots)

    # Дополнительный график "стресс-тест кривой" (гибрид)
    plot_stress_test_curve(base_curve, base_loans, base_deposits, stress_shifts)

    print("\nВсе графики сохранены в папке 'plots/'")
    print(
        f"Итоговый ЧПД базовый: {base_pnl.net_interest_income:.2f} руб., стресс: {stress_pnl.net_interest_income:.2f} руб.")


if __name__ == "__main__":
    main()
