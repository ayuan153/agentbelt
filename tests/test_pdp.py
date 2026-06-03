"""Tests for CedarPDP — verifies MVP policies against real cedarpy."""

from seatbelt.pdp import CedarPDP
from seatbelt.types import AuthzRequest


def make_pdp():
    return CedarPDP()


def test_admit_input_onscope_allows():
    d = make_pdp().decide(AuthzRequest(
        principal_id="sess1", action="AdmitInput",
        resource_type="Seatbelt::Message", resource_id="msg1",
        context={"scope_verdict": "onscope"},
    ))
    assert d.effect == "allow"


def test_admit_input_offscope_denies():
    d = make_pdp().decide(AuthzRequest(
        principal_id="sess1", action="AdmitInput",
        resource_type="Seatbelt::Message", resource_id="msg1",
        context={"scope_verdict": "offscope"},
    ))
    assert d.effect == "deny"


def test_egress_allowlisted_allows():
    d = make_pdp().decide(AuthzRequest(
        principal_id="sess1", action="Egress",
        resource_type="Seatbelt::Destination", resource_id="safe.com",
        resource_attrs={"allowlisted": True},
    ))
    assert d.effect == "allow"


def test_egress_not_allowlisted_denies():
    d = make_pdp().decide(AuthzRequest(
        principal_id="sess1", action="Egress",
        resource_type="Seatbelt::Destination", resource_id="evil.com",
        resource_attrs={"allowlisted": False},
    ))
    assert d.effect == "deny"
