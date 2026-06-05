"""Tests for CedarPDP — verifies MVP policies against real cedarpy."""

from agentbelt.pdp import CedarPDP
from agentbelt.types import AuthzRequest


def make_pdp():
    return CedarPDP()


def test_admit_input_onscope_allows():
    d = make_pdp().decide(AuthzRequest(
        principal_id="sess1", action="AdmitInput",
        resource_type="Agentbelt::Message", resource_id="msg1",
        context={"scope_verdict": "onscope"},
    ))
    assert d.effect == "allow"


def test_admit_input_offscope_denies():
    d = make_pdp().decide(AuthzRequest(
        principal_id="sess1", action="AdmitInput",
        resource_type="Agentbelt::Message", resource_id="msg1",
        context={"scope_verdict": "offscope"},
    ))
    assert d.effect == "deny"


def test_egress_allowlisted_allows():
    d = make_pdp().decide(AuthzRequest(
        principal_id="sess1", action="Egress",
        resource_type="Agentbelt::Destination", resource_id="safe.com",
        resource_attrs={"allowlisted": True},
    ))
    assert d.effect == "allow"


def test_egress_not_allowlisted_denies():
    d = make_pdp().decide(AuthzRequest(
        principal_id="sess1", action="Egress",
        resource_type="Agentbelt::Destination", resource_id="evil.com",
        resource_attrs={"allowlisted": False},
    ))
    assert d.effect == "deny"


def _invoke(tier, provenance="user", user_verified=False, human_confirmed=False):
    return CedarPDP().decide(AuthzRequest(
        principal_id="sess1", action="InvokeTool",
        resource_type="Agentbelt::Tool", resource_id="some_tool",
        context={"tier": tier, "provenance_max_trust": provenance,
                 "user_verified": user_verified, "human_confirmed": human_confirmed},
    ))


def test_invoke_low_tier_allowed_even_when_untrusted():
    # untrusted content may trigger read-only tools (reading more data is harmless)
    assert _invoke("low", provenance="untrusted").effect == "allow"


def test_invoke_medium_tier_blocked_when_untrusted():
    # capability-downgrade: untrusted content cannot drive a state-changing tool (T3)
    assert _invoke("medium", provenance="untrusted").effect == "deny"


def test_invoke_high_tier_requires_verification():
    # confused-deputy (T4): high-impact action needs verified user + confirmation
    assert _invoke("high", provenance="user").effect == "deny"
    assert _invoke("high", provenance="user", user_verified=True, human_confirmed=True).effect == "allow"


def test_invoke_user_provenance_medium_allowed():
    # a normal user-initiated medium tool call is fine
    assert _invoke("medium", provenance="user").effect == "allow"
