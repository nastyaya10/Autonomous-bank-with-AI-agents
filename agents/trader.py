import autogen
from models.schemas import TradeProposal, TradeType
from tools.market_data import calculate_pv01
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
        trade_type: str,
        notional: float,
        currency: str,
        counterparty: str,
        tenor_years: int,
        deal_direction: str,
        created_at: datetime
) -> str:
    """
    Генерирует предложение по сделке и возвращает валидный JSON.
    """

    # Исправляем некорректные типы сделок
    if trade_type == "swap":
        trade_type = "interest_rate_swap"

    # Рассчитываем risk metric
    pv01 = calculate_pv01(notional, tenor_years)

    # Создаем объект модели сделки
    proposal = TradeProposal(
        trade_type=TradeType(trade_type),
        notional=notional,
        currency=currency,
        counterparty=counterparty,
        tenor_years=tenor_years,
        deal_direction=deal_direction,
        risk_metrics={"pv01": pv01, "duration": tenor_years},
        created_at=created_at
    )

    # Преобразуем в словарь
    proposal_dict = proposal.model_dump()

    # Явно преобразуем числовые поля, чтобы не было Decimal
    proposal_dict['notional'] = float(proposal_dict['notional'])
    proposal_dict['risk_metrics']['duration'] = int(proposal_dict['risk_metrics']['duration'])

    # Сериализуем в валидный JSON
    return json.dumps(proposal_dict, default=safe_serializer)


# =======================
# Создание трейдерского агента
# =======================
def create_trader_agent(config_list):
    system_message = """
    Ты — трейдер на рынке деривативов.

    ТВОЯ ЗАДАЧА: Сгенерировать ровно одну сделку.
    Ты ОБЯЗАН использовать функцию generate_proposal для формирования JSON.
    Ты ОБЯЗАН вернуть корректный формат JSON.
    НЕ давай текстовых ответов, НЕ проси уточнений. Сразу вызывай функцию generate_proposal с правильными параметрами.
    
    Срок кредита ставь 1 год, срок вклада 3 года.
    Дату начала и конца любой сделки ставь на начало квартала.
    Даты заключения любых сделок должны лежать в отрезке от 01.01.2010 до 01.01.2020.
    Каждая следующая сделка должна быть заключена СТРОГО после предыдущей, уже в другом квартале.
    
    Генерируй РАЗЛИЧНЫЕ сделки, анализируя историю диалога.

    Параметры функции:
    - trade_type: тип сделки ("interest_rate_swap", "bond", "fx_swap")
    - notional: номинал в миллионах (число)
    - currency: валюта ("USD", "EUR", "GBP")
    - counterparty: контрагент (например, "Bank A")
    - tenor_years: срок в годах (целое число)
    - deal_direction: направление ("BUY" или "SELL")
    - created_at: дата заключения сделки (datetime)

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
                        "trade_type": {
                            "type": "string",
                            "enum": ["interest_rate_swap", "bond", "fx_swap"],
                            "description": "Тип сделки"
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
                        "counterparty": {
                            "type": "string",
                            "description": "Контрагент"
                        },
                        "tenor_years": {
                            "type": "integer",
                            "description": "Срок в годах"
                        },
                        "deal_direction": {
                            "type": "string",
                            "enum": ["BUY", "SELL"],
                            "description": "Направление сделки"
                        },
                        "created_at": {
                            "type": "datetime",
                            "description": "Дата заключения сделки"
                        }
                    },
                    "required": ["trade_type", "notional", "currency", "counterparty", "tenor_years", "deal_direction",
                                 "created_at"]
                }
            }
        }
    ]

    agent = autogen.AssistantAgent(
        name="Trader",
        system_message=system_message,
        llm_config={
            "config_list": config_list,
            "temperature": 0.7,
            "tools": tools_description,
        },
    )
    return agent
