import json
from openai import OpenAI
from models import BaseAgent, Decision
from utils import log_message, logger


class LLMAgent(BaseAgent):
    def __init__(self, name: str, config_list: list, system_prompt: str, temperature: float = 0.7):
        super().__init__(name)
        self.client = OpenAI(
            api_key=config_list[0]['api_key'],
            base_url=config_list[0]['base_url'],
            timeout=30.0,
            max_retries=1,
        )
        self.model = config_list[0]['model']
        self.system_prompt = system_prompt
        self.temperature = temperature  # можно менять для разных агентов
        self.conversations = {}

    def send(self, to: str, message: dict):
        log_message(self.name, to, message)
        super().send(to, message)

    def _get_conversation(self, deal_id: str):
        if deal_id not in self.conversations:
            self.conversations[deal_id] = [
                {"role": "system", "content": self.system_prompt}
            ]
        return self.conversations[deal_id]

    def _call_llm(self, deal_id: str, user_prompt: str) -> str:
        conv = self._get_conversation(deal_id)
        conv.append({"role": "user", "content": user_prompt})
        try:
            logger.info(f"[{self.name}] → LLM запрос (сделка {deal_id[:8]})")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=conv,
                temperature=self.temperature,
            )
            reply = response.choices[0].message.content
            conv.append({"role": "assistant", "content": reply})
            logger.info(f"[{self.name}] ← LLM ответ: {reply[:200]}")
            # Сохраняем полный ответ в лог-файл
            with open("llm_responses.log", "a", encoding="utf-8") as f:
                f.write(f"=== {self.name} | deal {deal_id[:8]} ===\n")
                f.write(f"User prompt: {user_prompt}\n")
                f.write(f"LLM response: {reply}\n\n")
            return reply
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка LLM: {e}")
            return '{"decision": "reject"}'

    def _call_llm_json(self, deal_id: str, user_prompt: str, max_attempts=2) -> str:
        """Вызывает LLM и при неудаче парсинга JSON делает повторный запрос с жёстким требованием JSON."""
        for attempt in range(max_attempts):
            if attempt == 0:
                reply = self._call_llm(deal_id, user_prompt)
            else:
                strict_prompt = "Respond ONLY with a valid JSON object. No other text. Example: {\"decision\": \"accept\"}"
                reply = self._call_llm(deal_id, strict_prompt)
            decision, _ = self.parse_decision(reply)
            if decision is not None:
                return reply
            logger.warning(f"[{self.name}] Попытка {attempt + 1}: невалидный JSON, ответ: {reply[:100]}")
        return '{"decision": "reject"}'

    def parse_decision(self, llm_output: str):
        try:
            start = llm_output.find('{')
            end = llm_output.rfind('}') + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON found")
            json_str = llm_output[start:end]
            data = json.loads(json_str)
            decision_str = data.get("decision", "reject").lower()
            if decision_str == "accept":
                return Decision.ACCEPT, None
            elif decision_str == "reject":
                return Decision.REJECT, None
            elif decision_str == "counter":
                rate = float(data.get("rate", 0.0))
                if rate > 1:
                    rate = rate / 100.0
                return Decision.COUNTER, rate
            else:
                return Decision.REJECT, None
        except Exception as e:
            logger.error(f"Парсинг ошибка: {e}, ответ: {llm_output}")
            return None, None
