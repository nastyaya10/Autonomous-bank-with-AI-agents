import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
import random
import math
import csv
import os


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


class RepaymentSchedule(Enum):
    ANNUITY = "annuity"
    DIFFERENTIATED = "differentiated"


@dataclass
class Deal:
    deal_id: str
    type: DealType
    amount: float
    term_months: int
    rate: float
    client_id: str
    credit_score: int
    loan_type: Optional[LoanType] = None
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    maturity_date: Optional[datetime] = None
    effective_rate: float = 0.0
    outstanding_principal: float = 0.0
    schedule_type: RepaymentSchedule = RepaymentSchedule.ANNUITY
    commission_rate: float = 0.0

    def __post_init__(self):
        if self.maturity_date is None:
            self.maturity_date = self.created_at + timedelta(days=self.term_months * 30)
        if self.type == DealType.LOAN:
            self.outstanding_principal = self.amount
            self.effective_rate = calculate_effective_rate(
                principal=self.amount,
                term_months=self.term_months,
                rate=self.rate,
                schedule=self.schedule_type,
                commission_rate=self.commission_rate
            )
        else:
            self.outstanding_principal = self.amount

    def remaining_term_days(self, current_date: datetime) -> int:
        return max(0, (self.maturity_date - current_date).days)

    def is_matured(self, current_date: datetime) -> bool:
        return current_date >= self.maturity_date

    def get_monthly_payment(self) -> float:
        if self.type != DealType.LOAN or self.outstanding_principal <= 0:
            return 0.0
        if self.schedule_type == RepaymentSchedule.ANNUITY:
            monthly_rate = self.rate / 12.0
            if monthly_rate == 0:
                return self.outstanding_principal / self.term_months
            payment = self.outstanding_principal * monthly_rate / (1 - (1 + monthly_rate) ** -self.term_months)
            return payment
        else:
            principal_payment = self.outstanding_principal / self.term_months
            interest = self.outstanding_principal * self.rate / 12.0
            return principal_payment + interest

    def apply_payment(self) -> float:
        if self.outstanding_principal <= 0:
            return 0.0
        payment = self.get_monthly_payment()
        interest = self.outstanding_principal * self.rate / 12.0
        principal_paid = payment - interest
        self.outstanding_principal -= principal_paid
        if self.outstanding_principal < 0:
            self.outstanding_principal = 0.0
        return principal_paid


def calculate_effective_rate(principal: float, term_months: int, rate: float,
                             schedule: RepaymentSchedule, commission_rate: float) -> float:
    monthly_rate = rate / 12.0
    cf0 = principal * (commission_rate - 1.0)
    cashflows = [cf0]
    if schedule == RepaymentSchedule.ANNUITY:
        if monthly_rate > 0:
            payment = principal * monthly_rate / (1 - (1 + monthly_rate) ** -term_months)
        else:
            payment = principal / term_months
        for t in range(1, term_months + 1):
            cashflows.append(payment)
    else:
        principal_payment = principal / term_months
        for t in range(1, term_months + 1):
            interest = (principal - principal_payment * (t - 1)) * monthly_rate
            cashflows.append(principal_payment + interest)
    irr_monthly = 0.01
    for _ in range(100):
        npv = 0.0
        dnpv = 0.0
        for idx, cf in enumerate(cashflows):
            npv += cf / ((1 + irr_monthly) ** idx)
            if idx > 0:
                dnpv -= idx * cf / ((1 + irr_monthly) ** (idx + 1))
        if abs(npv) < 0.01:
            break
        irr_monthly -= npv / dnpv if dnpv != 0 else 0.001
    return (1 + irr_monthly) ** 12 - 1


