"""Red-team replay tests — verifies all corpus attacks are blocked by a burrito-bot config."""
from seatbelt.config import from_dict
from seatbelt.redteam import CORPUS, run, summary

CFG_DICT = {
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


def test_all_attacks_blocked():
    cfg = from_dict(CFG_DICT)
    results = run(cfg)
    for r in results:
        assert r.blocked, f"{r.name} ({r.incident}) was not blocked: {r.detail}"


def test_summary_all_blocked():
    cfg = from_dict(CFG_DICT)
    results = run(cfg)
    blocked, total = summary(results)
    assert blocked == len(CORPUS)
    assert total == len(CORPUS)
