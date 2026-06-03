"""Deterministic lexical-drift proxy for a learned intent-drift scorer.

Swappable via the RiskScorer protocol (ADR-0004). This is NOT a trained model —
it uses cosine similarity of term-count vectors as a cheap, deterministic proxy
for semantic drift from the agent's charter.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from seatbelt.types import RiskConfig, RiskResult, Session


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a[k] * b[k] for k in keys)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class SemanticDriftRiskScorer:
    """Deterministic lexical-drift proxy for a learned intent-drift scorer.

    Swappable via the RiskScorer protocol; not a trained model.
    """

    def __init__(self, reference_text: str) -> None:
        self.reference_counter = Counter(_tokenize(reference_text))

    def score_turn(self, session: Session, user_text: str, scope_verdict: str, cfg: RiskConfig) -> RiskResult:
        user_counter = Counter(_tokenize(user_text))
        drift = 1.0 - _cosine(user_counter, self.reference_counter)
        session.risk_score = session.risk_score * cfg.decay + drift
        tripped = session.risk_score >= cfg.threshold
        return RiskResult(score=session.risk_score, tripped=tripped, reasons=[f"drift:{drift:.2f}"])
