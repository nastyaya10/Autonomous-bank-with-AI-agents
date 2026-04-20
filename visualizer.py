import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os


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

    # Эволюция портфеля
    plt.figure(figsize=(12, 6))
    plt.plot(dates, loans, label="Кредиты", marker='.')
    plt.plot(dates, deposits, label="Депозиты", marker='.')
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

    # GAP по корзинам
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

    # NII и VaR
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
    from models import YieldCurve
    yc = YieldCurve(key_rate=0.21)
    terms = [1, 3, 6, 12, 24, 36, 60]
    rates = [yc.rate(t) * 100 for t in terms]
    plt.figure(figsize=(8, 5))
    plt.plot(terms, rates, marker='o', linestyle='-')
    plt.title("Кривая ОФЗ (плоская)")
    plt.xlabel("Срок, мес.")
    plt.ylabel("Ставка, %")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("plots/yield_curve.png")
    plt.close()

    print("Все графики сохранены в папку 'plots/'")
