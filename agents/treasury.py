import autogen
from tools.liquidity import check_liquidity as check_liquidity_service


# Функция-инструмент
def check_liquidity(currency: str, amount: float) -> str:
    result = check_liquidity_service(currency, amount)
    if result["available"]:
        return f"APPROVED: ликвидность доступна, баланс {result['current_balance']}M {currency}"
    else:
        return f"REJECTED: недостаточно {currency}, требуется {amount}M, доступно {result['current_balance']}M"


def create_treasury_agent(config_list):
    system_message = """
    Ты — начальник казначейства.
    Проверяй сделки на наличие ликвидности.
    Используй функцию check_liquidity.
    Отвечай только APPROVED или REJECTED с причиной.
    """

    tools_description = [
        {
            "type": "function",
            "function": {
                "name": "check_liquidity",
                "description": "Проверить наличие ликвидности",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "currency": {"type": "string"},
                        "amount": {"type": "number"}
                    },
                    "required": ["currency", "amount"]
                }
            }
        }
    ]

    agent = autogen.AssistantAgent(
        name="Treasury",
        system_message=system_message,
        llm_config={
            "config_list": config_list,
            "temperature": 0.1,
            "tools": tools_description,
        },
    )
    return agent
