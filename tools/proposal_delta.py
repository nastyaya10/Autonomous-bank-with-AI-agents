from datetime import datetime
from typing import Dict, Any
import models.schemas


def evaluate_trade(trade: models.schemas.TradeProposal, current_date: datetime) -> dict[str, str | float | int | Any] | None:
    """
    Оценивает прибыль/убыток сделки на текущую дату.
    """

    # срок окончания сделки
    maturity_date = trade.created_at.replace(
        year=trade.created_at.year + trade.tenor_years
    )

    # оставшееся время в годах
    remaining_days = (maturity_date - current_date).days
    remaining_years = max(remaining_days / 365, 0)

    if remaining_days > 0:
        return None

    # базовые метрики
    rate = trade.risk_metrics.get("rate", 0)
    market_rate = trade.risk_metrics.get("market_rate", rate)

    notional = trade.notional * 1_000_000

    # простая модель PnL
    rate_diff = market_rate - rate

    if trade.deal_direction == "BUY":
        pnl = rate_diff * notional * remaining_years
    else:
        pnl = -rate_diff * notional * remaining_years

    status = "MATURED" if remaining_days <= 0 else "ACTIVE"

    return {
        "proposal_id": trade.proposal_id,
        "status": status,
        "remaining_years": remaining_years,
        "pnl": pnl,
        "notional": notional,
        "rate": rate,
        "market_rate": market_rate,
        "currency": trade.currency
    }
