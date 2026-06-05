"""MCP server-manifest annotation discovery.

Only call discover_annotations on operator-TRUSTED servers. The tier resolver
still re-checks trust independently. MCP transport is Streamable HTTP, so
discovery is a normal HTTP POST (JSON-RPC tools/list).
"""

import httpx


def _default_fetch(server_url: str) -> list[dict]:
    """Fetch tools from an MCP server via Streamable HTTP. Returns [] on any error."""
    try:
        resp = httpx.post(
            server_url,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            timeout=10,
        )
        return resp.json()["result"]["tools"]
    except Exception:
        return []


def discover_annotations(servers: list[str], fetch=None) -> dict:
    """Return {tool_name: (annotations_dict, server_url)} discovered from the given (trusted)
    MCP servers. ``fetch(server_url) -> list[dict]`` returns that server's tools (each a dict
    with at least "name" and optional "annotations"); injectable for testing. The default does
    an MCP tools/list JSON-RPC POST over HTTP.

    Only call on operator-TRUSTED servers (the resolver still re-checks trust);
    MCP transport is Streamable HTTP (so this is a normal HTTP call).
    """
    if fetch is None:
        fetch = _default_fetch
    registry: dict = {}
    for server in servers:
        try:
            tools = fetch(server)
        except Exception:
            continue
        for tool in tools:
            registry[tool["name"]] = (tool.get("annotations"), server)
    return registry