@dataclass
class Portfolio:
    loans: List[Deal] = field(default_factory=list)
    deposits: List[Deal] = field(default_factory=list)
    prepaid_loans: List[Deal] = field(default_factory=list)
    capital: float = 1_000_000.0
    cb_position: float = 0.0  # >0 – размещено в ЦБ, <0 – заём у ЦБ

    def add_loan(self, deal: Deal):
        self.loans.append(deal)

    def add_deposit(self, deal: Deal):
        self.deposits.append(deal)

    def remove_matured(self, current_date: datetime):
        self.loans = [d for d in self.loans if not d.is_matured(current_date) and d.outstanding_principal > 0]
        self.deposits = [d for d in self.deposits if not d.is_matured(current_date)]

    def apply_prepayments(self, current_date: datetime, base_prob: float = 0.001, rate_factor: float = 0.01):
        remaining_loans = []
        for loan in self.loans:
            effective_rate = loan.rate
            prob = base_prob + rate_factor * (1 - min(effective_rate / 0.35, 1.0))
            if random.random() < prob:
                self.prepaid_loans.append(loan)
                continue
            remaining_loans.append(loan)
        self.loans = remaining_loans

    def total_loans(self) -> float:
        return sum(d.outstanding_principal for d in self.loans)

    def total_deposits(self) -> float:
        return sum(d.amount for d in self.deposits)

    def net_position(self) -> float:
        return self.total_loans() - self.total_deposits()

    def gap_by_remaining_term(self, current_date: datetime) -> Dict[str, float]:
        buckets = {"0-1y": 0.0, "1-3y": 0.0, "3-5y": 0.0, ">5y": 0.0}
        for loan in self.loans:
            rem = loan.remaining_term_days(current_date)
            if rem <= 365:
                buckets["0-1y"] += loan.outstanding_principal
            elif rem <= 3 * 365:
                buckets["1-3y"] += loan.outstanding_principal
            elif rem <= 5 * 365:
                buckets["3-5y"] += loan.outstanding_principal
            else:
                buckets[">5y"] += loan.outstanding_principal
        for dep in self.deposits:
            rem = dep.remaining_term_days(current_date)
            if rem <= 365:
                buckets["0-1y"] -= dep.amount
            elif rem <= 3 * 365:
                buckets["1-3y"] -= dep.amount
            elif rem <= 5 * 365:
                buckets["3-5y"] -= dep.amount
            else:
                buckets[">5y"] -= dep.amount
        return buckets

    def weighted_loan_rate(self, key_rate: float) -> float:
        total = self.total_loans()
        if total == 0:
            return 0
        weighted = 0.0
        for loan in self.loans:
            if loan.loan_type == LoanType.FIXED:
                rate = loan.rate
            else:
                rate = key_rate + loan.rate
            weighted += loan.outstanding_principal * rate
        return weighted / total

    def weighted_deposit_rate(self) -> float:
        total = self.total_deposits()
        if total == 0:
            return 0
        weighted = sum(d.amount * d.rate for d in self.deposits)
        return weighted / total


