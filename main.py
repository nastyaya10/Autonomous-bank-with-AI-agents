import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from models import (
    Portfolio, MessageBus, LoanType, YieldCurve, KeyRate,
    PnL, RiskMetrics, TimeSnapshot
)
from agents import (
    LendingDepartment, CreditClient,
    DepositDepartment, DepositClient,
    Treasury, RiskAgent
)
from utils import write_report
from visualizer import plot_time_series, plot_deposit_rates, plot_stress_test

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

key_rate = KeyRate(current=0.21)  # текущая ключевая ставка
yield_curve = YieldCurve(key_rate=key_rate.current)  # безрисковая кривая
pnl = PnL()
risk_metrics = RiskMetrics()


def random_credit_score() -> int:
    return random.randint(1, 999)


def run_simulation(simulation_days: int = 365):
    with open("report.txt", "w", encoding="utf-8") as f:
        f.write("=== ОТЧЁТ ПО СДЕЛКАМ ===\n\n")

    portfolio = Portfolio()
    bus = MessageBus()

    lending = LendingDepartment("LendingDept", portfolio, config_list,
                                rate_limit_min=0.10, rate_limit_max=0.35)
    credit_client = CreditClient("CreditClient", config_list, max_rate_willing=0.15)
    deposit_dept = DepositDepartment("DepositDept", portfolio, "Treasury", "RiskAgent", config_list)
    deposit_client = DepositClient("DepositClient", config_list, min_rate_willing=0.10)
    treasury = Treasury("Treasury", portfolio, "RiskAgent", config_list, base_rate=0.07)
    risk = RiskAgent("RiskAgent", portfolio, config_list)

    for agent in [lending, credit_client, deposit_dept, deposit_client, treasury, risk]:
        bus.register(agent)

    current_date = datetime.now()
    end_date = current_date + timedelta(days=simulation_days)

    snapshots = []
    stress_test_results = []  # (date, base_nii, shocked_nii)

    while current_date <= end_date:
        # Раз в месяц меняем ключевую ставку (простой сценарий: +0.5% каждые 60 дней)
        if (current_date - datetime.now()).days % 60 == 0 and current_date != datetime.now():
            key_rate.set(key_rate.current + 0.005)
            yield_curve.key_rate = key_rate.current
            write_report(f"--- Изменение ключевой ставки до {key_rate.current * 100:.2f}% ---")

        if random.random() < 0.4:
            write_report(f"\n--- СДЕЛКА {current_date.strftime('%Y-%m-%d')} ---")
            if random.choice(["loan", "deposit"]) == "loan":
                amount = random.randint(10000, 500000)
                term = random.choice([3, 6, 12, 24])
                score = random_credit_score()
                loan_type = random.choice([LoanType.FIXED, LoanType.FLOATING])
                # Рассчитываем безрисковую ставку для срока
                rf = yield_curve.rate(term)
                write_report(
                    f"Инициируем кредит: сумма {amount} руб., срок {term} мес., ПКР={score}, тип={loan_type.value}")
                lending.propose_loan("CreditClient", amount, term, score, loan_type, current_date, risk_free_rate=rf)
            else:
                amount = random.randint(5000, 300000)
                term = random.choice([1, 3, 6, 12])
                score = random_credit_score()
                rf = yield_curve.rate(term)
                write_report(f"Инициируем депозит: сумма {amount} руб., срок {term} мес., ПКР={score}")
                deposit_dept.propose_deposit("DepositClient", amount, term, score, current_date, risk_free_rate=rf)

        pnl.accrue_daily(portfolio, key_rate.current, yield_curve, days=1)
        portfolio.remove_matured(current_date)

        current_gap = portfolio.gap_by_remaining_term(current_date)
        risk_metrics.calculate(portfolio, key_rate.current, yield_curve)

        # Отправка данных риск-агенту
        risk.receive("Main", {
            "type": "risk_assessment",
            "loans": portfolio.total_loans(),
            "deposits": portfolio.total_deposits(),
            "net": portfolio.net_position(),
            "gap": current_gap,
            "nii": pnl.net_interest_income,
            "var": risk_metrics.var_95,
            "nii_sensitivity": risk_metrics.nii_sensitivity,
            "expected_loss": risk_metrics.expected_loss
        })

        # Стресс-тест раз в месяц (каждые 30 дней)
        if (current_date - datetime.now()).days % 30 == 0:
            # Симулируем шок ключевой ставки на +2%
            shocked_key = key_rate.current + 0.02
            # Пересчитываем NII за один день с шокированной ставкой (грубо)
            # Для оценки годового NII можно умножить на 365, но здесь просто дневной эффект
            test_pnl = PnL()
            test_pnl.accrue_daily(portfolio, shocked_key, yield_curve, days=1)
            base_nii_day = pnl.net_interest_income  # текущий накопленный NII
            shocked_nii_day = test_pnl.net_interest_income
            stress_test_results.append((current_date, base_nii_day, shocked_nii_day))
            write_report(f"[StressTest] NII при шоке +2%: базовый {base_nii_day:.2f}, шок {shocked_nii_day:.2f}")

        snapshot = TimeSnapshot(
            date=current_date,
            loans=portfolio.total_loans(),
            deposits=portfolio.total_deposits(),
            net=portfolio.net_position(),
            gap=current_gap,
            nii=pnl.net_interest_income,
            var=risk_metrics.var_95,
            expected_loss=risk_metrics.expected_loss
        )
        snapshots.append(snapshot)

        daily_report = f"\n=== ОТЧЁТ за {current_date.strftime('%Y-%m-%d')} ===\n"
        daily_report += f"💰 PnL: доход {pnl.total_interest_income:.2f}, расход {pnl.total_interest_expense:.2f}, NII {pnl.net_interest_income:.2f}\n"
        daily_report += f"⚠️ Риск: VaR(95%) = {risk_metrics.var_95:.2f}, чувствительность NII к +1% = {risk_metrics.nii_sensitivity:.2f}\n"
        daily_report += f"💳 Ожидаемые потери (EL) = {risk_metrics.expected_loss:.2f} руб.\n"
        daily_report += f"📊 Портфель: кредиты {portfolio.total_loans():,.2f} руб., депозиты {portfolio.total_deposits():,.2f} руб., нетто-позиция {portfolio.net_position():,.2f} руб.\n"
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
    write_report(f"Итоговый VaR(95%): {risk_metrics.var_95:.2f} руб.")
    write_report(f"Итоговые ожидаемые потери: {risk_metrics.expected_loss:.2f} руб.")

    plot_time_series(snapshots)
    plot_deposit_rates(yield_curve, portfolio)
    if stress_test_results:
        dates_stress, base_nii_vals, shocked_nii_vals = zip(*stress_test_results)
        plot_stress_test(dates_stress, base_nii_vals, shocked_nii_vals)


if __name__ == "__main__":
    run_simulation(simulation_days=365)
