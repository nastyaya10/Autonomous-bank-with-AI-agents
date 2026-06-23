import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
from models import RealYieldCurve, StressedYieldCurve
import random


def setup_plots_dir():
    os.makedirs("plots", exist_ok=True)


def _to_millions(values):
    return [v / 1e6 for v in values]


def plot_time_series(snapshots, label="", suffix=""):
    setup_plots_dir()
    dates = [s.date for s in snapshots]
    loans = _to_millions([s.loans for s in snapshots])
    deposits = _to_millions([s.deposits for s in snapshots])
    nii = _to_millions([s.nii for s in snapshots])
    el = _to_millions([s.expected_loss for s in snapshots])

    plt.figure(figsize=(12, 6))
    plt.plot(dates, loans, label="Кредиты", marker='.', linestyle='-')
    plt.plot(dates, deposits, label="Депозиты", marker='.', linestyle='-')
    plt.title(f"Эволюция портфеля ({label})")
    plt.xlabel("Дата")
    plt.ylabel("млн руб.")
    plt.legend()
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f"plots/portfolio_evolution_{suffix}.png")
    plt.close()

    plt.figure(figsize=(12, 6))
    plt.plot(dates, nii, label="ЧПД (накопленный)", color='green')
    plt.title(f"Чистый процентный доход ({label})")
    plt.xlabel("Дата")
    plt.ylabel("млн руб.")
    plt.legend()
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f"plots/nii_{suffix}.png")
    plt.close()

    plt.figure(figsize=(12, 6))
    plt.plot(dates, el, label="Ожидаемые потери (EL)", color='orange', linestyle='-.')
    plt.title(f"Ожидаемые потери ({label})")
    plt.xlabel("Дата")
    plt.ylabel("млн руб.")
    plt.legend()
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f"plots/el_{suffix}.png")
    plt.close()


def plot_rates_vs_curve(yield_curve, loans: list, deposits: list, label="", suffix=""):
    setup_plots_dir()
    dep_terms = [d.term_months for d in deposits]
    dep_rates = [d.rate * 100 for d in deposits]

    # Добавляем джиттер для кредитных точек
    loan_terms = []
    loan_rates = []
    for l in loans:
        t = l.term_months + random.uniform(-0.5, 0.5)
        r = l.rate * 100 + random.uniform(-0.3, 0.3)
        loan_terms.append(t)
        loan_rates.append(r)

    all_terms = sorted(set(dep_terms + [l.term_months for l in loans] + [1, 3, 6, 12, 24, 36, 48, 60, 72, 84]))
    yc_rates = [yield_curve.rate(t) * 100 for t in all_terms]

    plt.figure(figsize=(10, 6))
    plt.plot(all_terms, yc_rates, 'r-', linewidth=2, label='ОФЗ')
    if dep_terms:
        plt.scatter(dep_terms, dep_rates, color='blue', alpha=0.9, s=60, label='Депозитные ставки')
    if loan_terms:
        plt.scatter(loan_terms, loan_rates, color='green', alpha=0.4, s=60, marker='s', label='Кредитные ставки')
    plt.title(f"Ставки банка vs кривая ОФЗ ({label})")
    plt.xlabel("Срок, мес.")
    plt.ylabel("Ставка, % годовых")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"plots/rates_vs_yield_curve_{suffix}.png")
    plt.close()


def plot_stress_test_curve(base_curve, stress_curve,
                           base_loans, base_deposits,
                           stress_loans, stress_deposits,
                           credit_spread_low=0.06, credit_spread_high=0.08, deposit_discount=0.05):
    """
    Объединённый график с джиттером для кредитных точек.
    """
    setup_plots_dir()

    # Базовые точки
    base_dep_terms = [d.term_months for d in base_deposits]
    base_dep_rates = [d.rate * 100 for d in base_deposits]

    base_loan_terms_jittered = []
    base_loan_rates_jittered = []
    for l in base_loans:
        t = l.term_months + random.uniform(-0.5, 0.5)
        r = l.rate * 100 + random.uniform(-0.3, 0.3)
        base_loan_terms_jittered.append(t)
        base_loan_rates_jittered.append(r)

    # Стрессовые точки
    stress_dep_terms = [d.term_months for d in stress_deposits]
    stress_dep_rates = [d.rate * 100 for d in stress_deposits]

    stress_loan_terms_jittered = []
    stress_loan_rates_jittered = []
    for l in stress_loans:
        t = l.term_months + random.uniform(-0.5, 0.5)
        r = l.rate * 100 + random.uniform(-0.3, 0.3)
        stress_loan_terms_jittered.append(t)
        stress_loan_rates_jittered.append(r)

    all_terms = sorted(set(base_dep_terms + [l.term_months for l in base_loans] +
                           stress_dep_terms + [l.term_months for l in stress_loans] +
                           [1, 3, 6, 12, 24, 36, 48, 60, 72, 84]))
    base_yc = [base_curve.rate(t) * 100 for t in all_terms]
    stress_yc = [stress_curve.rate(t) * 100 for t in all_terms]

    plt.figure(figsize=(12, 7))
    plt.plot(all_terms, base_yc, 'r-', linewidth=2, label='ОФЗ базовая')
    plt.plot(all_terms, stress_yc, 'darkblue', linewidth=2, label='ОФЗ стресс')

    if base_dep_terms:
        plt.scatter(base_dep_terms, base_dep_rates, color='darkblue', alpha=0.9, s=60, label='Депозиты (база)')
    if base_loan_terms_jittered:
        plt.scatter(base_loan_terms_jittered, base_loan_rates_jittered, color='darkgreen', alpha=0.9, s=60, marker='s',
                    label='Кредиты (база)')

    if stress_dep_terms:
        plt.scatter(stress_dep_terms, stress_dep_rates, color='orange', alpha=0.9, s=60, label='Депозиты (стресс)')
    if stress_loan_terms_jittered:
        plt.scatter(stress_loan_terms_jittered, stress_loan_rates_jittered, color='red', alpha=0.9, s=60, marker='s',
                    label='Кредиты (стресс)')

    plt.title("Стресс-тест кривой ОФЗ: текущая vs исторический шок 2022")
    plt.xlabel("Срок, мес.")
    plt.ylabel("Ставка, % годовых")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("plots/stress_test_curve.png")
    plt.close()
    print("Объединённый график стресс-теста сохранён в 'plots/stress_test_curve.png'")


