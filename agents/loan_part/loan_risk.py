import autogen
import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List

from models.schemas import Deal


# =======================
# Сериализация нестандартных типов
# =======================
def safe_serializer(obj):
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):  # Pydantic v2
        return obj.model_dump()
    if hasattr(obj, "dict"):  # Pydantic v1
        return obj.dict()
    return str(obj)


# =======================
# Функция расчёта риска кредитной сделки с учётом истории клиента
# =======================
def calculate_loan_risk(
        client_deals: List[Deal],
        loan: Deal,
        lgd: float = 0.6
) -> str:
    """
    Рассчитывает кредитный риск для сделки клиента на основе истории его сделок.
    Сделка всегда является кредитом (loan).

    Параметры:
        client_deals: список старых сделок клиента (loan или deposit)
        loan: объект TradeProposal для рассматриваемой сделки
        lgd: потери при дефолте (по умолчанию 0.6)

    Возвращает:
        JSON-строку с отчётом по сделке.
    """
    # Если нет истории, считаем риск только по рассматриваемой сделке
    if not client_deals:
        ead = loan.notional
        pd_total = 1 - (1 - loan.pd_annual) ** loan.tenor_years
        expected_loss = ead * pd_total * lgd

        result = {
            "client_id": loan.client,
            "ead": round(ead, 2),
            "avg_tenor": loan.tenor_years,
            "weighted_pd_annual": round(loan.pd_annual, 4),
            "pd_total": round(pd_total, 4),
            "lgd": lgd,
            "expected_loss": round(expected_loss, 4),
            "details": "Нет истории, риск оценивается только по текущей сделке"
        }
        return json.dumps(result, default=safe_serializer)

    # Считаем чистую кредитную позицию клиента
    total_loan = 0.0
    total_deposit = 0.0
    weighted_tenor = 0.0
    weighted_pd = 0.0
    loan_sum = 0.0

    for deal in client_deals:
        if deal.deal_direction == "loan":
            total_loan += deal.notional
            weighted_tenor += deal.notional * deal.tenor_years
            loan_sum += deal.notional
            weighted_pd += deal.notional * deal.pd_annual
        elif deal.deal_direction == "deposit":
            total_deposit += deal.notional

    # Добавляем рассматриваемую сделку
    total_loan += loan.notional
    weighted_tenor += loan.notional * loan.tenor_years
    loan_sum += loan.notional
    weighted_pd += loan.notional * loan.pd_annual

    ead = max(0.0, total_loan - total_deposit)

    if ead == 0.0 or loan_sum == 0.0:
        result = {
            "client_id": loan.client,
            "ead": 0.0,
            "avg_tenor": 0.0,
            "weighted_pd_annual": 0.0,
            "pd_total": 0.0,
            "lgd": lgd,
            "expected_loss": 0.0,
            "details": "Нет чистой кредитной позиции после учёта сделки"
        }
    else:
        weighted_pd_annual = weighted_pd / loan_sum
        avg_tenor = weighted_tenor / loan_sum
        pd_total = 1 - (1 - weighted_pd_annual) ** avg_tenor
        expected_loss = ead * pd_total * lgd

        result = {
            "client_id": loan.client,
            "ead": round(ead, 2),
            "avg_tenor": round(avg_tenor, 2),
            "weighted_pd_annual": round(weighted_pd_annual, 4),
            "pd_total": round(pd_total, 4),
            "lgd": lgd,
            "expected_loss": round(expected_loss, 4),
            "details": "Риск рассчитан с учётом истории и текущей кредитной сделки"
        }

    return json.dumps(result, default=safe_serializer)


# =======================
# Создание агента для оценки кредитной сделки
# =======================
def create_loan_risk_agent(config_list):
    system_message = """
    Ты — аналитик кредитных рисков в банке. Твоя задача — оценивать риск кредитной сделки для конкретного клиента.

    На вход ты получаешь:
      - сделку (loan) как объект TradeProposal
      - список старых сделок клиента (loan/deposit)

    Ты должен вызвать функцию calculate_loan_risk, которая вернёт структурированный отчёт с метриками, 
    а также твой вердикт APPROVED / REJECTED - нужно ли реализовать эту сделку..
    Проанализируй результат и дай вердикт: APPROVED или REJECTED с объяснением.

    Используй LGD=0.6 по умолчанию.
    Все сделки предполагаются в рублях (currency = "RUB").
    Если нет истории, разреши сделку.
    """

    tools_description = [
        {
            "type": "function",
            "function": {
                "name": "calculate_loan_risk",
                "description": "Рассчитать риск кредитной сделки на основе истории клиента",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_deals": {
                            "type": "array",
                            "description": "Список старых сделок клиента",
                            "items": {"type": "object"}
                        },
                        "loan": {
                            "type": "object",
                            "description": "Кредитная сделка TradeProposal",
                        },
                        "lgd": {
                            "type": "number",
                            "description": "Потери при дефолте (по умолчанию 0.6)"
                        }
                    },
                    "required": ["client_deals", "loan"]
                }
            }
        }
    ]

    agent = autogen.AssistantAgent(
        name="LoanRisk",
        system_message=system_message,
        llm_config={
            "config_list": config_list,
            "temperature": 0.2,
            "tools": tools_description,
        },
    )
    return agent
