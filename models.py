import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta

class DealType(Enum):
    LOAN = "loan"
    DEPOSIT = "deposit"

class LoanType(Enum):
    FIXED = "fixed"
    FLOATING = "floating"

class Decision(Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    COUNTER = "counter"

@dataclass
class Deal:
    deal_id: str
    type: DealType
    amount: float
    term_months: int
    rate: float          # для фиксированной ставки или спред для плавающей
    client_id: str
    credit_score: int
    loan_type: Optional[LoanType] = None
    status: str = "active"  # active, matured
    created_at: datetime = field(default_factory=datetime.now)
    maturity_date: Optional[datetime] = None

    def __post_init__(self):
        if self.maturity_date is None:
            self.maturity_date = self.created_at + timedelta(days=self.term_months * 30)

    def remaining_term_days(self, current_date: datetime) -> int:
        return max(0, (self.maturity_date - current_date).days)

    def is_matured(self, current_date: datetime) -> bool:
        return current_date >= self.maturity_date

@dataclass
class Portfolio:
    loans: List[Deal] = field(default_factory=list)
    deposits: List[Deal] = field(default_factory=list)

    def add_loan(self, deal: Deal):
        self.loans.append(deal)

    def add_deposit(self, deal: Deal):
        self.deposits.append(deal)

    def remove_matured(self, current_date: datetime):
        self.loans = [d for d in self.loans if not d.is_matured(current_date)]
        self.deposits = [d for d in self.deposits if not d.is_matured(current_date)]

    def total_loans(self) -> float:
        return sum(d.amount for d in self.loans)

    def total_deposits(self) -> float:
        return sum(d.amount for d in self.deposits)

    def net_position(self) -> float:
        return self.total_loans() - self.total_deposits()

    def gap_by_remaining_term(self, current_date: datetime) -> Dict[str, float]:
        buckets = {"0-90d": 0.0, "90-180d": 0.0, "180-365d": 0.0, ">365d": 0.0}
        for loan in self.loans:
            rem = loan.remaining_term_days(current_date)
            if rem <= 90: buckets["0-90d"] += loan.amount
            elif rem <= 180: buckets["90-180d"] += loan.amount
            elif rem <= 365: buckets["180-365d"] += loan.amount
            else: buckets[">365d"] += loan.amount
        for dep in self.deposits:
            rem = dep.remaining_term_days(current_date)
            if rem <= 90: buckets["0-90d"] -= dep.amount
            elif rem <= 180: buckets["90-180d"] -= dep.amount
            elif rem <= 365: buckets["180-365d"] -= dep.amount
            else: buckets[">365d"] -= dep.amount
        return buckets

    def weighted_loan_rate(self, yield_curve=None) -> float:
        total = self.total_loans()
        if total == 0:
            return 0
        weighted = 0.0
        for loan in self.loans:
            if loan.loan_type == LoanType.FIXED:
                rate = loan.rate
            else:
                if yield_curve:
                    rate = yield_curve.rate(loan.term_months) + loan.rate
                else:
                    rate = loan.rate
            weighted += loan.amount * rate
        return weighted / total

    def weighted_deposit_rate(self) -> float:
        total = self.total_deposits()
        if total == 0:
            return 0
        weighted = sum(d.amount * d.rate for d in self.deposits)
        return weighted / total

@dataclass
class YieldCurve:
    key_rate: float
    base_spread: float = 0.02
    def rate(self, term_months: int) -> float:
        return self.key_rate + self.base_spread

@dataclass
class PnL:
    total_interest_income: float = 0.0
    total_interest_expense: float = 0.0
    net_interest_income: float = 0.0

    def accrue_daily(self, portfolio: Portfolio, yield_curve: YieldCurve, days: int = 1):
        income = 0.0
        expense = 0.0
        for loan in portfolio.loans:
            if loan.loan_type == LoanType.FIXED:
                daily_rate = loan.rate / 365
            else:
                floating_rate = yield_curve.rate(loan.term_months) + loan.rate
                daily_rate = floating_rate / 365
            income += loan.amount * daily_rate * days
        for dep in portfolio.deposits:
            daily_rate = dep.rate / 365
            expense += dep.amount * daily_rate * days
        self.total_interest_income += income
        self.total_interest_expense += expense
        self.net_interest_income = self.total_interest_income - self.total_interest_expense

@dataclass
class RiskMetrics:
    var_95: float = 0.0
    nii_sensitivity: float = 0.0

    def calculate(self, portfolio: Portfolio, yield_curve: YieldCurve):
        shift = 0.01
        weighted_loan = portfolio.weighted_loan_rate(yield_curve)
        weighted_deposit = portfolio.weighted_deposit_rate()
        nii_original = weighted_loan * portfolio.total_loans() - weighted_deposit * portfolio.total_deposits()
        new_loan_income = (weighted_loan + shift) * portfolio.total_loans()
        new_deposit_expense = (weighted_deposit + shift) * portfolio.total_deposits()
        nii_new = new_loan_income - new_deposit_expense
        self.nii_sensitivity = nii_new - nii_original
        self.var_95 = 0.05 * abs(portfolio.net_position())

@dataclass
class TimeSnapshot:
    date: datetime
    loans: float
    deposits: float
    net: float
    gap: Dict[str, float]
    nii: float
    var: float

class GapHistory:
    def __init__(self):
        self.entries: List[TimeSnapshot] = []

    def record(self, snapshot: TimeSnapshot):
        self.entries.append(snapshot)

class MessageBus:
    def __init__(self):
        self.agents: Dict[str, Any] = {}

    def register(self, agent):
        self.agents[agent.name] = agent
        agent.bus = self

    def send(self, from_agent: str, to_agent: str, message: Dict):
        if to_agent not in self.agents:
            raise ValueError(f"Agent {to_agent} not found")
        self.agents[to_agent].receive(from_agent, message)

class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.bus: Optional[MessageBus] = None

    def receive(self, from_agent: str, message: Dict):
        raise NotImplementedError

    def send(self, to: str, message: Dict):
        self.bus.send(self.name, to, message)