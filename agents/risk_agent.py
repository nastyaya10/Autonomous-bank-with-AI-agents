from llm_agent import LLMAgent
from utils import write_report, logger


class RiskAgent(LLMAgent):
    def __init__(self, name: str, portfolio, config_list: list):
        system_prompt = (
            "Ты риск-менеджер банка. Твоя задача — проанализировать текущее состояние портфеля "
            "и риски, дать краткую рекомендацию (1-2 предложения).\n"
            "Учитывай GAP ликвидности, VaR, чувствительность NII.\n"
            "Если риски высоки, предложи меры: сократить кредитование, привлечь больше депозитов, "
            "изменить структуру активов/пассивов.\n"
            "Отвечай только текстом, не используй JSON."
        )
        # температура 0.5 для разнообразия рекомендаций
        super().__init__(name, config_list, system_prompt, temperature=0.5)
        self.portfolio = portfolio

    def receive(self, from_agent: str, message: dict):
        if message.get("type") != "risk_assessment":
            return

        data = message
        prompt = (
            f"Текущее состояние:\n"
            f"Кредиты: {data['loans']:,.2f} руб.\n"
            f"Депозиты: {data['deposits']:,.2f} руб.\n"
            f"Нетто-позиция: {data['net']:,.2f} руб.\n"
            f"GAP по срокам: 0-90д: {data['gap'].get('0-90d', 0):,.2f}, "
            f"90-180д: {data['gap'].get('90-180d', 0):,.2f}, "
            f"180-365д: {data['gap'].get('180-365d', 0):,.2f}, "
            f">365д: {data['gap'].get('>365d', 0):,.2f} руб.\n"
            f"NII (накопленный): {data['nii']:,.2f} руб.\n"
            f"VaR(95%): {data['var']:,.2f} руб.\n"
            f"Чувствительность NII к +1% ставки: {data['nii_sensitivity']:,.2f} руб.\n\n"
            f"Твой анализ и рекомендация:"
        )

        # Используем _call_llm для получения текстового ответа
        response = self._call_llm("risk_daily", prompt)
        write_report(f"[RiskAgent] Оценка риска: {response}")
        logger.info(f"[RiskAgent] Рекомендация: {response}")
