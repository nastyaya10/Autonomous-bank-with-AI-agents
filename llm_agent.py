import json
import time
from openai import OpenAI, APIError, APITimeoutError, APIConnectionError
from models import BaseAgent, Decision


class LLMAgent(BaseAgent):
    def __init__(self, name: str, config_list: list, system_prompt: str):
        super().__init__(name)
        self.client = OpenAI(
            api_key=config_list[0]['api_key'],
            base_url=config_list[0]['base_url'],
            timeout=30.0,  # таймаут на соединение и чтение
            max_retries=1,  # не ретраить слишком долго
        )
        self.model = config_list[0]['model']
        self.system_prompt = system_prompt
        self.conversations = {}

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
            print(f"[{self.name}] → отправляю запрос к LLM (сделка {deal_id[:8]}...)")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=conv,
                temperature=0.7,
                timeout=30,
            )
            reply = response.choices[0].message.content
            conv.append({"role": "assistant", "content": reply})
            print(f"[{self.name}] ← получен ответ от LLM")
            return reply
        except APITimeoutError:
            print(f"[{self.name}] ❌ Таймаут API (30 сек). Возвращаю отказ.")
            return '{"decision": "reject"}'
        except APIConnectionError as e:
            print(f"[{self.name}] ❌ Ошибка соединения: {e}. Возвращаю отказ.")
            return '{"decision": "reject"}'
        except APIError as e:
            print(f"[{self.name}] ❌ Ошибка API: {e}. Возвращаю отказ.")
            return '{"decision": "reject"}'
        except Exception as e:
            print(f"[{self.name}] ❌ Неизвестная ошибка: {e}. Возвращаю отказ.")
            return '{"decision": "reject"}'

    def parse_decision(self, llm_output: str) -> tuple[Decision, float | None]:
        try:
            start = llm_output.find('{')
            end = llm_output.rfind('}') + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON found")
            data = json.loads(llm_output[start:end])
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
            print(f"[{self.name}] Ошибка парсинга JSON: {e}\nОтвет: {llm_output}")
            return Decision.REJECT, None
