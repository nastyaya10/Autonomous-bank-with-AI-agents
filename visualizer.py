import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
from models import RealYieldCurve, Portfolio


def setup_plots_dir():
    os.makedirs("plots", exist_ok=True)


def plot_time_series(snapshots):
    setup_plots_dir()
    dates = [s.date for s in snapshots]
    loans = [s.loans for s in snapshots]
    deposits = [s.deposits for s in snapshots]
    nii = [s.nii for s in snapshots]
    el = [s.expected_loss for s in snapshots]

    # График портфеля (кредиты и депозиты)
    plt.figure(figsize=(12, 6))
    plt.plot(dates, loans, label="Кредиты", marker='.', linestyle='-')
    plt.plot(dates, deposits, label="Депозиты", marker='.', linestyle='-')
    plt.title("Эволюция портфеля во времени")
    plt.xlabel("Дата")
    plt.ylabel("Сумма, руб.")
    plt.legend()
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("plots/portfolio_evolution.png")
    plt.close()

    # График GAP (stacked area)
    buckets = ["0-90d", "90-180d", "180-365d", ">365d"]
    gap_data = {b: [] for b in buckets}
    for s in snapshots:
        for b in buckets:
            gap_data[b].append(s.gap.get(b, 0.0))
    plt.figure(figsize=(12, 6))
    plt.stackplot(dates, gap_data.values(), labels=buckets, alpha=0.7)
    plt.title("Эволюция процентного GAP по оставшемуся сроку")
    plt.xlabel("Дата")
    plt.ylabel("GAP, руб.")
    plt.legend(loc='upper left')
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("plots/gap_evolution.png")
    plt.close()

    # График ЧПД (NII)
    plt.figure(figsize=(12, 6))
    plt.plot(dates, nii, label="ЧПД (накопленный)", color='green')
    plt.title("Чистый процентный доход (ЧПД) во времени")
    plt.xlabel("Дата")
    plt.ylabel("Руб.")
    plt.legend()
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("plots/nii.png")
    plt.close()

    # График ожидаемых потерь (EL)
    plt.figure(figsize=(12, 6))
    plt.plot(dates, el, label="Ожидаемые потери (EL)", color='orange', linestyle='-.')
    plt.title("Ожидаемые потери (EL) во времени")
    plt.xlabel("Дата")
    plt.ylabel("Руб.")
    plt.legend()
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("plots/el.png")
    plt.close()

    print("Все графики сохранены в папку 'plots/'")


def plot_rates_vs_curve(yield_curve, portfolio: Portfolio):
    """График ставок (депозитов и кредитов) относительно кривой ОФЗ."""
    setup_plots_dir()
    deposits = portfolio.deposits
    loans = portfolio.loans

    dep_terms = [d.term_months for d in deposits]
    dep_rates = [d.rate * 100 for d in deposits]

    loan_terms = [l.term_months for l in loans]
    loan_rates = [l.rate * 100 for l in loans]

    all_terms = sorted(set(dep_terms + loan_terms + [1, 3, 6, 12, 24, 36, 60]))
    yc_rates = [yield_curve.rate(t) * 100 for t in all_terms]

    plt.figure(figsize=(10, 6))
    plt.plot(all_terms, yc_rates, 'r-', linewidth=2, label='Кривая ОФЗ')
    if dep_terms:
        plt.scatter(dep_terms, dep_rates, color='blue', alpha=0.6, label='Депозитные ставки')
    if loan_terms:
        plt.scatter(loan_terms, loan_rates, color='green', alpha=0.6, marker='s', label='Кредитные ставки')
    plt.title("Ставки банка vs кривая ОФЗ")
    plt.xlabel("Срок, мес.")
    plt.ylabel("Ставка, % годовых")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("plots/rates_vs_yield_curve.png")
    plt.close()
    print("График ставок сохранён в 'plots/rates_vs_yield_curve.png'")


def plot_stress_test(stress_dates, base_nii, shocked_nii):
    setup_plots_dir()
    plt.figure(figsize=(10, 5))
    plt.plot(stress_dates, base_nii, label="ЧПД базовый", marker='o')
    plt.plot(stress_dates, shocked_nii, label="ЧПД после шока (+4%)", marker='x')
    plt.title("Стресс-тест ЧПД при шоке ключевой ставки на +4%")
    plt.xlabel("Дата")
    plt.ylabel("ЧПД, руб.")
    plt.legend()
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("plots/stress_test_nii.png")
    plt.close()
    print("График стресс-теста сохранён в 'plots/stress_test_nii.png'")


def plot_gap_barchart(gap: dict):
    """Bar chart GAP по срочностям на последний день."""
    setup_plots_dir()
    buckets = list(gap.keys())
    values = list(gap.values())
    colors = ['green' if v >= 0 else 'red' for v in values]
    plt.figure(figsize=(8, 5))
    plt.bar(buckets, values, color=colors)
    plt.title("GAP по срочностям (на конец периода)")
    plt.xlabel("Срок")
    plt.ylabel("GAP, руб.")
    plt.grid(True, axis='y')
    plt.tight_layout()
    plt.savefig("plots/gap_barchart.png")
    plt.close()
    print("Bar chart GAP сохранён в 'plots/gap_barchart.png'")
