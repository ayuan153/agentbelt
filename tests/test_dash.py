import json, tempfile, os
from seatbelt.dash import load, aggregate, render

RECORDS = [
    {"session_id": "s1", "principal_key": "alice", "action": "chat", "decision": "allow", "reasons": [], "scope_verdict": "in", "cost_used": 0.5, "extra": {}},
    {"session_id": "s2", "principal_key": "alice", "action": "chat", "decision": "deflect", "reasons": ["off-scope"], "scope_verdict": "out", "cost_used": 0.8, "extra": {}},
    {"session_id": "s3", "principal_key": "bob", "action": "tool", "decision": "throttle", "reasons": ["budget"], "scope_verdict": "in", "cost_used": 1.2, "extra": {}},
    {"session_id": "s4", "principal_key": "bob", "action": "chat", "decision": "allow", "reasons": [], "scope_verdict": "in", "cost_used": 0.3, "extra": {}},
]


def _write_jsonl(records, include_bad=False):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for r in records:
        f.write(json.dumps(r) + "\n")
    if include_bad:
        f.write("not json\n")
        f.write("\n")
    f.close()
    return f.name


def test_load_skips_bad_lines():
    path = _write_jsonl(RECORDS, include_bad=True)
    try:
        result = load(path)
        assert len(result) == 4
    finally:
        os.unlink(path)


def test_aggregate():
    agg = aggregate(RECORDS)
    assert agg["total"] == 4
    assert agg["blocked"] == 2
    assert agg["by_decision"]["allow"] == 2
    assert agg["by_decision"]["deflect"] == 1
    assert agg["by_decision"]["throttle"] == 1
    assert agg["spend_by_principal"]["alice"] == 0.8
    assert agg["spend_by_principal"]["bob"] == 1.2
    assert len(agg["recent_blocks"]) == 2


def test_render_smoke():
    path = _write_jsonl(RECORDS)
    try:
        from rich.console import Console
        agg = render(path, console=Console(file=open(os.devnull, "w")))
        assert agg["total"] == 4
        assert agg["blocked"] == 2
    finally:
        os.unlink(path)
