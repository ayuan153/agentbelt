"""Optional in-process Policy Enforcement Point (PEP) from ADR-0002.

This shim is COOPERATIVE: the agent must explicitly call ingest() and guard_tool()
— it provides finer-grained, causal provenance tracking than the gateway's
approximation (which infers trust from the messages array), but it is NOT
automatic taint propagation. The agent reports what it actually consumed.

It shares the SAME Cedar policies as the gateway proxy (via CedarPDP).
"""

from agentbelt.pdp import CedarPDP
from agentbelt.tooltier import resolve_tier
from agentbelt.types import AuthzRequest, Decision


class AgentbeltShim:
    """Cooperative in-process PEP for causal provenance-aware tool mediation."""

    def __init__(self, tool_tiers: dict, trusted_servers: list):
        self._pdp = CedarPDP()
        self._tool_tiers = tool_tiers
        self._trusted_servers = trusted_servers
        self._tainted = False

    def begin_turn(self) -> None:
        """Reset per-turn taint state."""
        self._tainted = False

    def ingest(self, trust: str) -> None:
        """Agent reports trust of consumed content. Any 'untrusted' taints the turn."""
        if trust == "untrusted":
            self._tainted = True

    def guard_tool(self, name: str, *, annotations: dict | None = None,
                   server: str | None = None, user_verified: bool = False,
                   human_confirmed: bool = False) -> Decision:
        """Evaluate whether a tool invocation should be allowed."""
        tier = resolve_tier(name, self._tool_tiers, self._trusted_servers, annotations, server)
        provenance_max_trust = "untrusted" if self._tainted else "user"
        req = AuthzRequest(
            principal_id="in-process",
            action="InvokeTool",
            resource_type="Agentbelt::Tool",
            resource_id=name,
            context={
                "provenance_max_trust": provenance_max_trust,
                "tier": tier,
                "user_verified": user_verified,
                "human_confirmed": human_confirmed,
            },
        )
        return self._pdp.decide(req)
