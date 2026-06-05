"""Tool-sensitivity tier resolver for Agentbelt H3 tool/action mediation.

Implements the precedence defined in docs/configurability.md §3 and ADR-0003:
  1. Operator override (authoritative)
  2. Trusted-server MCP ToolAnnotations (MCP 2025-03-26)
  3. Name heuristic
  4. Default-sensitive ('high')

MCP trusted-server caveat: per the MCP spec, clients MUST treat tool annotations
as untrusted unless they come from a server in the operator's trusted_servers list.
Annotations from untrusted servers are ignored entirely.

MCP ToolAnnotations fields (2025-03-26):
  - readOnlyHint: bool — tool does not modify state (omitted => assumes modifies)
  - destructiveHint: bool — tool may destructively update (omitted => assumes destructive)
  - idempotentHint: bool — repeated calls with same args have no additional effect
  - openWorldHint: bool — tool interacts with external entities
"""

_READ_PREFIXES = ('get_', 'list_', 'read_', 'search_', 'lookup_', 'fetch_')
_WRITE_TOKENS = ('send', 'delete', 'transfer', 'refund', 'reset', 'pay',
                 'grant', 'wire', 'charge', 'disable', 'remove', 'cancel')


def tier_from_annotations(a: dict) -> str:
    """Map MCP ToolAnnotations to a tier with conservative omission defaults."""
    if a.get('readOnlyHint') is True:
        return 'low'
    destructive = a.get('destructiveHint', True)  # omitted => destructive
    if destructive:
        return 'high'
    return 'medium'


def heuristic_tier(name: str) -> str | None:
    """Infer tier from tool name conventions. Returns None if no signal."""
    low = name.lower()
    if low.startswith(_READ_PREFIXES):
        return 'low'
    if any(tok in low for tok in _WRITE_TOKENS):
        return 'high'
    return None


def resolve_tier(name: str, tool_tiers: dict, trusted_servers: list,
                 annotations: dict | None = None, server: str | None = None) -> str:
    """Resolve the sensitivity tier for a tool. Returns 'low'|'medium'|'high'."""
    # 1. Operator override
    if name in tool_tiers:
        return tool_tiers[name]
    # 2. Trusted-server MCP annotations
    if annotations is not None and server in trusted_servers:
        return tier_from_annotations(annotations)
    # 3. Name heuristic
    h = heuristic_tier(name)
    if h is not None:
        return h
    # 4. Default-sensitive
    return 'high'
