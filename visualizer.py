import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
from models import YieldCurve, Portfolio

def setup_plots_dir():
    os.makedirs("plots", exist_ok=True)

def plot_time_series(snapshots):
    setup_plots_dir()
    dates = [s.date for s in snapshots]
    loans = [s.loans for s in snapshots]
    deposits = [s.deposits for s in snapshots]
    net = [s.net for s in snapshots]
    nii = [s.nii for s in snapshots]
    var = [s.var for s in snapshots]

    # График портфеля
    plt.figure(figsize=(12, 6))
    plt.plot(dates, loans, label="Кредиты", marker='.', linestyle='-')
    plt.plot(dates, deposits, label="Депозиты", marker='.', linestyle='-')
    plt.plot(dates, net, label="Нетто-позиция", linestyle='--')
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

    # График GAP
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

    # График NII и VaR
    plt.figure(figsize=(12, 6))
    plt.plot(dates, nii, label="NII (накопленный)", color='green')
    plt.plot(dates, var, label="VaR(95%)", color='red', linestyle='--')
    plt.title("NII и VaR во времени")
    plt.xlabel("Дата")
    plt.ylabel("Руб.")
    plt.legend()
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("plots/nii_var.png")
    plt.close()

    # Кривая ОФЗ (статическая)
    yc = YieldCurve(key_rate=0.21)
    terms = [1, 3, 6, 12, 24, 36, 60]
    rates = [yc.rate(t) * 100 for t in terms]
    plt.figure(figsize=(8, 5))
    plt.plot(terms, rates, marker='o', linestyle='-')
    plt.title("Кривая ОФЗ (ключевая ставка 21% + 2%)")
    plt.xlabel("Срок, мес.")
    plt.ylabel("Ставка, %")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("plots/yield_curve.png")
    plt.close()

    print("Все графики сохранены в папку 'plots/'")

def plot_deposit_rates(yield_curve: YieldCurve, portfolio: Portfolio):
    """График сравнения депозитных ставок и кривой ОФЗ"""
    setup_plots_dir()
    # Собираем все активные депозиты (на момент вызова они уже активны)
    deposits = portfolio.deposits
    if not deposits:
        print("Нет активных депозитов для графика ставок.")
        return

    deposit_terms = [d.term_months for d in deposits]
    deposit_rates = [d.rate * 100 for d in deposits]   # переводим в проценты

    # Кривая ОФЗ для диапазона сроков
    terms_range = sorted(set(deposit_terms + [1, 3, 6, 12, 24, 36, 60]))
    terms_range = [t for t in terms_range if t > 0]
    yc_rates = [yield_curve.rate(t) * 100 for t in terms_range]

    plt.figure(figsize=(10, 6))
    plt.plot(terms_range, yc_rates, 'r-', linewidth=2, label='Кривая ОФЗ (базовая)')
    plt.scatter(deposit_terms, deposit_rates, color='blue', alpha=0.6, label='Депозитные ставки')
    plt.title("Соответствие депозитных ставок кривой ОФЗ")
    plt.xlabel("Срок, мес.")
    plt.ylabel("Ставка, % годовых")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("plots/deposit_rates_vs_yield_curve.png")
    plt.close()
    print("График депозитных ставок сохранён в 'plots/deposit_rates_vs_yield_curve.png'")