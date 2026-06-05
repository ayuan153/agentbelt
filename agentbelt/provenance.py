"""Provenance / Context Firewall (hook H2) — see ADR-0002 + docs/spikes/provenance-model.md.

Tracks the trust of content flowing through the proxy so the capability-downgrade
invariant can be enforced: untrusted content (tool results, retrieved docs) must not be
able to drive a sensitive tool call or egress (defends T3/T5 — EchoLeak/ForcedLeak/Slack).

Trust tiers (lowest first): UNTRUSTED < USER < TRUSTED. Derived from OpenAI message roles
by default; a host app may override per-message with a `_agentbelt_trust` hint (used only
for content it has itself classified — e.g. RAG text embedded in a user turn).

`provenance_max_trust` is the most-trusted tier we can *safely attribute* to this turn's
action justification; it degrades to "untrusted" if ANY untrusted content was newly
introduced this turn. This is an approximation (content-trust accounting, not causal
tracing) — exact provenance needs the optional in-process shim (ADR-0002).
"""
from __future__ import annotations

import hashlib

from agentbelt.types import Session

TrustTier = str  # "trusted" | "user" | "untrusted"
_RANK = {"untrusted": 0, "user": 1, "trusted": 2}
_BY_RANK = {0: "untrusted", 1: "user", 2: "trusted"}


def classify_message(m: dict) -> TrustTier:
    hint = m.get("_agentbelt_trust")
    if hint in _RANK:
        return hint
    role = m.get("role", "")
    if role in ("system", "developer"):
        return "trusted"
    if role == "tool":  # tool/function results are untrusted ingested content
        return "untrusted"
    return "user"  # user + assistant turns


def _hash(m: dict) -> str:
    key = f"{m.get('role','')}\x00{m.get('content') or ''}\x00{m.get('tool_call_id','')}"
    return hashlib.sha256(key.encode()).hexdigest()


class ProvenanceTracker:
    """Computes the turn's provenance_max_trust from content newly introduced this turn."""

    def turn_trust(self, session: Session, messages: list[dict]) -> TrustTier:
        new = [m for m in messages if _hash(m) not in session.seen_hashes]
        for m in messages:
            session.seen_hashes.add(_hash(m))
        if not new:
            return "user"
        # weakest link: degrade to the least-trusted newly-introduced content
        return _BY_RANK[min(_RANK[classify_message(m)] for m in new)]
