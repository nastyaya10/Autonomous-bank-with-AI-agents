from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum
import uuid
from datetime import datetime


class TradeType(str, Enum):
    IRS = "interest_rate_swap"
    BOND = "bond"
    FX_SWAP = "fx_swap"


class TradeProposal(BaseModel):
    """Предложение сделки от трейдера"""
    proposal_id: str = str(uuid.uuid4())[:8]
    trade_type: TradeType
    notional: float  # в миллионах
    currency: str
    counterparty: str
    tenor_years: int
    deal_direction: str  # BUY/SELL
    risk_metrics: Dict[str, float] = {}
    created_at: datetime


class TradeVerdict(BaseModel):
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
