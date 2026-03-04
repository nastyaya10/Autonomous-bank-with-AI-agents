import random

def check_liquidity(currency: str, amount: float) -> dict:
    available = random.choice([True, False])
    balance = round(random.uniform(amount * 0.5, amount * 1.5), 2)
    return {
        "currency": currency,
        "required": amount,
        "available": available,
        "current_balance": balance,
        "deficit": round(max(0, amount - balance), 2) if not available else 0
    }
