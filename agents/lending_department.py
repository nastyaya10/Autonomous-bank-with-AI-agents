import uuid
from datetime import datetime
from models import Deal, DealType, LoanType, Decision, Portfolio, RepaymentSchedule, PnL
from llm_agent import LLMAgent
from utils import write_report


class LendingDepartment(LLMAgent):
    def __init__(self, name: str, portfolio: Portfolio, config_list: list,
                 pnl: PnL, treasury_name: str):
        system_prompt = """Ты — кредитный департамент. Предлагаешь ставку, зависящую от безрисковой кривой и ПКР."""
        super().__init__(name, config_list, system_prompt)
        self.portfolio = portfolio
        self.pnl = pnl
        self.treasury_name = treasury_name
        self.pending_loans = {}

    def propose_loan(self, client_name: str, amount: float, term_months: int,
                     credit_score: int, loan_type: LoanType, current_date: datetime,
                     risk_free_rate: float,
                     schedule: RepaymentSchedule = RepaymentSchedule.ANNUITY,
                     commission_rate: float = 0.0) -> str:
        deal_id = str(uuid.uuid4())

        norm = (credit_score - 1) / 998
        credit_spread = 0.05 - 0.02 * norm  # 5% для низкого ПКР, 3% для высокого
        proposed_rate = risk_free_rate + credit_spread
        proposed_rate = min(proposed_rate, 0.50)

        self.pending_loans[deal_id] = {
            "client_name": client_name, "amount": amount, "term": term_months,
            "credit_score": credit_score, "loan_type": loan_type,
            "current_date": current_date, "risk_free_rate": risk_free_rate,
            "schedule": schedule, "commission_rate": commission_rate,
            "proposed_rate": proposed_rate,
            "min_rate": None  # будет заполнен после ответа казначейства
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
        if msg_type == "rate_response" and message.get("purpose") == "loan":
            deal_id = message["deal_id"]
            info = self.pending_loans.get(deal_id)
            if not info:
                return
            info["min_rate"] = message["min_rate"]
            proposed_rate = max(info["proposed_rate"], info["min_rate"])

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
                "commission_rate": info["commission_rate"],
                "risk_free_rate": info["risk_free_rate"]
            }

            write_report(
                f"[{self.name}] Предлагаю кредит {info['amount']} руб. на {info['term']} мес. под {proposed_rate * 100:.2f}% (ПКР={info['credit_score']}, ОФЗ={info['risk_free_rate'] * 100:.2f}%)")
            self.send(info["client_name"], msg_to_client)

        elif msg_type == "client_response":
            deal_id = message["deal_id"]
            # Ищем информацию в pending_loans (может быть ещё там, если не удалена)
            # Удаляем, если найдём, но сначала сохраним min_rate
            info = self.pending_loans.pop(deal_id, None)
            decision = message["decision"]
            current_date = datetime.fromisoformat(message.get("current_date", datetime.now().isoformat()))
            schedule = RepaymentSchedule(message.get("schedule", "annuity"))
            commission_rate = message.get("commission_rate", 0.0)

            if decision == Decision.ACCEPT:
                self._create_deal(message, from_agent, current_date, schedule, commission_rate, rate=message["rate"])
            elif decision == Decision.COUNTER:
                client_rate = message["counter_rate"]
                # Проверяем минимальную ставку от Treasury
                min_rate = info["min_rate"] if info else 0.0
                if client_rate >= min_rate:
                    write_report(f"[{self.name}] Принимаем встречную ставку: {client_rate * 100:.2f}%")
                    self._create_deal(message, from_agent, current_date, schedule, commission_rate, rate=client_rate)
                else:
                    write_report(
                        f"[{self.name}] Отклоняем встречную ставку {client_rate * 100:.2f}% (ниже минимальной {min_rate * 100:.2f}%)")
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