def plot_gap_barchart(gap, title_suffix=""):
    setup_plots_dir()
    buckets = list(gap.keys())
    values = _to_millions(list(gap.values()))
    colors = ['green' if v >= 0 else 'red' for v in values]
    plt.figure(figsize=(8, 5))
    plt.bar(buckets, values, color=colors)
    plt.title(f"GAP по срочностям{title_suffix}")
    plt.xlabel("Срок")
    plt.ylabel("млн руб.")
    plt.grid(True, axis='y')
    plt.tight_layout()
    filename = f"plots/gap_barchart{title_suffix.replace(' ', '_').replace('(', '').replace(')', '')}.png"
    plt.savefig(filename)
    plt.close()


def plot_comparison_bars(base_pnl, stress_pnl, base_gap, stress_gap):
    setup_plots_dir()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    ax1.bar(["Базовый", "Стресс"],
            [base_pnl.net_interest_income / 1e6, stress_pnl.net_interest_income / 1e6],
            color=['blue', 'red'], alpha=0.7)
    ax1.set_title("Итоговый ЧПД")
    ax1.set_ylabel("млн руб.")
    ax1.grid(True, axis='y')

    buckets = list(base_gap.keys())
    base_vals = _to_millions([base_gap[b] for b in buckets])
    stress_vals = _to_millions([stress_gap[b] for b in buckets])
    x = range(len(buckets))
    width = 0.35
    ax2.bar([i - width / 2 for i in x], base_vals, width, label='Базовый', color='blue', alpha=0.7)
    ax2.bar([i + width / 2 for i in x], stress_vals, width, label='Стресс', color='red', alpha=0.7)
    ax2.set_xticks(x)
    ax2.set_xticklabels(buckets)
    ax2.set_title("GAP по срочностям на конец периода")
    ax2.set_ylabel("млн руб.")
    ax2.legend()
    ax2.grid(True, axis='y')
    plt.tight_layout()
    plt.savefig("plots/comparison_bars.png")
    plt.close()


def plot_comparison_lines(base_snapshots, stress_snapshots):
    setup_plots_dir()
    base_dates = [s.date for s in base_snapshots]
    stress_dates = [s.date for s in stress_snapshots]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    ax1.plot(base_dates, _to_millions([s.nii for s in base_snapshots]), label="ЧПД базовый", color='blue')
    ax1.plot(stress_dates, _to_millions([s.nii for s in stress_snapshots]), label="ЧПД стресс", color='red')
    ax1.set_title("Динамика ЧПД")
    ax1.set_ylabel("млн руб.")
    ax1.legend()
    ax1.grid(True)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax1.tick_params(axis='x', rotation=45)

    ax2.plot(base_dates, _to_millions([s.loans for s in base_snapshots]), label="Кредиты базовый", linestyle='-',
             color='blue')
    ax2.plot(base_dates, _to_millions([s.deposits for s in base_snapshots]), label="Депозиты базовый", linestyle='--',
             color='blue')
    ax2.plot(stress_dates, _to_millions([s.loans for s in stress_snapshots]), label="Кредиты стресс", linestyle='-',
             color='red')
    ax2.plot(stress_dates, _to_millions([s.deposits for s in stress_snapshots]), label="Депозиты стресс",
             linestyle='--', color='red')
    ax2.set_title("Динамика портфеля")
    ax2.set_ylabel("млн руб.")
    ax2.legend()
    ax2.grid(True)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax2.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig("plots/comparison_lines.png")
    plt.close()
