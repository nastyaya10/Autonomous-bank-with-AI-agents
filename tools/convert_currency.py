from typing import Dict, Optional

def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    rates: Optional[Dict[str, float]] = None,
    base_currency: str = "USD"
) -> float:
    """
    Конвертирует сумму из одной валюты в другую.

    Параметры:
    amount : float — сумма в исходной валюте
    from_currency : str — код исходной валюты (например, "RUB")
    to_currency : str — код целевой валюты (например, "USD")
    rates : dict, optional — словарь курсов относительно base_currency.
            Если не передан, используются фиктивные курсы для демонстрации.
    base_currency : str — базовая валюта, относительно которой заданы курсы.

    Возвращает:
    float — сумма в целевой валюте.
    """
    # Если курсы не предоставлены, используем тестовые значения
    if rates is None:
        rates = {
            "USD": 1.0,
            "EUR": 0.92,
            "RUB": 97.5,
            "GBP": 0.79,
            "JPY": 150.2
        }
        base_currency = "USD"

    # Приводим к базовой валюте, затем к целевой
    if from_currency == base_currency:
        amount_in_base = amount
    else:
        if from_currency not in rates:
            raise ValueError(f"Курс для валюты {from_currency} не найден")
        amount_in_base = amount / rates[from_currency]

    if to_currency == base_currency:
        return amount_in_base
    else:
        if to_currency not in rates:
            raise ValueError(f"Курс для валюты {to_currency} не найден")
        return amount_in_base * rates[to_currency]