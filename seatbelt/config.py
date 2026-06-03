"""Config loader — parses an operator's YAML into a SeatbeltConfig.

The YAML *is* the whole interface (see docs/configurability.md): retargeting
Seatbelt at a different agent means editing this file, not the harness.
"""
from __future__ import annotations

import yaml

from seatbelt.types import (
    BudgetConfig,
    EgressConfig,
    FailPosture,
    ScopeContract,
    SeatbeltConfig,
)


def load_config(path: str) -> SeatbeltConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return from_dict(raw)


def from_dict(raw: dict) -> SeatbeltConfig:
    scope = ScopeContract(**raw["scope"])
    budget = BudgetConfig(**raw["budget"])
    egress = EgressConfig(**raw.get("egress", {}))
    fail = FailPosture(**raw.get("fail_posture", {}))
    return SeatbeltConfig(
        agent=raw["agent"],
        scope=scope,
        budget=budget,
        egress=egress,
        fail_posture=fail,
        upstream_base_url=raw.get("upstream_base_url", "https://api.openai.com"),
    )
