import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
import math


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
    rate: float  # для fixed – ставка, для floating – спред над ключевой ставкой
    client_id: str
    credit_score: int
    loan_type: Optional[LoanType] = None
    status: str = "active"
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
            if rem <= 90:
                buckets["0-90d"] += loan.amount
            elif rem <= 180:
                buckets["90-180d"] += loan.amount
            elif rem <= 365:
                buckets["180-365d"] += loan.amount
            else:
                buckets[">365d"] += loan.amount
        for dep in self.deposits:
            rem = dep.remaining_term_days(current_date)
            if rem <= 90:
                buckets["0-90d"] -= dep.amount
            elif rem <= 180:
                buckets["90-180d"] -= dep.amount
            elif rem <= 365:
                buckets["180-365d"] -= dep.amount
            else:
                buckets[">365d"] -= dep.amount
        return buckets

    def weighted_loan_rate(self, key_rate: float, yield_curve) -> float:
        total = self.total_loans()
        if total == 0:
            return 0
        weighted = 0.0
        for loan in self.loans:
            if loan.loan_type == LoanType.FIXED:
                rate = loan.rate
            else:
                rate = key_rate + loan.rate  # плавающая = ключевая + спред
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
    term_premium: float = 0.01  # годовая премия за каждый год срока (1%)

    def rate(self, term_months: int) -> float:
        """Безрисковая ставка на заданный срок (десятичная дробь)"""
        years = term_months / 12.0
        return self.key_rate + self.term_premium * years + self.base_spread


@dataclass
class KeyRate:
    current: float = 0.21  # текущая ключевая ставка

    def set(self, new_rate: float):
        self.current = new_rate


@dataclass
class PnL:
    total_interest_income: float = 0.0
    total_interest_expense: float = 0.0
    net_interest_income: float = 0.0

    def accrue_daily(self, portfolio: Portfolio, key_rate: float, yield_curve, days: int = 1):
        income = 0.0
        expense = 0.0
        for loan in portfolio.loans:
            if loan.loan_type == LoanType.FIXED:
                daily_rate = loan.rate / 365
            else:
                floating_rate = key_rate + loan.rate  # плавающая = ключевая + спред
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
    expected_loss: float = 0.0

    def calculate(self, portfolio: Portfolio, key_rate: float, yield_curve: YieldCurve):
        # Чувствительность NII через GAP: ΔNII = Σ (GAP_i * 0.01 * средний_срок_в_годах)
        gap = portfolio.gap_by_remaining_term(datetime.now())
        avg_years = {"0-90d": 45 / 365, "90-180d": 135 / 365, "180-365d": 272 / 365, ">365d": 2.0}
        self.nii_sensitivity = sum(gap[b] * 0.01 * avg_years[b] for b in gap)

        # VaR (упрощённый параметрический, 95%) = 1.65 * σ_rate * |NII_sensitivity| / 0.01
        # σ_rate годовая ~ 2%
        sigma_rate = 0.02
        self.var_95 = 1.65 * sigma_rate * abs(self.nii_sensitivity) / 0.01

        # Кредитный риск: ожидаемые потери EL = Σ (PD * LGD * amount)
        el = 0.0
        for loan in portfolio.loans:
            pd = self._pd_from_pkr(loan.credit_score)
            lgd = 0.45
            el += pd * lgd * loan.amount
        self.expected_loss = el

    @staticmethod
    def _pd_from_pkr(pkr: int) -> float:
        """Маппинг ПКР в вероятность дефолта (PD) – примерная шкала"""
        if pkr >= 900:
            return 0.001
        elif pkr >= 700:
            return 0.005
        elif pkr >= 500:
            return 0.02
        elif pkr >= 300:
            return 0.08
        else:
            return 0.15


@dataclass
class TimeSnapshot:
    date: datetime
    loans: float
    deposits: float
    net: float
    gap: Dict[str, float]
    nii: float
    var: float
    expected_loss: float = 0.0


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
