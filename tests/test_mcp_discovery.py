from agentbelt.mcp_discovery import discover_annotations


def test_discover_annotations_from_trusted_server():
    tools = [
        {"name": "read_db", "annotations": {"readOnlyHint": True}},
        {"name": "wipe", "annotations": {"destructiveHint": True}},
    ]
    fetch = lambda server: tools
    registry = discover_annotations(["https://trusted"], fetch=fetch)
    assert registry["read_db"] == ({"readOnlyHint": True}, "https://trusted")
    assert registry["wipe"] == ({"destructiveHint": True}, "https://trusted")


def test_fetch_error_yields_empty_registry():
    def failing_fetch(server):
        raise RuntimeError("connection refused")

    assert discover_annotations(["https://down"], fetch=failing_fetch) == {}


def test_partial_failure():
    def mixed_fetch(server):
        if server == "https://good":
            return [{"name": "tool_a", "annotations": {"readOnlyHint": True}}]
        raise RuntimeError("boom")

    registry = discover_annotations(["https://bad", "https://good"], fetch=mixed_fetch)
    assert registry == {"tool_a": ({"readOnlyHint": True}, "https://good")}
