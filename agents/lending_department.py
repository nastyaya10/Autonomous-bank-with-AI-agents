import uuid
from datetime import datetime, timedelta
from models import Deal, DealType, LoanType, Decision, Portfolio
from llm_agent import LLMAgent
from utils import write_report


class LendingDepartment(LLMAgent):
    def __init__(self, name: str, portfolio: Portfolio, config_list: list,
                 rate_limit_min: float = 0.10, rate_limit_max: float = 0.25):
        system_prompt = f"""Ты — Выдающее отделение банка. Твоя задача — предлагать кредиты клиентам и реагировать на их контрпредложения.
У тебя есть лимиты: ставка кредита должна быть между {rate_limit_min * 100:.2f}% и {rate_limit_max * 100:.2f}% годовых.
Если клиент предлагает контрставку, ты можешь согласиться (accept), если она в лимитах, иначе откажи (reject).
Отвечай ТОЛЬКО JSON форматом: {{"decision": "accept"/"reject"/"counter", "rate": число (если counter)}}.
Ставку указывай в процентах годовых."""
        super().__init__(name, config_list, system_prompt)
        self.portfolio = portfolio
        self.rate_limit_min = rate_limit_min
        self.rate_limit_max = rate_limit_max

    def propose_loan(self, client_name: str, amount: float, term_months: int,
                     credit_score: int, loan_type: LoanType, current_date: datetime) -> str:
        deal_id = str(uuid.uuid4())
        norm = (credit_score - 1) / 998
        proposed_rate = self.rate_limit_min + (self.rate_limit_max - self.rate_limit_min) * (1 - norm)
        proposed_rate = round(max(self.rate_limit_min, min(self.rate_limit_max, proposed_rate)), 4)
        message = {
            "type": "loan_proposal",
            "deal_id": deal_id,
            "amount": amount,
            "term": term_months,
            "rate": proposed_rate,
            "credit_score": credit_score,
            "loan_type": loan_type.value,
            "current_date": current_date.isoformat(),
        }
        write_report(
            f"[{self.name}] Предлагаю кредит {amount} руб. на {term_months} мес. под {proposed_rate * 100:.2f}% (ПКР={credit_score})")
        self.send(client_name, message)
        return deal_id

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        if msg_type == "client_response":
            deal_id = message["deal_id"]
            decision = message["decision"]
            current_date = datetime.fromisoformat(message.get("current_date", datetime.now().isoformat()))
            if decision == Decision.ACCEPT:
                deal = Deal(
                    deal_id=deal_id,
                    type=DealType.LOAN,
                    amount=message["amount"],
                    term_months=message["term"],
                    rate=message["rate"],
                    client_id=from_agent,
                    credit_score=message.get("credit_score", 500),
                    loan_type=LoanType(message.get("loan_type", "fixed")),
                    status="active",
                    created_at=current_date,
                )
                self.portfolio.add_loan(deal)
                write_report(
                    f"[{self.name}] Кредит {deal_id[:8]} одобрен: {deal.amount} руб. на {deal.term_months} мес. под {deal.rate * 100:.2f}%")
                self.send(from_agent, {"type": "deal_confirmed", "deal_id": deal_id})
            elif decision == Decision.REJECT:
                write_report(f"[{self.name}] Клиент {from_agent} отклонил кредит {deal_id[:8]}")
            elif decision == Decision.COUNTER:
                client_rate = message["counter_rate"]
                if self.rate_limit_min <= client_rate <= self.rate_limit_max:
                    write_report(f"[{self.name}] Принимаем контрпредложение: ставка {client_rate * 100:.2f}%")
                    deal = Deal(
                        deal_id=deal_id,
                        type=DealType.LOAN,
                        amount=message["amount"],
                        term_months=message["term"],
                        rate=client_rate,
                        client_id=from_agent,
                        credit_score=message.get("credit_score", 500),
                        loan_type=LoanType(message.get("loan_type", "fixed")),
                        status="active",
                        created_at=current_date,
                    )
                    self.portfolio.add_loan(deal)
                    self.send(from_agent, {"type": "deal_confirmed", "deal_id": deal_id})
                else:
                    write_report(f"[{self.name}] Отклоняем контрпредложение {client_rate * 100:.2f}% (выход за лимиты)")
                    self.send(from_agent, {"type": "reject_counter", "deal_id": deal_id})
        elif msg_type == "deal_confirmed":
            write_report(f"[{self.name}] Клиент подтвердил сделку {message['deal_id'][:8]}")
