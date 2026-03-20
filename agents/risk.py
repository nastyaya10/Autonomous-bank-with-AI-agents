import autogen
import json
import math
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Any, Optional

from models.schemas import TradeProposal


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
    if hasattr(obj, "dict"):        # Pydantic v1
        return obj.dict()
    return str(obj)


# =======================
# Функция расчёта риска для конкретного клиента
# =======================
def calculate_client_risk(
    client_deals: List[TradeProposal],
    lgd: float = 0.6
) -> str:
    """
    Рассчитывает кредитный риск для одного клиента на основе его сделок.
    Каждая сделка содержит собственное значение pd_annual.

    Параметры:
        client_deals: список объектов TradeProposal (старые сделки клиента)
        lgd: потери при дефолте (по умолчанию 0.6 = 60%)

    Возвращает:
        JSON-строку с отчётом по клиенту.
    """

    # Если нет сделок, возвращаем нулевой риск
    if not client_deals:
        result = {
            "client_id": None,
            "ead": 0.0,
            "avg_tenor": 0.0,
            "weighted_pd_annual": 0.0,
            "pd_total": 0.0,
            "lgd": lgd,
            "expected_loss": 0.0,
            "details": "Нет сделок"
        }
        return json.dumps(result, default=safe_serializer)

    # Извлекаем client_id из первой сделки (все сделки должны быть одного клиента)
    client_id = client_deals[0].client

    total_loan = 0.0
    total_deposit = 0.0
    weighted_tenor = 0.0
    loan_sum = 0.0
    weighted_pd = 0.0

    for deal in client_deals:
        if deal.deal_direction == "loan":
            total_loan += deal.notional
            weighted_tenor += deal.notional * deal.tenor_years
            loan_sum += deal.notional
            weighted_pd += deal.notional * deal.pd_annual
        elif deal.deal_direction == "deposit":
            total_deposit += deal.notional

    ead = max(0.0, total_loan - total_deposit)

    if ead == 0.0 or loan_sum == 0.0:
        result = {
            "client_id": client_id,
            "ead": 0.0,
            "avg_tenor": 0.0,
            "weighted_pd_annual": 0.0,
            "pd_total": 0.0,
            "lgd": lgd,
            "expected_loss": 0.0,
            "details": "Нет чистой кредитной позиции"
        }
    else:
        weighted_pd_annual = weighted_pd / loan_sum
        avg_tenor = weighted_tenor / loan_sum
        # Приведение годовой PD к сроку avg_tenor (точная формула)
        pd_total = 1 - (1 - weighted_pd_annual) ** avg_tenor
        expected_loss = ead * pd_total * lgd

        result = {
            "client_id": client_id,
            "ead": round(ead, 2),
            "avg_tenor": round(avg_tenor, 2),
            "weighted_pd_annual": round(weighted_pd_annual, 4),
            "pd_total": round(pd_total, 4),
            "lgd": lgd,
            "expected_loss": round(expected_loss, 4),
            "details": "Расчёт выполнен на основе индивидуальных PD сделок"
        }

    return json.dumps(result, default=safe_serializer)


# =======================
# Создание агента-аналитика рисков
# =======================
def create_client_risk_agent(config_list):
    system_message = """
    Ты — аналитик кредитных рисков в банке. Твоя задача — оценивать риск для конкретного клиента на основе списка его старых сделок.

    На вход ты получаешь список сделок клиента. Каждая сделка является объектом TradeProposal.
    Ты должен вызвать функцию calculate_client_risk, которая вернёт структурированный отчёт с метриками риска для этого клиента.
    Проанализируй ответ функции и реши, какой вердикт дать.
    Отвечай только APPROVED или REJECTED с причиной.

    Используй LGD=0.6 по умолчанию.
    Все сделки предполагаются в рублях (currency = "RUB").
    Если нет сделок, разреши эту сделку.
    """

    tools_description = [
        {
            "type": "function",
            "function": {
                "name": "calculate_client_risk",
                "description": "Рассчитать кредитный риск для клиента на основе его сделок",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_deals": {
                            "type": "array",
                            "description": "Список объектов TradeProposal (старые сделки клиента)",
                            "items": {
                                "type": "object",
                                "description": "Объект TradeProposal",
                                "properties": {
                                    "proposal_id": {"type": "string"},
                                    "client": {"type": "string"},
                                    "notional": {"type": "number"},
                                    "currency": {"type": "string", "enum": ["RUB"]},
                                    "tenor_years": {"type": "integer"},
                                    "deal_direction": {"type": "string", "enum": ["deposit", "loan"]},
                                    "pd_annual": {"type": "number", "description": "Годовая вероятность дефолта (0-1)"},
                                    "created_at": {"type": "string", "format": "date-time"},
                                    "interest": {"type": "number"}
                                },
                                "required": ["client", "notional", "currency", "tenor_years", "deal_direction", "pd_annual", "created_at", "interest"]
                            }
                        },
                        "lgd": {
                            "type": "number",
                            "description": "Потери при дефолте (по умолчанию 0.6)"
                        }
                    },
                    "required": ["client_deals"]
                }
            }
        }
    ]

    agent = autogen.AssistantAgent(
        name="Risk",
        system_message=system_message,
        llm_config={
            "config_list": config_list,
            "temperature": 0.2,
            "tools": tools_description,
        },
    )
    return agent
