from models.schemas import Balance
from tools.convert_currency import convert_currency


def check_liquidity(currency: str, amount: float, balance: Balance) -> dict:
    available = False
    convert_currency(balance.amount, balance.currency, currency)
    if balance.amount >= amount:
        available = True
    return {
        "currency": currency,
        "required": amount,
        "available": available,
        "current_balance": balance,
        "deficit": (amount - balance) if not available else 0
    }
