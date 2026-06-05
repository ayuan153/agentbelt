"""Read-only dashboard for AGENTBELT_AUDIT_LOG-style JSONL audit logs. Zero infra."""

import json
from collections import Counter
from rich.console import Console
from rich.table import Table

BLOCKED = {"deflect", "throttle", "deny", "partial_deny"}


def load(path: str) -> list[dict]:
    """Read JSONL, tolerant of blank/bad lines (skip them)."""
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue
    return records


def aggregate(records: list[dict]) -> dict:
    """Aggregate audit records into summary stats."""
    by_decision = Counter(r.get("decision", "") for r in records)
    by_principal = Counter(r.get("principal_key", "") for r in records)
    spend: dict[str, float] = {}
    for r in records:
        pk = r.get("principal_key", "")
        cost = r.get("cost_used", 0.0) or 0.0
        spend[pk] = max(spend.get(pk, 0.0), cost)
    blocked = sum(by_decision[d] for d in BLOCKED)
    recent_blocks = [r for r in records if r.get("decision") in BLOCKED][-10:]
    return {
        "total": len(records),
        "by_decision": by_decision,
        "by_principal": by_principal,
        "blocked": blocked,
        "spend_by_principal": spend,
        "recent_blocks": recent_blocks,
    }


def render(path: str, console=None) -> dict:
    """Load+aggregate, print rich tables, return aggregate dict."""
    console = console or Console()
    records = load(path)
    agg = aggregate(records)

    # Summary
    t = Table(title="Agentbelt Audit Summary")
    t.add_column("Metric"); t.add_column("Value")
    t.add_row("Total events", str(agg["total"]))
    t.add_row("Blocked", str(agg["blocked"]))
    console.print(t)

    # By decision
    t2 = Table(title="By Decision")
    t2.add_column("Decision"); t2.add_column("Count")
    for d, c in agg["by_decision"].most_common():
        t2.add_row(d, str(c))
    console.print(t2)

    # Top principals by spend
    t3 = Table(title="Top Principals by Spend")
    t3.add_column("Principal"); t3.add_column("Max Cost")
    for pk, cost in sorted(agg["spend_by_principal"].items(), key=lambda x: -x[1])[:10]:
        t3.add_row(pk, f"{cost:.4f}")
    console.print(t3)

    # Recent blocks
    if agg["recent_blocks"]:
        t4 = Table(title="Recent Blocks")
        t4.add_column("Principal"); t4.add_column("Decision"); t4.add_column("Action")
        for r in agg["recent_blocks"]:
            t4.add_row(r.get("principal_key", ""), r.get("decision", ""), r.get("action", ""))
        console.print(t4)

    return agg