class RealYieldCurve:
    def __init__(self, filename: str = "ofz_curve.csv"):
        self.terms = []
        self.rates = []
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Файл {filename} не найден.")
        with open(filename, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    term = float(row["term_months"])
                    rate = float(row["rate"])
                    self.terms.append(term)
                    self.rates.append(rate)
                except (ValueError, KeyError):
                    continue
        if len(self.terms) < 2:
            raise ValueError("В файле должно быть минимум две корректные точки")

    def rate(self, term_months: int) -> float:
        if term_months <= self.terms[0]:
            return self.rates[0]
        if term_months >= self.terms[-1]:
            return self.rates[-1]
        for i in range(len(self.terms) - 1):
            t1, t2 = self.terms[i], self.terms[i + 1]
            if t1 <= term_months <= t2:
                r1, r2 = self.rates[i], self.rates[i + 1]
                return r1 + (r2 - r1) * (term_months - t1) / (t2 - t1)
        return self.rates[-1]


class HistoricalYieldCurve:
    def __init__(self, filename: str = "historical_yields.csv"):
        self.curves = {}
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Файл {filename} не найден.")
        with open(filename, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.term_labels = [col for col in reader.fieldnames if col != 'date']
            self.hist_terms_years = [float(col) for col in self.term_labels]
            self.hist_terms_months = [t * 12 for t in self.hist_terms_years]
            for row in reader:
                date_str = row['date']
                rates = []
                for col in self.term_labels:
                    try:
                        val_str = row[col].replace(',', '.')
                        r = float(val_str)
                        rates.append(r / 100.0)
                    except (ValueError, KeyError):
                        rates.append(0.0)
                self.curves[date_str] = (self.hist_terms_months, rates)

    def get_curve(self, date_str: str):
        return self.curves.get(date_str, (None, None))

    def get_deltas(self, base_date: str, stressed_date: str):
        _, base_rates = self.curves[base_date]
        _, stress_rates = self.curves[stressed_date]
        deltas = [stress_rates[i] - base_rates[i] for i in range(len(base_rates))]
        return self.hist_terms_months, deltas


class StressedYieldCurve:
    def __init__(self, base_curve: RealYieldCurve, hist_terms_months, deltas):
        self.base_curve = base_curve
        self.hist_terms_months = hist_terms_months
        self.deltas = deltas

    def _delta_at(self, term_months: int) -> float:
        if term_months <= self.hist_terms_months[0]:
            return self.deltas[0]
        if term_months >= self.hist_terms_months[-1]:
            return self.deltas[-1]
        for i in range(len(self.hist_terms_months) - 1):
            t1, t2 = self.hist_terms_months[i], self.hist_terms_months[i + 1]
            if t1 <= term_months <= t2:
                d1, d2 = self.deltas[i], self.deltas[i + 1]
                return d1 + (d2 - d1) * (term_months - t1) / (t2 - t1)
        return 0.0

    def rate(self, term_months: int) -> float:
        base = self.base_curve.rate(term_months)
        return base + self._delta_at(term_months)


@dataclass
class KeyRate:
    current: float = 0.21

    def set(self, new_rate: float):
        self.current = new_rate


@dataclass
class PnL:
    total_interest_income: float = 0.0
    total_interest_expense: float = 0.0
    total_commission_income: float = 0.0
    cb_interest_income: float = 0.0
    cb_interest_expense: float = 0.0
    net_interest_income: float = 0.0

    def accrue_daily(self, portfolio: Portfolio, key_rate: float, days: int = 1):
        income = 0.0
        expense = 0.0
        for loan in portfolio.loans:
            if loan.loan_type == LoanType.FIXED:
                daily_rate = loan.rate / 365
            else:
                floating_rate = key_rate + loan.rate
                daily_rate = floating_rate / 365
            income += loan.outstanding_principal * daily_rate * days
        for dep in portfolio.deposits:
            daily_rate = dep.rate / 365
            expense += dep.amount * daily_rate * days
        self.total_interest_income += income
        self.total_interest_expense += expense
        self._update_nii()

    def accrue_cb(self, cb_position: float, key_rate: float, days: int = 1):
        if cb_position > 0:
            income = cb_position * (key_rate - 0.01) / 365 * days
            self.cb_interest_income += income
        elif cb_position < 0:
            expense = -cb_position * (key_rate + 0.01) / 365 * days
            self.cb_interest_expense += expense
        self._update_nii()

    def add_commission(self, amount: float):
        self.total_commission_income += amount
        self._update_nii()

    def _update_nii(self):
        self.net_interest_income = (self.total_interest_income +
                                    self.cb_interest_income +
                                    self.total_commission_income -
                                    self.total_interest_expense -
                                    self.cb_interest_expense)


@dataclass
class RiskMetrics:
    nii_sensitivity: float = 0.0
    expected_loss: float = 0.0

    def calculate(self, portfolio: Portfolio, yield_curve):
        gap = portfolio.gap_by_remaining_term(datetime.now())
        avg_years = {"0-1y": 0.5, "1-3y": 2.0, "3-5y": 4.0, ">5y": 7.0}
        self.nii_sensitivity = sum(gap[b] * 0.01 * avg_years[b] for b in gap)
        el = 0.0
        for loan in portfolio.loans:
            pd = self._pd_from_pkr(loan.credit_score)
            lgd = 0.45
            el += pd * lgd * loan.outstanding_principal
        self.expected_loss = el

    @staticmethod
    def _pd_from_pkr(pkr: int) -> float:
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
