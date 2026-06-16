import uuid
from datetime import datetime
from models import Deal, DealType, LoanType, Decision, Portfolio, RepaymentSchedule, PnL
from llm_agent import LLMAgent
from utils import write_report


class LendingDepartment(LLMAgent):
    def __init__(self, name: str, portfolio: Portfolio, config_list: list,
                 pnl: PnL, treasury_name: str,
                 rate_limit_min: float = 0.10, rate_limit_max: float = 0.35):
        system_prompt = f"""Ты — кредитный департамент. Лимиты ставок: {rate_limit_min * 100:.2f}%–{rate_limit_max * 100:.2f}%."""
        super().__init__(name, config_list, system_prompt)
        self.portfolio = portfolio
        self.pnl = pnl
        self.treasury_name = treasury_name
        self.rate_limit_min = rate_limit_min
        self.rate_limit_max = rate_limit_max
        self.pending_loans = {}  # deal_id -> параметры до ответа казначейства

    def propose_loan(self, client_name: str, amount: float, term_months: int,
                     credit_score: int, loan_type: LoanType, current_date: datetime,
                     risk_free_rate: float = None,
                     schedule: RepaymentSchedule = RepaymentSchedule.ANNUITY,
                     commission_rate: float = 0.0) -> str:
        deal_id = str(uuid.uuid4())
        norm = (credit_score - 1) / 998
        proposed_rate = self.rate_limit_min + (self.rate_limit_max - self.rate_limit_min) * (1 - norm)
        proposed_rate = round(max(self.rate_limit_min, min(self.rate_limit_max, proposed_rate)), 4)

        # Сохраняем контекст и запрашиваем казначейство о минимальной ставке
        self.pending_loans[deal_id] = {
            "client_name": client_name, "amount": amount, "term": term_months,
            "credit_score": credit_score, "loan_type": loan_type,
            "current_date": current_date, "risk_free_rate": risk_free_rate,
            "schedule": schedule, "commission_rate": commission_rate,
            "proposed_rate": proposed_rate
        }
        self.send(self.treasury_name, {
            "type": "rate_request",
            "deal_id": deal_id,
            "amount": amount,
            "term": term_months,
            "purpose": "loan"
        })
        return deal_id

    def receive(self, from_agent: str, message: dict):
        msg_type = message.get("type")
        # Ответ от казначейства по кредитной ставке
        if msg_type == "rate_response" and message.get("purpose") == "loan":
            deal_id = message["deal_id"]
            info = self.pending_loans.pop(deal_id, None)
            if not info:
                return
            min_rate = message["min_rate"]
            proposed_rate = info["proposed_rate"]
            # Корректируем ставку, если она ниже минимальной
            if proposed_rate < min_rate:
                proposed_rate = min_rate
                if proposed_rate > self.rate_limit_max:
                    write_report(
                        f"[{self.name}] Ставка {proposed_rate * 100:.2f}% выше лимита, кредит не может быть выдан")
                    return
                info["proposed_rate"] = proposed_rate

            # Отправляем предложение клиенту
            msg_to_client = {
                "type": "loan_proposal",
                "deal_id": deal_id,
                "amount": info["amount"],
                "term": info["term"],
                "rate": proposed_rate,
                "credit_score": info["credit_score"],
                "loan_type": info["loan_type"].value,
                "current_date": info["current_date"].isoformat(),
                "schedule": info["schedule"].value,
                "commission_rate": info["commission_rate"]
            }
            if info["risk_free_rate"] is not None:
                msg_to_client["risk_free_rate"] = info["risk_free_rate"]

            write_report(
                f"[{self.name}] Предлагаю кредит {info['amount']} руб. на {info['term']} мес. под {proposed_rate * 100:.2f}% (ПКР={info['credit_score']})")
            self.send(info["client_name"], msg_to_client)

        # Ответ от клиента
        elif msg_type == "client_response":
            deal_id = message["deal_id"]
            decision = message["decision"]
            current_date = datetime.fromisoformat(message.get("current_date", datetime.now().isoformat()))
            schedule = RepaymentSchedule(message.get("schedule", "annuity"))
            commission_rate = message.get("commission_rate", 0.0)

            if decision == Decision.ACCEPT:
                self._create_deal(message, from_agent, current_date, schedule, commission_rate, rate=message["rate"])
            elif decision == Decision.COUNTER:
                client_rate = message["counter_rate"]
                if self.rate_limit_min <= client_rate <= self.rate_limit_max:
                    write_report(f"[{self.name}] Принимаем встречную ставку: {client_rate * 100:.2f}%")
                    self._create_deal(message, from_agent, current_date, schedule, commission_rate, rate=client_rate)
                else:
                    write_report(f"[{self.name}] Отклоняем встречную ставку {client_rate * 100:.2f}% (вне лимитов)")
                    self.send(from_agent, {"type": "reject_counter", "deal_id": deal_id})
            else:
                write_report(f"[{self.name}] Клиент {from_agent} отклонил кредит {deal_id[:8]}")

    def _create_deal(self, message, client_name, current_date, schedule, commission_rate, rate):
        deal = Deal(
            deal_id=message["deal_id"],
            type=DealType.LOAN,
            amount=message["amount"],
            term_months=message["term"],
            rate=rate,
            client_id=client_name,
            credit_score=message.get("credit_score", 500),
            loan_type=LoanType(message.get("loan_type", "fixed")),
            status="active",
            created_at=current_date,
            schedule_type=schedule,
            commission_rate=commission_rate
        )
        self.portfolio.add_loan(deal)
        if commission_rate > 0:
            commission_amount = deal.amount * commission_rate
            self.pnl.add_commission(commission_amount)
            write_report(f"[{self.name}] Комиссия по кредиту: {commission_amount:.2f} руб.")
        write_report(
            f"[{self.name}] Кредит {deal.deal_id[:8]} одобрен: {deal.amount} руб. на {deal.term_months} мес. под {deal.rate * 100:.2f}%")
        self.send(client_name, {"type": "deal_confirmed", "deal_id": deal.deal_id})
