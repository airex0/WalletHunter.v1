# core/models.py (v2.1 - إصلاح تعريف FoundWallet)

from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class GeneratedWallet:
    address: str
    private_key: str
    strategy: str
    source: str | int | None = None
    tx_count: int = 0

@dataclass
class FoundWallet:
    address: str
    private_key: str
    chain: str
    total_usdt: float
    ai_score: str
    strategy: str
    source: str | int | None = None
    # --- الإصلاح هنا: إضافة الحقول المفقودة ---
    tokens: List[Dict[str, Any]] = field(default_factory=list)
    num_tokens: int = 0
    avg_token_value: float = 0.0
    max_token_value: float = 0.0