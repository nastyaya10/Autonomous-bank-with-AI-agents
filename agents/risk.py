import autogen
import json
from tools.risk_limits import check_counterparty_limit, calculate_capital_impact


# Функция-инструмент, доступная для импорта
def check_limits(counterparty: str, amount: float, proposal_json: str) -> str:
    """Проверяет лимиты на контрагента и влияние на капитал, используя полный JSON сделки."""
    # Проверка лимита на контрагента
    limit_check = check_counterparty_limit(counterparty, amount)
    if not limit_check["within_limit"]:
        return f"REJECTED: лимит на {counterparty} исчерпан, осталось {limit_check['remaining']}M"

    # Проверка влияния на капитал
    try:
        trade_dict = json.loads(proposal_json)
    except json.JSONDecodeError:
        return "REJECTED: ошибка в JSON сделки"

    capital_check = calculate_capital_impact(trade_dict)
    if not capital_check["acceptable"]:
        return f"REJECTED: влияние на капитал {capital_check['capital_charge']}M превышает порог"

    return "APPROVED"


def create_risk_agent(config_list):
    system_message = """
    Ты — глава отдела рисков.

    ТВОЯ ЗАДАЧА: Проверять сделки на лимиты контрагента и влияние на капитал.

    ПРАВИЛА:
    1. Ты получаешь JSON с данными сделки.
    2. Используй функцию check_limits, передавая ей три параметра:
       - counterparty: название контрагента (например, "Bank A")
       - amount: сумма сделки в миллионах (число)
       - proposal_json: **ТОЧНАЯ КОПИЯ** JSON сделки, который ты получил (скопируй его целиком)
    3. Функция вернёт результат проверки.
    4. После получения результата, если он содержит "APPROVED", ответь "APPROVED". Если содержит "REJECTED", ответь "REJECTED: <причина>".
    5. НИКАКИХ других ответов, только APPROVED или REJECTED.

    Пример вызова:
    check_limits(counterparty="Bank A", amount=10, proposal_json='{"proposal_id":"abc123","trade_type":"interest_rate_swap","notional":10,"currency":"USD","counterparty":"Bank A","tenor_years":5,"deal_direction":"BUY","risk_metrics":{"pv01":0.005,"duration":5},"created_at":"2025-03-03 12:00:00"}')
    """

    # Описание инструмента для LLM (с улучшенным параметром)
    tools_description = [
        {
            "type": "function",
            "function": {
                "name": "check_limits",
                "description": "Проверить лимиты на контрагента и влияние на капитал. Параметр proposal_json должен быть точной копией JSON сделки, которую вы получили.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "counterparty": {
                            "type": "string",
                            "description": "Название контрагента"
                        },
                        "amount": {
                            "type": "number",
                            "description": "Сумма сделки в миллионах"
                        },
                        "proposal_json": {
                            "type": "string",
                            "description": "Полный JSON сделки (скопируйте его из сообщения, которое вы получили)"
                        }
                    },
                    "required": ["counterparty", "amount", "proposal_json"]
                }
            }
        }
    ]

    agent = autogen.AssistantAgent(
        name="Risk",
        system_message=system_message,
        llm_config={
            "config_list": config_list,
            "temperature": 0.1,
            "tools": tools_description,
        },
    )
    return agent