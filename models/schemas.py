from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum
import uuid
from datetime import datetime

class Deal(BaseModel):
    """Предложение сделки от трейдера"""
    proposal_id: str = str(uuid.uuid4())[:8]
    client: str
    notional: float  # в миллионах
    currency: str
    tenor_years: int
    deal_direction: str  # deposit/loan
    pd_annual: float
    created_at: datetime
    interest: float # процент


class DealVerdict(BaseModel):
    """Решение контролирующего агента"""
    agent: str
    proposal_id: str
    decision: str  # APPROVED / REJECTED
    reason: Optional[str] = None
    timestamp: datetime = datetime.now()


class Balance(BaseModel):
    """Капитал"""
    amount: float  # в миллионах
    currency: str
    first_amount: float