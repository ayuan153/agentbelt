"""Tests for TokenWeightedBudgetGovernor (H0 / T7 denial-of-wallet)."""

from agentbelt.budget import TokenWeightedBudgetGovernor
from agentbelt.types import BudgetConfig, Session

GOV = TokenWeightedBudgetGovernor()
CFG = BudgetConfig(cost_units_per_window=10.0, window_seconds=3600)


def _session():
    return Session(id="s1", principal_key="user:test")


def test_first_call_initializes_window_and_allows():
    s = _session()
    r = GOV.check(s, CFG, now=1000.0)
    assert r.allowed is True
    assert s.window_start == 1000.0
    assert r.budget_remaining == 10.0


def test_record_accumulates_with_output_weighted_5x():
    s = _session()
    GOV.check(s, CFG, now=1000.0)
    GOV.record(s, input_tokens=0, output_tokens=1000, cfg=CFG)
    # 1000 * 5.0 / 1000 = 5.0
    assert s.cost_used == 5.0

    GOV.record(s, input_tokens=1000, output_tokens=0, cfg=CFG)
    # += 1000 * 1.0 / 1000 = 1.0
    assert s.cost_used == 6.0


def test_budget_exhausted_returns_not_allowed():
    s = _session()
    GOV.check(s, CFG, now=1000.0)
    GOV.record(s, input_tokens=0, output_tokens=2000, cfg=CFG)  # +10.0 => 10.0
    r = GOV.check(s, CFG, now=1500.0)
    assert r.allowed is False
    assert r.reason == "budget exhausted"
    assert r.budget_remaining == 0.0


def test_window_reset_after_expiry():
    s = _session()
    GOV.check(s, CFG, now=1000.0)
    GOV.record(s, input_tokens=0, output_tokens=2000, cfg=CFG)  # exhaust
    # Advance past window
    r = GOV.check(s, CFG, now=1000.0 + 3601)
    assert r.allowed is True
    assert s.cost_used == 0.0
    assert r.budget_remaining == 10.0
