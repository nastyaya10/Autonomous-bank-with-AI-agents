import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class DealType(Enum):
    LOAN = "loan"
    DEPOSIT = "deposit"


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
    rate: float
    client_id: str
    status: str = "proposed"


@dataclass
class Portfolio:
    loans: List[Deal] = field(default_factory=list)
    deposits: List[Deal] = field(default_factory=list)

    def add_loan(self, deal: Deal):
        self.loans.append(deal)

    def add_deposit(self, deal: Deal):
        self.deposits.append(deal)

    def total_loans(self) -> float:
        return sum(d.amount for d in self.loans)

    def total_deposits(self) -> float:
        return sum(d.amount for d in self.deposits)

    def net_position(self) -> float:
        return self.total_loans() - self.total_deposits()

    def gap_by_term(self) -> Dict[str, float]:
        buckets = {"0-3m": 0.0, "3-6m": 0.0, "6-12m": 0.0, ">12m": 0.0}
        for loan in self.loans:
            term = loan.term_months
            if term <= 3:
                buckets["0-3m"] += loan.amount
            elif term <= 6:
                buckets["3-6m"] += loan.amount
            elif term <= 12:
                buckets["6-12m"] += loan.amount
            else:
                buckets[">12m"] += loan.amount
        for dep in self.deposits:
            term = dep.term_months
            if term <= 3:
                buckets["0-3m"] -= dep.amount
            elif term <= 6:
                buckets["3-6m"] -= dep.amount
            elif term <= 12:
                buckets["6-12m"] -= dep.amount
            else:
                buckets[">12m"] -= dep.amount
        return buckets


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
