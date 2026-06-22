import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
from models import RealYieldCurve


def setup_plots_dir():
    os.makedirs("plots", exist_ok=True)


def plot_time_series(snapshots, label="", suffix=""):
    """Графики эволюции портфеля, ЧПД, EL для одного сценария."""
    setup_plots_dir()
    dates = [s.date for s in snapshots]
    loans = [s.loans for s in snapshots]
    deposits = [s.deposits for s in snapshots]
    nii = [s.nii for s in snapshots]
    el = [s.expected_loss for s in snapshots]

    plt.figure(figsize=(12, 6))
    plt.plot(dates, loans, label="Кредиты", marker='.', linestyle='-')
    plt.plot(dates, deposits, label="Депозиты", marker='.', linestyle='-')
    plt.title(f"Эволюция портфеля ({label})")
    plt.xlabel("Дата")
    plt.ylabel("Сумма, руб.")
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
    plt.ylabel("Руб.")
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
    plt.ylabel("Руб.")
    plt.legend()
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f"plots/el_{suffix}.png")
    plt.close()


def plot_rates_vs_curve(yield_curve: RealYieldCurve, loans: list, deposits: list, label="", suffix=""):
    setup_plots_dir()
    dep_terms = [d.term_months for d in deposits]
    dep_rates = [d.rate * 100 for d in deposits]
    loan_terms = [l.term_months for l in loans]
    loan_rates = [l.rate * 100 for l in loans]

    all_terms = sorted(set(dep_terms + loan_terms + [1, 3, 6, 12, 24, 36, 48, 60, 72, 84]))
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


def plot_stress_test_curve(base_curve, loans, deposits, stress_shifts, credit_spread_low=0.06, credit_spread_high=0.08,
                           deposit_discount=0.05):
    """График стресс-теста кривой ОФЗ (гибрид)."""
    setup_plots_dir()
    real_dep_terms = [d.term_months for d in deposits]
    real_dep_rates = [d.rate * 100 for d in deposits]
    real_loan_terms = [l.term_months for l in loans]
    real_loan_rates = [l.rate * 100 for l in loans]

    hypo_loan_terms, hypo_loan_rates = [], []
    hypo_dep_terms, hypo_dep_rates = [], []

    for d in deposits:
        t = d.term_months
        stress_rate = base_curve.rate(t) + _shift_for_term(t, stress_shifts) / 100.0
        hypo_dep_terms.append(t)
        hypo_dep_rates.append(max(0.01, stress_rate - deposit_discount) * 100)

    for l in loans:
        t = l.term_months
        norm = (l.credit_score - 1) / 998
        spread = credit_spread_high - (credit_spread_high - credit_spread_low) * norm
        stress_rate = base_curve.rate(t) + _shift_for_term(t, stress_shifts) / 100.0
        hypo_loan_terms.append(t)
        hypo_loan_rates.append((stress_rate + spread) * 100)

    all_terms = sorted(
        set(real_dep_terms + real_loan_terms + hypo_loan_terms + hypo_dep_terms + [1, 3, 6, 12, 24, 36, 48, 60, 72,
                                                                                   84]))
    base_yc = [base_curve.rate(t) * 100 for t in all_terms]
    stressed_yc = [base_curve.rate(t) * 100 + _shift_for_term(t, stress_shifts) for t in all_terms]

    plt.figure(figsize=(12, 7))
    plt.plot(all_terms, base_yc, color='red', linewidth=1, alpha=0.2, label='ОФЗ текущая (бледная)')
    plt.plot(all_terms, stressed_yc, color='red', linewidth=3, alpha=1.0, label='ОФЗ стресс (яркая)')
    if real_dep_terms:
        plt.scatter(real_dep_terms, real_dep_rates, color='blue', alpha=0.1, s=40, label='Депозиты (реальные)')
    if real_loan_terms:
        plt.scatter(real_loan_terms, real_loan_rates, color='green', alpha=0.1, s=40, marker='s',
                    label='Кредиты (реальные)')
    if hypo_dep_terms:
        plt.scatter(hypo_dep_terms, hypo_dep_rates, color='blue', alpha=1.0, s=70, edgecolors='black', linewidths=0.8,
                    label='Депозиты (стресс)')
    if hypo_loan_terms:
        plt.scatter(hypo_loan_terms, hypo_loan_rates, color='green', alpha=1.0, s=70, marker='s', edgecolors='black',
                    linewidths=0.8, label='Кредиты (стресс)')
    plt.title("Стресс-тест кривой ОФЗ: текущая vs гибрид с 2022")
    plt.xlabel("Срок, мес.")
    plt.ylabel("Ставка, % годовых")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("plots/stress_test_curve.png")
    plt.close()


