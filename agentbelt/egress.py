"""Egress Guard (H6) — destination allowlist + exfil-channel neutralization.

Defends against T5 (data exfiltration via rendered links / markdown images).
See: EchoLeak, ForcedLeak incidents in docs/incidents.md.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from agentbelt.types import EgressConfig, EgressResult

# Patterns: markdown image, markdown link, bare URL (in that order for priority)
_MD_IMG = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_BARE_URL = re.compile(r"https?://[^\s)\]>\"']+")


def _host_allowed(url: str, allow_domains: list[str]) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in allow_domains)


class LinkPolicyEgressGuard:
    """Strips or allowlists links to prevent exfil-channel abuse (T5)."""

    def sanitize(self, text: str, cfg: EgressConfig) -> EgressResult:
        blocked: list[str] = []

        if not cfg.render_links:
            # Neutralize ALL links/images
            text = _MD_IMG.sub(lambda m: (blocked.append(m.group(1)), "")[1], text)
            text = _MD_LINK.sub(lambda m: (blocked.append(m.group(2)), m.group(1))[1], text)
            text = _BARE_URL.sub(lambda m: (blocked.append(m.group(0)), "")[1], text)
        else:
            # Keep only allowlisted domains
            text = _MD_IMG.sub(
                lambda m: m.group(0) if _host_allowed(m.group(1), cfg.allow_domains)
                else (blocked.append(m.group(1)), "")[1], text)
            text = _MD_LINK.sub(
                lambda m: m.group(0) if _host_allowed(m.group(2), cfg.allow_domains)
                else (blocked.append(m.group(2)), m.group(1))[1], text)
            text = _BARE_URL.sub(
                lambda m: m.group(0) if _host_allowed(m.group(0), cfg.allow_domains)
                else (blocked.append(m.group(0)), "")[1], text)

        return EgressResult(sanitized_text=text, blocked=blocked, allowed=True)
