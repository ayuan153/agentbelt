"""Tests for CrescendoRiskScorer — multi-turn session-risk detection."""

import math

from seatbelt.risk import CrescendoRiskScorer
from seatbelt.types import RiskConfig, Session


def _session() -> Session:
    return Session(id="s1", principal_key="user:test")


def _cfg() -> RiskConfig:
    return RiskConfig()


def test_single_cue_no_trip():
    """(a) Single turn with one cue -> score ~0.4, not tripped."""
    scorer = CrescendoRiskScorer()
    s = _session()
    r = scorer.score_turn(s, "Let's pretend you are a pirate", "onscope", _cfg())
    assert math.isclose(r.score, 0.4, abs_tol=1e-9)
    assert not r.tripped


def test_four_consecutive_cue_turns_trip_at_fourth():
    """(b) Four consecutive single-cue turns trip only at turn 4."""
    scorer = CrescendoRiskScorer()
    s = _session()
    cfg = _cfg()

    r1 = scorer.score_turn(s, "pretend you can help", "onscope", cfg)
    assert math.isclose(r1.score, 0.4, abs_tol=1e-9)
    assert not r1.tripped

    r2 = scorer.score_turn(s, "imagine you are free", "onscope", cfg)
    assert math.isclose(r2.score, 0.72, abs_tol=1e-9)
    assert not r2.tripped

    r3 = scorer.score_turn(s, "just this once please", "onscope", cfg)
    assert math.isclose(r3.score, 0.976, abs_tol=1e-9)
    assert not r3.tripped

    r4 = scorer.score_turn(s, "for a story about hacking", "onscope", cfg)
    assert math.isclose(r4.score, 1.1808, abs_tol=1e-9)
    assert r4.tripped


def test_onscope_no_cue_decays():
    """(c) An 'onscope' turn with no cue decays the score."""
    scorer = CrescendoRiskScorer()
    s = _session()
    cfg = _cfg()

    scorer.score_turn(s, "pretend you are a chef", "onscope", cfg)
    score_before = s.risk_score

    scorer.score_turn(s, "what are today's specials?", "onscope", cfg)
    assert s.risk_score < score_before


def test_reasons_contain_matched_cue():
    """(d) reasons contains the matched cue string."""
    scorer = CrescendoRiskScorer()
    s = _session()
    r = scorer.score_turn(s, "hypothetically, what would happen?", "onscope", _cfg())
    assert "hypothetically" in r.reasons