def _shift_for_term(term_months, shifts):
    for limit, shift in sorted(shifts.items()):
        if term_months <= limit:
            return shift
    return 0.0


def plot_gap_barchart(gap, title_suffix=""):
    setup_plots_dir()
    buckets = list(gap.keys())
    values = list(gap.values())
    colors = ['green' if v >= 0 else 'red' for v in values]
    plt.figure(figsize=(8, 5))
    plt.bar(buckets, values, color=colors)
    plt.title(f"GAP по срочностям{title_suffix}")
    plt.xlabel("Срок")
    plt.ylabel("GAP, руб.")
    plt.grid(True, axis='y')
    plt.tight_layout()
    filename = f"plots/gap_barchart{title_suffix.replace(' ', '_').replace('(', '').replace(')', '')}.png"
    plt.savefig(filename)
    plt.close()


def plot_comparison_bars(base_pnl, stress_pnl, base_gap, stress_gap):
    """Столбчатая диаграмма сравнения итоговых ЧПД и GAP по корзинам."""
    setup_plots_dir()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # ЧПД
    ax1.bar(["Базовый", "Стресс"], [base_pnl.net_interest_income, stress_pnl.net_interest_income],
            color=['blue', 'red'], alpha=0.7)
    ax1.set_title("Итоговый ЧПД")
    ax1.set_ylabel("Руб.")
    ax1.grid(True, axis='y')

    # GAP по корзинам
    buckets = list(base_gap.keys())
    base_vals = [base_gap[b] for b in buckets]
    stress_vals = [stress_gap[b] for b in buckets]
    x = range(len(buckets))
    width = 0.35
    ax2.bar([i - width / 2 for i in x], base_vals, width, label='Базовый', color='blue', alpha=0.7)
    ax2.bar([i + width / 2 for i in x], stress_vals, width, label='Стресс', color='red', alpha=0.7)
    ax2.set_xticks(x)
    ax2.set_xticklabels(buckets)
    ax2.set_title("GAP по срочностям на конец периода")
    ax2.legend()
    ax2.grid(True, axis='y')
    plt.tight_layout()
    plt.savefig("plots/comparison_bars.png")
    plt.close()


def plot_comparison_lines(base_snapshots, stress_snapshots):
    """Линейные графики динамики ЧПД и портфеля для двух сценариев."""
    setup_plots_dir()
    base_dates = [s.date for s in base_snapshots]
    stress_dates = [s.date for s in stress_snapshots]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    # ЧПД
    ax1.plot(base_dates, [s.nii for s in base_snapshots], label="ЧПД базовый", color='blue')
    ax1.plot(stress_dates, [s.nii for s in stress_snapshots], label="ЧПД стресс", color='red')
    ax1.set_title("Динамика ЧПД")
    ax1.legend()
    ax1.grid(True)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax1.tick_params(axis='x', rotation=45)

    # Портфель (кредиты и депозиты)
    ax2.plot(base_dates, [s.loans for s in base_snapshots], label="Кредиты базовый", linestyle='-', color='blue')
    ax2.plot(base_dates, [s.deposits for s in base_snapshots], label="Депозиты базовый", linestyle='--', color='blue')
    ax2.plot(stress_dates, [s.loans for s in stress_snapshots], label="Кредиты стресс", linestyle='-', color='red')
    ax2.plot(stress_dates, [s.deposits for s in stress_snapshots], label="Депозиты стресс", linestyle='--', color='red')
    ax2.set_title("Динамика портфеля")
    ax2.legend()
    ax2.grid(True)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax2.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig("plots/comparison_lines.png")
    plt.close()
