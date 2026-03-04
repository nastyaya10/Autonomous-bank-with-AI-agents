def calculate_pv01(notional: float, tenor: int) -> float:
    return round(notional * tenor * 0.0001, 4)
