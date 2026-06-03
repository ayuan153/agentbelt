# ADR-0005: Extension / Plugin Interface

## Status

**Accepted**

## Context

Seatbelt's value proposition is being a *generic, configurable* harness. The built-in guards are
deliberately simple and deterministic (keyword scope, heuristic risk, lexical drift). Power users
will outgrow them — they'll want to plug in their **own** scope classifier, their own multi-turn
risk model, or their own policy engine — **without forking the harness or training anything inside
it**. We already express each control as a Protocol in `seatbelt/types.py`; what was missing was an
ergonomic way to *select and load* an implementation.

This is intentionally **not** about training models. It is the software seam that lets someone bring
a model (or any custom logic) they built elsewhere.

## Decision

Introduce a **provider** indirection for every extension point. A provider is a factory
`factory(cfg: SeatbeltConfig) -> component`, where `component` satisfies the matching Protocol
(`ScopeGuard` / `RiskScorer` / `BudgetGovernor` / `EgressGuard` / `PolicyDecisionPoint`).

Selection is config-driven, via a top-level `providers:` map, where each value is **either**:

- a **built-in name** (e.g. `semantic`), resolved from a registry, **or**
- a **dotted import path** to the user's own factory: `"yourpkg.module:make"`.

```yaml
providers:
  scope:  deterministic                       # built-in
  risk:   "acme.guards:make_drift_model"       # bring your own — a factory(cfg) -> RiskScorer
  pdp:    cedar
```

`seatbelt/plugins.py` provides `register(kind, name)` (for built-ins / in-process registration) and
`resolve(kind, spec, cfg)` (dotted-path import or registry lookup → call `factory(cfg)`). `create_app`
builds all five guards through `resolve(...)`, defaulting to the built-ins, so existing deployments
are unchanged. The factory receives the **whole config**, so a custom component has full access to
the charter, params, tool tiers, etc. — and gets per-call context (messages/scope/session) through
its Protocol method.

The previous `risk.scorer` field is retained as a back-compat alias for `providers.risk`.

`ProvenanceTracker` and the audit sink are **infrastructure**, not extension points, so they are not
pluggable (yet).

## Consequences

- A power user plugs in their own model by writing a one-line factory and pointing config at it —
  no harness fork, no PR, no training inside Seatbelt.
- Built-ins are just registered providers, so the core and "custom" paths are identical and equally
  tested (`tests/test_plugins.py`, incl. an end-to-end custom scorer).
- Keeps the harness generic: domain/risk *intelligence* can live in operator-owned plugins while the
  enforcement spine stays constant.

### Limitations / residual gaps

- The factory contract (`factory(cfg) -> Protocol`) is a runtime contract; a malformed plugin fails
  at startup/first use rather than at config-validation time. (Acceptable for a power-user feature.)
- A plugin runs **in-process** with the harness's privileges — operators must trust code they load
  (same trust model as any Python dependency). No sandboxing.
- Per-call Protocol signatures are fixed; a plugin needing richer context (e.g. full history) is
  limited to what the Protocol passes plus what it reads from `cfg` at construction. Widening a
  signature is a future, versioned change.

## Alternatives Considered

| Alternative | Why not |
|-------------|---------|
| Subclass + fork the harness | Defeats "generic, no fork"; the thing we're avoiding |
| Python entry-points (`importlib.metadata`) | Heavier packaging ceremony; dotted-path is friendlier for a config file and in-repo plugins. Can be added later as another `resolve` source. |
| Pass instances in code only | Not config-driven; operators editing YAML can't swap implementations |

---

*Related:* [`../lld/plugin-interface.md`](../lld/plugin-interface.md) (bring-your-own guide),
[`../configurability.md`](../configurability.md), [ADR-0004](ADR-0004-multi-turn-risk.md)
(RiskScorer is the headline pluggable point), `seatbelt/types.py` (the Protocols).
