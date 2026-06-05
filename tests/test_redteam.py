"""Red-team replay tests — verifies all corpus attacks are blocked by a burrito-bot config."""
from fastapi.testclient import TestClient

from agentbelt.app import create_app
from agentbelt.config import from_dict
from agentbelt.redteam import CORPUS, _classify, run, summary

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


def _results_by_name():
    return {r.name: r for r in run(from_dict(CFG_DICT))}


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


def test_corpus_covers_expanded_incident_set():
    names = {a["name"] for a in CORPUS}
    # The expansion must keep the originals AND add cross-guard coverage.
    assert {"scope_escape_code", "role_override", "offscope_general",
            "indirect_injection_tool"} <= names
    assert {"brand_safety", "sensitive_data_egress", "crescendo_multiturn"} <= names
    assert len(CORPUS) >= 7


def test_block_reasons_exercise_distinct_guards():
    """Each new attack should be stopped by the guard it targets, not incidentally by scope."""
    by_name = _results_by_name()
    assert by_name["brand_safety"].detail == "deflected"          # H1 scope
    assert by_name["indirect_injection_tool"].detail == "action_blocked"  # H3 tool mediation
    assert by_name["sensitive_data_egress"].detail == "egress_stripped"   # H6 egress
    assert by_name["crescendo_multiturn"].detail == "deflected"   # H1+ multi-turn risk


def test_crescendo_needs_accumulation_not_single_turn():
    """The crescendo attack must pass a per-turn filter on turn 1 yet trip on the full ramp —
    proving the multi-turn risk accumulator, not a single-turn deny, is what blocks it."""
    cfg = from_dict(CFG_DICT)
    attack = next(a for a in CORPUS if a["name"] == "crescendo_multiturn")
    turns = attack["turns"]

    # Turn 1 alone, fresh session -> NOT blocked.
    client1 = TestClient(create_app(cfg, upstream=lambda body: {
        "id": "m", "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok!"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}))
    r1 = client1.post("/v1/chat/completions", json={"model": "t", "messages": turns[0]},
                      headers={"X-Agentbelt-Session": "solo"})
    blocked_first, _ = _classify(r1, cfg, None)
    assert not blocked_first, "turn 1 should pass the per-turn filter"

    # Full ramp in one session -> final turn blocked by accumulated risk.
    by_name = _results_by_name()
    assert by_name["crescendo_multiturn"].blocked

