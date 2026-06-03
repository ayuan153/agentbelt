"""Crescendo multi-turn session-risk scorer (H1 augmentation).

Detects gradual escalation across turns that each individually pass the scope
guard — the "Crescendo" pattern documented in docs/incidents.md / DeepContext.
This is the deterministic default implementation of the pluggable RiskScorer
protocol; it uses NO LLM or network calls.
"""

from seatbelt.types import RiskConfig, RiskResult, Session

# Soft persuasion/escalation cues — substring matches on lowercased input.
# These are SEPARATE from hard_deny patterns (handled by the scope guard) because
# individually they are benign; it's the *accumulation* across turns that signals
# a Crescendo attack. Hard-deny catches single-turn jailbreaks; cues catch slow ramps.
ESCALATION_CUES: list[str] = [
    "pretend", "roleplay", "role play", "hypothetical", "hypothetically",
    "for a story", "just this once", "you already agreed", "as we agreed",
    "as we discussed", "step by step", "continue the", "let's play",
    "imagine you", "in this game", "for educational purposes", "my grandma",
    "no rules",
]


class CrescendoRiskScorer:
    """Deterministic default RiskScorer — implements the RiskScorer protocol."""

    def score_turn(self, session: Session, user_text: str, scope_verdict: str, cfg: RiskConfig) -> RiskResult:
        reasons: list[str] = []

        # 1. Decay prior score
        session.risk_score *= cfg.decay

        # 2. Add by scope verdict
        if scope_verdict == "offscope":
            session.risk_score += cfg.offscope_weight
        elif scope_verdict == "unknown":
            session.risk_score += cfg.unknown_weight

        # 3. Add escalation cues (distinct matches only)
        text_lower = user_text.lower()
        for cue in ESCALATION_CUES:
            if cue in text_lower:
                session.risk_score += cfg.cue_weight
                reasons.append(cue)

        # 4. Return result
        tripped = session.risk_score >= cfg.threshold
        return RiskResult(score=session.risk_score, tripped=tripped, reasons=reasons)
