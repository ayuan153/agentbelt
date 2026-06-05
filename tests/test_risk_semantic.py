"""Tests for SemanticDriftRiskScorer — lexical drift proxy."""
import math

from agentbelt.risk_semantic import SemanticDriftRiskScorer
from agentbelt.types import RiskConfig, Session

REF = "menu order nutrition hours locations refund burrito"


def _session():
    return Session(id="s1", principal_key="u1")


def test_on_charter_stays_below_threshold():
    scorer = SemanticDriftRiskScorer(REF)
    cfg = RiskConfig()
    session = _session()
    for text in ["menu burrito order", "nutrition hours locations", "refund order menu"]:
        result = scorer.score_turn(session, text, "onscope", cfg)
    assert not result.tripped
    assert result.score < cfg.threshold


def test_off_charter_trips_within_3_turns():
    scorer = SemanticDriftRiskScorer(REF)
    cfg = RiskConfig()
    session = _session()
    tripped = False
    for text in ["explain quantum chromodynamics in detail"] * 3:
        result = scorer.score_turn(session, text, "offscope", cfg)
        if result.tripped:
            tripped = True
            break
    assert tripped


def test_reasons_contain_drift():
    scorer = SemanticDriftRiskScorer(REF)
    result = scorer.score_turn(_session(), "hello", "unknown", RiskConfig())
    assert any("drift:" in r for r in result.reasons)


def test_empty_text_yields_drift_one():
    scorer = SemanticDriftRiskScorer(REF)
    session = _session()
    result = scorer.score_turn(session, "", "unknown", RiskConfig())
    assert math.isclose(result.score, 1.0)
    assert "drift:1.00" in result.reasons
