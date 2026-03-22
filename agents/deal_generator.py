import autogen
from models.schemas import Deal
import json
from decimal import Decimal
from enum import Enum
from datetime import datetime


# =======================
# Сериализация нестандартных типов
# =======================
def safe_serializer(obj):
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()  # ISO 8601, валидный JSON
    return str(obj)  # fallback для любых других типов


# =======================
# Функция генерации предложения
# =======================
def generate_proposal(
        client: str,
        notional: float,
        currency: str,
        tenor_years: int,
        deal_direction: str,
        pd_annual: float,
        created_at: datetime,
        interest: float
) -> str:
    """
    Генерирует предложение по сделке и возвращает валидный JSON.
    """

    # Создаем объект модели сделки
    proposal = Deal(
        client=client,
        notional=notional,
        currency=currency,
        tenor_years=tenor_years,
        deal_direction=deal_direction,
        pd_annual=pd_annual,
        created_at=created_at,
        interest=interest
    )

    # Преобразуем в словарь
    proposal_dict = proposal.model_dump()

    # Явно преобразуем числовые поля, чтобы не было Decimal
    proposal_dict['notional'] = float(proposal_dict['notional'])
    proposal_dict['pd_annual'] = float(proposal_dict['pd_annual'])

    # Сериализуем в валидный JSON
    return json.dumps(proposal_dict, default=safe_serializer)


# =======================
# Создание агента генерации сделок
# =======================
def create_deal_generator_agent(config_list):
    system_message = """
    Ты — генератор вкладов и кредитов для конкретного банка.

    ТВОЯ ЗАДАЧА: Сгенерировать ровно одну сделку - ВКЛАД или КРЕДИТ.
    Ты ОБЯЗАН использовать функцию generate_proposal для формирования JSON.
    САМОЕ ВАЖНОЕ: Ты ОБЯЗАН вернуть корректный формат JSON.
    НЕ давай текстовых ответов, НЕ проси уточнений. Сразу вызывай функцию generate_proposal с правильными параметрами.
    Генерируй РАЗЛИЧНЫЕ сделки, анализируя историю диалога.
    Кредиторы и вкладчики - физические лица - обычные люди, выбирай размер сделки СООТВЕТСТВЕННО.
    Работай ТОЛЬКО в валюте RUB.
    
    Про даты и сроки:
    - Срок кредита ставь 1 год, срок вклада 3 года.
    - Дату начала и конца любой сделки ставь на начало какого-то квартала.
    - Даты заключения любых сделок должны лежать в отрезке от 01.01.2010 до 01.01.2020.
    - Дата заключения каждой следующей сделки строго позже предыдущей.

    Параметры функции generate_proposal:
    - client: id клиента (строка)
    - notional: номинал в миллионах (число)
    - currency: валюта ("RUB")
    - tenor_years: срок в годах (целое число)
    - deal_direction: направление ("deposit" или "loan")
    - pd_annual: годовой PD клиента (float)
    - created_at: дата заключения сделки (datetime)
    - interest: процент по кредиту или вкладу (float)

    """

    tools_description = [
        {
            "type": "function",
            "function": {
                "name": "generate_proposal",
                "description": "Сгенерировать предложение по сделке и вернуть JSON",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client": {
                            "type": "string",
                            "description": "id клиента"
                        },
                        "notional": {
                            "type": "number",
                            "description": "Номинал в миллионах"
                        },
                        "currency": {
                            "type": "string",
                            "enum": ["USD", "EUR", "GBP"],
                            "description": "Валюта"
                        },
                        "tenor_years": {
                            "type": "integer",
                            "description": "Срок в годах"
                        },
                        "deal_direction": {
                            "type": "string",
                            "enum": ["deposit", "loan"],
                            "description": "Направление сделки"
                        },
                        "pd_annual": {
                            "type": "float",
                            "description": "Годовой PD клиента"
                        },
                        "created_at": {
                            "type": "datetime",
                            "description": "Дата заключения сделки"
                        },
                        "interest": {
                            "type": "float",
                            "description": "Процент по вкладу или кредиту"
                        }
                    },
                    "required": ["client", "notional", "currency", "tenor_years", "deal_direction",
                                 "created_at", "interest"]
                }
            }
        }
    ]

    agent = autogen.AssistantAgent(
        name="DealGenerator",
        system_message=system_message,
        llm_config={
            "config_list": config_list,
            "temperature": 0.7,
            "tools": tools_description,
        },
    )
    return agent
