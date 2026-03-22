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
# Функция расчёта "риска" для вклада с учётом истории клиента
# =======================
def calculate_deposit_risk(
        client_deals: List[Deal],
        deposit: Deal,
        lgd: float = 0.6
) -> str:
    """
    Рассчитывает эффект от новой депозитной сделки для клиента.
    Для банка депозит уменьшает чистую кредитную позицию (EAD).

    Параметры:
        client_deals: список старых сделок клиента (loan/deposit)
        deposit: объект TradeProposal для новой депозитной сделки
        lgd: потери при дефолте (по умолчанию 0.6, не критично для депозита)

    Возвращает:
        JSON-строку с отчётом по клиенту с учётом депозита.
    """
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

    # Добавляем новый депозит
    total_deposit += deposit.notional

    # Рассчитываем чистую кредитную позицию
    ead = max(0.0, total_loan - total_deposit)

    if ead == 0.0 or loan_sum == 0.0:
        # Чистая кредитная позиция обнулена депозитом
        result = {
            "client_id": deposit.client,
            "ead": 0.0,
            "avg_tenor": 0.0,
            "weighted_pd_annual": 0.0,
            "pd_total": 0.0,
            "lgd": lgd,
            "expected_loss": 0.0,
            "details": "Чистая кредитная позиция обнулена депозитом, риск для банка снижен"
        }
    else:
        # Взвешенный PD по кредитам
        weighted_pd_annual = weighted_pd / loan_sum
        avg_tenor = weighted_tenor / loan_sum
        pd_total = 1 - (1 - weighted_pd_annual) ** avg_tenor
        expected_loss = ead * pd_total * lgd

        result = {
            "client_id": deposit.client,
            "ead": round(ead, 2),
            "avg_tenor": round(avg_tenor, 2),
            "weighted_pd_annual": round(weighted_pd_annual, 4),
            "pd_total": round(pd_total, 4),
            "lgd": lgd,
            "expected_loss": round(expected_loss, 4),
            "details": "Риск по кредитам снижен за счёт депозита"
        }

    return json.dumps(result, default=safe_serializer)


# =======================
# Создание агента для оценки вклада
# =======================
def create_deposit_risk_agent(config_list):
    system_message = """
    Ты — аналитик кредитных рисков в банке. Твоя задача — оценивать, как депозитная сделка клиента влияет на его риск для банка.

    На вход ты получаешь:
      - новый депозит как объект TradeProposal
      - список старых сделок клиента (loan/deposit)

    Ты должен вызвать функцию calculate_deposit_risk и вернуть структурированный отчёт с метриками, 
    а также твой вердикт APPROVED / REJECTED - нужно ли реализовать эту сделку.
    Обрати внимание: депозит уменьшает чистую кредитную позицию, но сам по себе почти не создаёт риск.
    """

    tools_description = [
        {
            "type": "function",
            "function": {
                "name": "calculate_deposit_risk",
                "description": "Рассчитать эффект депозита на риск клиента",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_deals": {
                            "type": "array",
                            "description": "Список старых сделок клиента",
                            "items": {"type": "object"}
                        },
                        "deposit": {
                            "type": "object",
                            "description": "Новая депозитная сделка TradeProposal",
                        },
                        "lgd": {
                            "type": "number",
                            "description": "Потери при дефолте (по умолчанию 0.6)"
                        }
                    },
                    "required": ["client_deals", "deposit"]
                }
            }
        }
    ]

    agent = autogen.AssistantAgent(
        name="DepositRisk",
        system_message=system_message,
        llm_config={
            "config_list": config_list,
            "temperature": 0.2,
            "tools": tools_description,
        },
    )
    return agent
