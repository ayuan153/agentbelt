"""Tests for the in-process shim (cooperative PEP)."""

from seatbelt.shim import SeatbeltShim


def test_untrusted_denies_medium_tier():
    """(a) Untrusted content taints turn → medium tool denied (capability-downgrade)."""
    shim = SeatbeltShim(tool_tiers={"place_order": "medium"}, trusted_servers=[])
    shim.ingest("untrusted")
    result = shim.guard_tool("place_order")
    assert result.effect == "deny"


def test_begin_turn_resets_taint():
    """(b) After begin_turn(), taint is cleared → medium tool allowed."""
    shim = SeatbeltShim(tool_tiers={"place_order": "medium"}, trusted_servers=[])
    shim.ingest("untrusted")
    shim.begin_turn()
    result = shim.guard_tool("place_order")
    assert result.effect == "allow"


def test_high_tier_requires_verification():
    """(c) High-tier denied without verification, allowed with it."""
    shim = SeatbeltShim(tool_tiers={"issue_refund": "high"}, trusted_servers=[])
    denied = shim.guard_tool("issue_refund")
    assert denied.effect == "deny"
    allowed = shim.guard_tool("issue_refund", user_verified=True, human_confirmed=True)
    assert allowed.effect == "allow"


def test_low_tier_allowed_even_when_tainted():
    """(d) Low-tier tool allowed even after untrusted ingest."""
    shim = SeatbeltShim(tool_tiers={"get_menu": "low"}, trusted_servers=[])
    shim.ingest("untrusted")
    result = shim.guard_tool("get_menu")
    assert result.effect == "allow"
