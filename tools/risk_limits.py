import random

def check_counterparty_limit(counterparty: str, amount: float) -> dict:
    limits = {"Bank A": 50.0, "Bank B": 30.0, "Bank C": 20.0, "default": 25.0}
    limit = limits.get(counterparty, limits["default"])
    used = random.uniform(0, limit * 0.9)
    remaining = round(limit - used, 2)
    return {
        "counterparty": counterparty,
        "limit": limit,
        "used": round(used, 2),
        "remaining": remaining,
        "within_limit": amount <= remaining
    }

def calculate_capital_impact(trade_data: dict) -> dict:
    notional = trade_data.get("notional", 0)
    rwa_impact = notional * 0.05
    capital_charge = rwa_impact * 0.08
    return {
        "rwa_increase": round(rwa_impact, 2),
        "capital_charge": round(capital_charge, 2),
        "acceptable": capital_charge < 1.0
    }
