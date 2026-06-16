import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from models import (
    Portfolio, MessageBus, LoanType, YieldCurve, KeyRate,
    PnL, RiskMetrics, TimeSnapshot, RepaymentSchedule
)
from agents import (
    LendingDepartment, CreditClient,
    DepositDepartment, DepositClient,
    Treasury, RiskAgent
)
from utils import write_report
from visualizer import (
    plot_time_series, plot_deposit_rates,
    plot_stress_test, plot_gap_barchart
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

key_rate = KeyRate(current=0.21)
yield_curve = YieldCurve(key_rate=key_rate.current)
pnl = PnL()
risk_metrics = RiskMetrics()


def random_credit_score() -> int:
    return random.randint(1, 999)


def run_simulation(simulation_days: int = 365):
    with open("report.txt", "w", encoding="utf-8") as f:
        f.write("=== ОТЧЁТ ПО СДЕЛКАМ ===\n\n")

    portfolio = Portfolio()
    bus = MessageBus()

    # Повышенная базовая ставка казначейства для сближения с ОФЗ
    treasury = Treasury("Treasury", portfolio, "RiskAgent", base_rate=0.15)
    lending = LendingDepartment("LendingDept", portfolio, config_list, pnl, "Treasury",
                                rate_limit_min=0.10, rate_limit_max=0.35)
    credit_client = CreditClient("CreditClient", config_list, max_rate_willing=0.15)
    deposit_client = DepositClient("DepositClient", config_list, min_rate_willing=0.10)
    deposit_dept = DepositDepartment("DepositDept", portfolio, "Treasury", "RiskAgent", config_list)
    risk = RiskAgent("RiskAgent", portfolio, config_list)

    for agent in [lending, credit_client, deposit_dept, deposit_client, treasury, risk]:
        bus.register(agent)

    current_date = datetime.now()
    end_date = current_date + timedelta(days=simulation_days)

    snapshots = []
    stress_test_results = []

    while current_date <= end_date:
        if (current_date - datetime.now()).days % 60 == 0 and current_date != datetime.now():
            key_rate.set(key_rate.current + 0.005)
            yield_curve.key_rate = key_rate.current
            write_report(f"--- Изменение ключевой ставки до {key_rate.current * 100:.2f}% ---")

        if random.random() < 0.4:
            # Балансировка: не выдаём кредиты, если левередж > 3
            leverage = portfolio.total_loans() / (portfolio.total_deposits() + 1)
            if leverage > 3.0:
                write_report(
                    f"[Balancing] Кредиты ({portfolio.total_loans():,.0f}) более чем в 3 раза превышают депозиты ({portfolio.total_deposits():,.0f}), кредитование приостановлено.")
            else:
                write_report(f"\n--- СДЕЛКА {current_date.strftime('%Y-%m-%d')} ---")
                if random.choice(["loan", "deposit"]) == "loan":
                    amount = random.randint(10000, 500000)
                    term = random.choice([3, 6, 12, 24])
                    score = random_credit_score()
                    loan_type = random.choice([LoanType.FIXED, LoanType.FLOATING])
                    schedule = random.choice([RepaymentSchedule.ANNUITY, RepaymentSchedule.DIFFERENTIATED])
                    commission_rate = random.uniform(0, 0.02)
                    rf = yield_curve.rate(term)
                    write_report(
                        f"Инициируем кредит: сумма {amount} руб., срок {term} мес., ПКР={score}, тип={loan_type.value}, "
                        f"график={schedule.value}, комиссия={commission_rate * 100:.1f}%")
                    lending.propose_loan("CreditClient", amount, term, score, loan_type, current_date,
                                         risk_free_rate=rf, schedule=schedule, commission_rate=commission_rate)
                else:
                    amount = random.randint(5000, 300000)
                    term = random.choice([1, 3, 6, 12])
                    score = random_credit_score()
                    rf = yield_curve.rate(term)
                    write_report(f"Инициируем депозит: сумма {amount} руб., срок {term} мес., ПКР={score}")
                    deposit_dept.propose_deposit("DepositClient", amount, term, score, current_date,
                                                 risk_free_rate=rf)

        if current_date.day == 1 and current_date != datetime.now():
            total_principal_paid = 0.0
            for loan in portfolio.loans:
                principal_paid = loan.apply_payment()
                total_principal_paid += principal_paid
                if loan.outstanding_principal <= 0:
                    write_report(f"[Payment] Кредит {loan.deal_id[:8]} полностью погашен.")
            if total_principal_paid > 0:
                write_report(f"[Payments] Общая сумма погашения основного долга: {total_principal_paid:,.2f} руб.")

        pnl.accrue_daily(portfolio, key_rate.current, days=1)

        portfolio.apply_prepayments(current_date)
        if portfolio.prepaid_loans:
            total_prepaid = sum(loan.outstanding_principal for loan in portfolio.prepaid_loans)
            write_report(f"[Prepayments] Досрочно погашено кредитов на сумму {total_prepaid:,.2f} руб.")
            portfolio.prepaid_loans.clear()

        portfolio.remove_matured(current_date)

        current_gap = portfolio.gap_by_remaining_term(current_date)
        risk_metrics.calculate(portfolio, yield_curve)

        if (current_date - datetime.now()).days % 30 == 0:
            risk.receive("Main", {
                "type": "risk_assessment",
                "loans": portfolio.total_loans(),
                "deposits": portfolio.total_deposits(),
                "net": portfolio.net_position(),
                "gap": current_gap,
                "nii": pnl.net_interest_income,
                "nii_sensitivity": risk_metrics.nii_sensitivity,
                "expected_loss": risk_metrics.expected_loss
            })

            elapsed_days = max(1, (current_date - datetime.now()).days)
            base_daily_interest = pnl.total_interest_income - pnl.total_interest_expense
            base_annual_nii = (base_daily_interest / elapsed_days) * 365

            shocked_key = key_rate.current + 0.04
            shocked_pnl = PnL()
            shocked_pnl.accrue_daily(portfolio, shocked_key, days=1)
            shocked_daily_interest = shocked_pnl.total_interest_income - shocked_pnl.total_interest_expense
            shocked_annual_nii = shocked_daily_interest * 365

            change = shocked_annual_nii - base_annual_nii
            sign = "+" if change >= 0 else ""
            stress_test_results.append((current_date, base_annual_nii, shocked_annual_nii))
            write_report(f"[StressTest] Ожидаемый годовой NII: базовый {base_annual_nii:,.2f} руб., "
                         f"при шоке +4% {shocked_annual_nii:,.2f} руб. "
                         f"(изменение {sign}{change:,.2f} руб.)")

        snapshot = TimeSnapshot(
            date=current_date,
            loans=portfolio.total_loans(),
            deposits=portfolio.total_deposits(),
            net=portfolio.net_position(),
            gap=current_gap,
            nii=pnl.net_interest_income,
            expected_loss=risk_metrics.expected_loss
        )
        snapshots.append(snapshot)

        daily_report = f"\n=== ОТЧЁТ за {current_date.strftime('%Y-%m-%d')} ===\n"
        daily_report += f"💰 PnL: процентный доход {pnl.total_interest_income:.2f}, расход {pnl.total_interest_expense:.2f}, "
        daily_report += f"комиссионный доход {pnl.total_commission_income:.2f}, NII {pnl.net_interest_income:.2f}\n"
        daily_report += f"⚠️ Риск: чувствительность NII к +1% = {risk_metrics.nii_sensitivity:.2f}\n"
        daily_report += f"💳 Ожидаемые потери (EL) = {risk_metrics.expected_loss:.2f} руб.\n"
        daily_report += f"📊 Портфель: кредиты {portfolio.total_loans():,.2f} руб., депозиты {portfolio.total_deposits():,.2f} руб., нетто-позиция {portfolio.net_position():,.2f} руб.\n"
        recent_loans = [loan for loan in portfolio.loans if loan.created_at.date() == current_date.date()]
        for loan in recent_loans[:3]:
            daily_report += f"   - Кредит {loan.deal_id[:8]}: эффективная ставка {loan.effective_rate * 100:.2f}%\n"
        daily_report += "📉 Процентный GAP по оставшемуся сроку:\n"
        for bucket, value in current_gap.items():
            daily_report += f"  {bucket}: {value:,.2f} руб.\n"
        daily_report += "💱 Валютный GAP: 0 руб.\n"
        daily_report += "========================"
        write_report(daily_report)

        current_date += timedelta(days=1)

    write_report("\n=== ИТОГОВЫЙ ОТЧЁТ ПО ВСЕМУ ПЕРИОДУ ===")
    write_report(f"Всего дней симуляции: {simulation_days}")
    write_report(f"Итоговый PnL: {pnl.net_interest_income:.2f} руб.")
    write_report(f"Итоговые ожидаемые потери: {risk_metrics.expected_loss:.2f} руб.")

    plot_time_series(snapshots)
    plot_deposit_rates(yield_curve, portfolio)
    if stress_test_results:
        dates_stress, base_nii_vals, shocked_nii_vals = zip(*stress_test_results)
        plot_stress_test(dates_stress, base_nii_vals, shocked_nii_vals)
    # Дополнительный bar chart GAP на конец периода
    final_gap = portfolio.gap_by_remaining_term(end_date)
    plot_gap_barchart(final_gap)


if __name__ == "__main__":
    run_simulation(simulation_days=365)
