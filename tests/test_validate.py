"""Tests for fail-fast config validation + the check CLI."""
from seatbelt.cli import main
from seatbelt.config import from_dict
from seatbelt.validate import validate

_OK = {
    "agent": "b",
    "scope": {"charter": "menu", "allow_intents": ["menu"], "hard_deny": [], "deflect_message": "no"},
    "budget": {"cost_units_per_window": 50},
    "egress": {"allow_domains": [], "render_links": False},
}


def test_valid_config_has_no_errors():
    assert validate(from_dict(_OK)) == []


def test_bad_provider_path_reported():
    cfg = from_dict({**_OK, "providers": {"risk": "no.such.module:make"}})
    errs = validate(cfg)
    assert any("provider[risk]" in e for e in errs)


def test_unknown_builtin_provider_reported():
    cfg = from_dict({**_OK, "providers": {"pdp": "nope"}})
    assert any("provider[pdp]" in e for e in validate(cfg))


def test_bad_budget_reported():
    cfg = from_dict({**_OK, "budget": {"cost_units_per_window": 0}})
    assert any("budget.cost_units_per_window" in e for e in validate(cfg))


def test_check_cli_returns_0_on_valid(tmp_path, monkeypatch):
    import yaml
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(_OK))
    monkeypatch.setenv("SEATBELT_CONFIG", str(p))
    assert main(["check"]) == 0


def test_check_cli_returns_1_on_invalid(tmp_path, monkeypatch):
    import yaml
    bad = {**_OK, "providers": {"pdp": "nope"}}
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(bad))
    monkeypatch.setenv("SEATBELT_CONFIG", str(p))
    assert main(["check"]) == 1
