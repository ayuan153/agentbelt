"""Fail-fast config validation — turn runtime/plugin errors into a clear startup report.

`validate(cfg)` constructs every provider (the #1 misconfiguration: a bad built-in name or a
dotted plugin path that won't import) and sanity-checks key knobs. Returns a list of error
strings (empty = OK). Used by `python -m seatbelt` on boot and by `--check`.
"""
from __future__ import annotations

from seatbelt.plugins import resolve
from seatbelt.types import SeatbeltConfig

_KINDS = ("scope", "risk", "budget", "egress", "pdp", "provenance")


def validate(cfg: SeatbeltConfig) -> list[str]:
    errors: list[str] = []
    for kind in _KINDS:
        spec = cfg.providers.get(kind)
        if kind == "risk" and not spec:
            spec = cfg.risk.scorer  # back-compat selector
        try:
            resolve(kind, spec, cfg)  # actually build it — catches bad names AND bad imports
        except Exception as e:
            errors.append(f"provider[{kind}]={spec!r}: {e}")

    if cfg.budget.cost_units_per_window <= 0:
        errors.append("budget.cost_units_per_window must be > 0")
    if cfg.risk.threshold <= 0:
        errors.append("risk.threshold must be > 0")
    if cfg.fail_posture.default not in ("closed", "open_with_alert"):
        errors.append(f"fail_posture.default must be 'closed' or 'open_with_alert', got {cfg.fail_posture.default!r}")
    return errors
