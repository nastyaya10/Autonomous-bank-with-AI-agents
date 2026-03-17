from models.schemas import Balance
from tools.convert_currency import convert_currency


def check_liquidity(currency: str, amount: float, balance: Balance) -> dict:
    available = False
    amount_in_valid_currency = convert_currency(balance.amount, balance.currency, currency)
    if amount_in_valid_currency >= amount:
        available = True
    return {
        "currency": currency,
        "required": amount,
        "available": available,
        "current_balance": balance,
        "deficit": (amount - balance.amount) if not available else 0
    }
