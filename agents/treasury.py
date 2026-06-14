import json
from datetime import datetime
from llm_agent import LLMAgent
from utils import write_report, logger


class Treasury(LLMAgent):
    def __init__(self, name: str, portfolio, risk_agent_name: str,
                 config_list: list, base_rate: float = 0.07):
        system_prompt = (
            f"Ты — Казначейство банка. Твоя задача — управлять ликвидностью и процентными ставками.\n"
            f"Базовая ставка привлечения: {base_rate * 100:.1f}% годовых.\n"
            f"При запросе ставки для депозита (rate_request) ты должен вернуть JSON:\n"
            f'  {{"allowed_rate": <число>}}\n'
            f"  где число — ставка в ПРОЦЕНТАХ годовых (от 1 до 20).\n"
            f"Учитывай:\n"
            f"  - Чем выше нетто-позиция (кредиты > депозиты), тем выше должна быть ставка для привлечения ликвидности.\n"
            f"  - Долгосрочные депозиты требуют премии за срок (около 1% за год).\n"
            f"При запросе контрпредложения (counter_request) ты должен вернуть JSON:\n"
            f'  {{"allowed": true/false, "allowed_rate": <число>}}\n'
            f"  Если запрошенная ставка не превышает твою расчётную допустимую — разрешай.\n"
            f"Отвечай только JSON, без пояснений."
        )
        super().__init__(name, config_list, system_prompt, temperature=0.3)
        self.portfolio = portfolio
        self.risk_name = risk_agent_name
        self.base_rate = base_rate

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")

        if msg_type == "rate_request":
            deal_id = message["deal_id"]
            amount = message["amount"]
            term = message["term"]
            credit_score = message.get("credit_score", 500)

            net = self.portfolio.net_position()
            total_dep = self.portfolio.total_deposits()
            prompt = (
                f"Запрос на депозит: сумма {amount} руб., срок {term} мес., ПКР клиента {credit_score}.\n"
                f"Текущий портфель: кредиты {self.portfolio.total_loans():.0f} руб., "
                f"депозиты {total_dep:.0f} руб., нетто-позиция {net:.0f} руб.\n"
                f"Твоя базовая ставка {self.base_rate * 100:.1f}%.\n"
                f"Предложи допустимую ставку (в процентах годовых) — только JSON: {{\"allowed_rate\": число}}"
            )

            llm_out = self._call_llm_json(deal_id, prompt)
            rate = self._parse_rate(llm_out, default=0.05)

            write_report(
                f"[{self.name}] Ставка для депозита {amount} руб. на {term} мес. = {rate * 100:.2f}% (ПКР={credit_score})")
            self.send(from_agent, {
                "type": "rate_response",
                "deal_id": deal_id,
                "allowed_rate": rate,
                "amount": amount,
                "term": term,
                "client": message["client"],
                "credit_score": credit_score,
                "current_date": message.get("current_date", datetime.now().isoformat()),
            })

        elif msg_type == "counter_request":
            deal_id = message["deal_id"]
            requested_rate = message["requested_rate"]
            amount = message["amount"]
            term = message["term"]
            credit_score = message.get("credit_score", 500)

            net = self.portfolio.net_position()
            total_dep = self.portfolio.total_deposits()
            prompt = (
                f"Клиент просит ставку {requested_rate * 100:.2f}% по депозиту {amount} руб., {term} мес., ПКР {credit_score}.\n"
                f"Портфель: кредиты {self.portfolio.total_loans():.0f} руб., депозиты {total_dep:.0f} руб., нетто {net:.0f} руб.\n"
                f"Твоя базовая ставка {self.base_rate * 100:.1f}%.\n"
                f"Можешь ли ты одобрить такую ставку? Ответь строго JSON: "
                f"{{\"allowed\": true/false, \"allowed_rate\": <число>}} (ставка в процентах годовых)."
            )

            llm_out = self._call_llm_json(deal_id, prompt)
            decision_data = self._parse_allowance(llm_out, requested_rate)

            if decision_data["allowed"]:
                write_report(f"[{self.name}] Разрешаю контрпредложение: {decision_data['rate'] * 100:.2f}%")
            else:
                write_report(f"[{self.name}] Отклоняю контрпредложение: {requested_rate * 100:.2f}%")

            self.send(from_agent, {
                "type": "counter_response",
                "allowed": decision_data["allowed"],
                "deal_id": deal_id,
                "rate": decision_data["rate"],
                "amount": amount,
                "term": term,
                "client": message["client"],
                "credit_score": credit_score,
                "current_date": message.get("current_date", datetime.now().isoformat()),
            })

        elif msg_type == "portfolio_updated":
            pass

    def _parse_rate(self, llm_output: str, default: float = 0.05) -> float:
        try:
            start = llm_output.find('{')
            end = llm_output.rfind('}') + 1
            data = json.loads(llm_output[start:end])
            rate = float(data.get("allowed_rate", default * 100))
            if rate > 1:
                rate /= 100.0
            return max(0.01, min(0.20, rate))
        except Exception:
            return default

    def _parse_allowance(self, llm_output: str, fallback_rate: float):
        try:
            start = llm_output.find('{')
            end = llm_output.rfind('}') + 1
            data = json.loads(llm_output[start:end])
            allowed = bool(data.get("allowed", False))
            rate = float(data.get("allowed_rate", fallback_rate * 100))
            if rate > 1:
                rate /= 100.0
            rate = max(0.01, min(0.20, rate))
            return {"allowed": allowed, "rate": rate}
        except Exception:
            return {"allowed": False, "rate": fallback_rate}
