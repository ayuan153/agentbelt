"""Plugin registry + resolver — the ergonomic "bring your own component" surface.

Every guard is built through a **provider**: a `factory(cfg) -> instance`. A provider is selected
in config (`providers:` section) by either:
  - a built-in name (e.g. `"semantic"`), or
  - a dotted import path to your own factory, e.g. `"yourpkg.module:make_scorer"`.

The factory receives the whole `AgentbeltConfig`, so a custom implementation has everything it needs
(charter, params, tool tiers, …). The thing it returns must satisfy the matching Protocol in
`agentbelt/types.py` (ScopeGuard / RiskScorer / BudgetGovernor / EgressGuard / PolicyDecisionPoint).

No model training here — this is the plug-in seam for power users who bring their own.
"""
from __future__ import annotations

from importlib import import_module
from typing import Callable

from agentbelt.budget import TokenWeightedBudgetGovernor
from agentbelt.egress import LinkPolicyEgressGuard
from agentbelt.pdp import CedarPDP
from agentbelt.provenance import ProvenanceTracker
from agentbelt.risk import CrescendoRiskScorer
from agentbelt.risk_semantic import SemanticDriftRiskScorer
from agentbelt.scope import DeterministicScopeGuard

Factory = Callable[[object], object]  # factory(cfg) -> component instance

_REGISTRY: dict[str, dict[str, Factory]] = {
    "scope": {}, "risk": {}, "budget": {}, "egress": {}, "pdp": {}, "provenance": {}}
_DEFAULTS = {"scope": "deterministic", "risk": "crescendo", "budget": "token_weighted",
             "egress": "link_policy", "pdp": "cedar", "provenance": "default"}


def register(kind: str, name: str):
    """Register a built-in (or in-process custom) provider: @register('risk','myname')."""
    def deco(factory: Factory) -> Factory:
        _REGISTRY.setdefault(kind, {})[name] = factory
        return factory
    return deco


def resolve(kind: str, spec: str | None, cfg) -> object:
    """Build a component. `spec` is a built-in name, a dotted 'module:factory' path, or None."""
    spec = spec or _DEFAULTS[kind]
    if ":" in spec:  # user-supplied dotted import path to a factory(cfg)
        module, _, attr = spec.partition(":")
        factory = getattr(import_module(module), attr)
    else:
        try:
            factory = _REGISTRY[kind][spec]
        except KeyError:
            raise ValueError(f"unknown {kind} provider '{spec}' "
                             f"(built-ins: {sorted(_REGISTRY[kind])}, or use 'module:factory')")
    return factory(cfg)


# --- built-in factories ------------------------------------------------------

@register("scope", "deterministic")
def _scope(cfg):
    return DeterministicScopeGuard()


@register("risk", "crescendo")
def _risk_crescendo(cfg):
    return CrescendoRiskScorer()


@register("risk", "semantic")
def _risk_semantic(cfg):
    reference = cfg.scope.charter + " " + " ".join(
        e.get("text", "") for e in cfg.scope.examples if e.get("label") == "onscope")
    return SemanticDriftRiskScorer(reference)


@register("budget", "token_weighted")
def _budget(cfg):
    return TokenWeightedBudgetGovernor()


@register("egress", "link_policy")
def _egress(cfg):
    return LinkPolicyEgressGuard()


@register("pdp", "cedar")
def _pdp(cfg):
    return CedarPDP()


@register("provenance", "default")
def _provenance(cfg):
    return ProvenanceTracker()
