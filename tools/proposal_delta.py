from datetime import datetime
import models.schemas
import math


def evaluate_trade(
        trade: models.schemas.TradeProposal,
        current_date: datetime,
        include_interest: bool = True  # оставлен для совместимости
) -> dict[str, float | str]:
    """
    Возвращает:
    {
        "principal": остаток без процентов,
        "total": остаток с процентами,
        "currency": валюта
    }

    +  -> клиент должен банку (loan)
    -  -> банк должен клиенту (deposit)
    """

    notional = trade.notional
    annual_rate = trade.interest

    # квартальные параметры
    periods_per_year = 4
    total_periods = trade.tenor_years * periods_per_year
    period_rate = annual_rate / periods_per_year

    # сколько прошло времени
    elapsed_days = (current_date - trade.created_at).days
    elapsed_years = max(elapsed_days / 365, 0)

    elapsed_periods = min(int(elapsed_years * periods_per_year), total_periods)

    # аннуитетный платеж
    if period_rate > 0:
        payment = notional * (period_rate * (1 + period_rate) ** total_periods) / (
                (1 + period_rate) ** total_periods - 1
        )
    else:
        payment = notional / total_periods

    remaining_principal = notional

    # прогоняем уже прошедшие платежи
    for _ in range(elapsed_periods):
        interest_part = remaining_principal * period_rate
        principal_part = payment - interest_part
        remaining_principal -= principal_part

    # остаток с учётом процентов (следующий период)
    accrued_interest = remaining_principal * period_rate
    total_value = remaining_principal + accrued_interest

    if trade.deal_direction == "deposit":
        principal_value = -remaining_principal
        total_value = -total_value
    else:
        principal_value = remaining_principal

    return {
        "principal": principal_value,
        "total": total_value,
        "currency": trade.currency
    }
