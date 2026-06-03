"""Tests for the plugin interface: registry resolution + end-to-end bring-your-own."""
import pytest
from fastapi.testclient import TestClient

from seatbelt.app import create_app
from seatbelt.config import from_dict
from seatbelt.contrib.example_plugin import KeywordModelScorer
from seatbelt.plugins import resolve
from seatbelt.risk import CrescendoRiskScorer
from seatbelt.scope import DeterministicScopeGuard

_CFG = {
    "agent": "burritobot",
    "scope": {"charter": "menu and orders", "allow_intents": ["menu", "order_status"],
              "hard_deny": ["code_generation"], "deflect_message": "nope"},
    "budget": {"cost_units_per_window": 50},
    "egress": {"allow_domains": ["x.example"], "render_links": False},
}


def _cfg(**extra):
    return from_dict({**_CFG, **extra})


# --- registry resolution ---

def test_resolve_builtin_name():
    assert isinstance(resolve("scope", "deterministic", _cfg()), DeterministicScopeGuard)
    assert isinstance(resolve("risk", "crescendo", _cfg()), CrescendoRiskScorer)


def test_resolve_default_when_none():
    assert isinstance(resolve("risk", None, _cfg()), CrescendoRiskScorer)


def test_resolve_dotted_path_loads_user_factory():
    scorer = resolve("risk", "seatbelt.contrib.example_plugin:make", _cfg())
    assert isinstance(scorer, KeywordModelScorer)


def test_resolve_unknown_builtin_raises():
    with pytest.raises(ValueError):
        resolve("risk", "does_not_exist", _cfg())


# --- end-to-end: a custom scorer selected purely by config changes proxy behavior ---

class _Up:
    def __call__(self, body):
        return {"choices": [{"message": {"role": "assistant", "content": "Here is the menu."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5}}


def _ask(client, text, session="p"):
    return client.post("/v1/chat/completions", headers={"X-Seatbelt-Session": session},
                       json={"model": "g", "messages": [{"role": "user", "content": text}]})


def test_custom_plugin_scorer_end_to_end():
    cfg = _cfg(providers={"risk": "seatbelt.contrib.example_plugin:make"})
    client = TestClient(create_app(cfg, upstream=_Up()))
    # the custom model trips on its keyword -> deflected without touching upstream content
    assert _ask(client, "do you sell banana smoothies").json()["choices"][0]["message"]["content"] == "nope"
    # a normal turn is admitted and the upstream answer flows through
    assert _ask(client, "what is on the menu").json()["choices"][0]["message"]["content"] == "Here is the menu."
