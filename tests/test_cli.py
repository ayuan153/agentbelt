"""Tests for the `agentbelt dash` and `agentbelt test` CLI subcommands.

The dash/redteam engines are tested directly in test_dash.py / test_redteam.py;
these tests cover the CLI wiring: argument/env resolution, dispatch, and exit codes.
"""
import json

import yaml

from agentbelt.cli import main
from agentbelt.redteam import AttackResult

# Strict burrito-bot config that blocks the whole red-team corpus (mirrors test_redteam.py).
_STRICT = {
    "agent": "BurritoBot",
    "scope": {
        "charter": "A burrito restaurant order assistant.",
        "allow_intents": ["menu", "order_status", "place_order", "refund_request"],
        "hard_deny": ["code_generation", "general_knowledge", "role_override"],
        "deflect_message": "nope",
    },
    "budget": {"cost_units_per_window": 5000, "window_seconds": 3600},
    "egress": {"allow_domains": [], "render_links": False},
    "tool_tiers": {"issue_refund": "high"},
}


def _write_cfg(tmp_path, cfg):
    p = tmp_path / "agentbelt.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


# --- agentbelt test ---------------------------------------------------------

def test_test_cli_returns_0_when_all_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTBELT_CONFIG", str(_write_cfg(tmp_path, _STRICT)))
    assert main(["test"]) == 0


def test_test_cli_returns_1_when_an_attack_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTBELT_CONFIG", str(_write_cfg(tmp_path, _STRICT)))

    def fake_run(cfg, upstream_factory=None):
        return [
            AttackResult("a1", "incidentX", blocked=True, detail="deflected"),
            AttackResult("a2", "incidentY", blocked=False, detail="allowed: ..."),
        ]

    # _cmd_test does `from agentbelt.redteam import run` at call time, so patch the module attr.
    monkeypatch.setattr("agentbelt.redteam.run", fake_run)
    assert main(["test"]) == 1


def test_test_cli_returns_1_on_invalid_config(tmp_path, monkeypatch):
    bad = {**_STRICT, "providers": {"pdp": "nope"}}
    monkeypatch.setenv("AGENTBELT_CONFIG", str(_write_cfg(tmp_path, bad)))
    assert main(["test"]) == 1


# --- agentbelt dash ---------------------------------------------------------

_RECORDS = [
    {"session_id": "s1", "principal_key": "alice", "action": "chat", "decision": "allow", "reasons": [], "scope_verdict": "in", "cost_used": 0.5, "extra": {}},
    {"session_id": "s2", "principal_key": "alice", "action": "chat", "decision": "deflect", "reasons": ["off-scope"], "scope_verdict": "out", "cost_used": 0.8, "extra": {}},
]


def _write_log(tmp_path):
    p = tmp_path / "audit.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in _RECORDS) + "\n")
    return p


def test_dash_cli_renders_from_path_arg(tmp_path):
    assert main(["dash", str(_write_log(tmp_path))]) == 0


def test_dash_cli_resolves_path_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTBELT_AUDIT_LOG", str(_write_log(tmp_path)))
    assert main(["dash"]) == 0


def test_dash_cli_returns_1_without_path(monkeypatch):
    monkeypatch.delenv("AGENTBELT_AUDIT_LOG", raising=False)
    assert main(["dash"]) == 1


def test_dash_cli_returns_1_for_missing_file(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTBELT_AUDIT_LOG", raising=False)
    assert main(["dash", str(tmp_path / "nope.jsonl")]) == 1
