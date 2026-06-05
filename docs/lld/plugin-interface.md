# Plugin Interface — Bring Your Own Component

Agentbelt's guards are **pluggable**. Without training anything in the harness, a power user can drop
in their own scope classifier, multi-turn risk model, policy engine, etc. Decision rationale:
[ADR-0005](../decisions/ADR-0005-plugin-interface.md).

## The six extension points (contracts)

Each is a Protocol in `agentbelt/types.py`. Implement the one you want to replace:

| Kind (`providers:` key) | Protocol | Method you implement | Built-ins |
|-------------------------|----------|----------------------|-----------|
| `scope` | `ScopeGuard` | `evaluate(messages, scope) -> ScopeResult` | `deterministic` |
| `risk` | `RiskScorer` | `score_turn(session, user_text, scope_verdict, cfg) -> RiskResult` | `crescendo`, `semantic` |
| `budget` | `BudgetGovernor` | `check(...)`, `record(...)` | `token_weighted` |
| `egress` | `EgressGuard` | `sanitize(text, cfg) -> EgressResult` | `link_policy` |
| `pdp` | `PolicyDecisionPoint` | `decide(req) -> Decision` | `cedar` |
| `provenance` | `ProvenanceProvider` | `turn_trust(session, messages) -> str` | `default` |

## How selection works

A **provider** is a factory `factory(cfg) -> component`. In config, each `providers:` value is either
a built-in name or a dotted import path `"module:factory"`:

```yaml
providers:
  scope:  deterministic                      # built-in by name
  risk:   "acme.guards:make_drift_scorer"     # your own factory(cfg) -> RiskScorer
  pdp:    cedar
```

`resolve(kind, spec, cfg)` imports the dotted path (or looks up the registry) and calls
`factory(cfg)`. The factory gets the **whole `AgentbeltConfig`** (charter, params, tool tiers, …), and
your component gets per-call context through its Protocol method. Unknown names raise `ValueError`.

## Minimal example (bring your own RiskScorer)

See [`agentbelt/contrib/example_plugin.py`](../../agentbelt/contrib/example_plugin.py):

```python
from agentbelt.types import RiskResult

class MyScorer:                                  # implements RiskScorer
    def __init__(self, threshold): self.threshold = threshold
    def score_turn(self, session, user_text, scope_verdict, cfg):
        score = my_model.predict(user_text)      # <-- your model/service call
        return RiskResult(score=score, tripped=score >= cfg.threshold,
                          reasons=["my_model"] if score >= cfg.threshold else [])

def make(cfg):                                   # the provider factory
    return MyScorer(threshold=cfg.risk.threshold)
```

```yaml
providers:
  risk: "yourpkg.scorers:make"
  # optional free-form params your factory can read from cfg.providers:
  risk_params: { threshold: 0.7 }
```

That's the whole integration — no harness fork, no training inside Agentbelt. When `score_turn`
reports `tripped`, the proxy deflects the turn through the existing Cedar `AdmitInput` path
(same as the built-in scorers).

## In-process registration (alternative to dotted path)

If you'd rather register by name at import time:

```python
from agentbelt.plugins import register
@register("risk", "my_scorer")
def make(cfg): return MyScorer(cfg.risk.threshold)
# then:  providers: { risk: my_scorer }   (ensure your module is imported first)
```

## Notes / limits

- Plugins run **in-process** with the harness's privileges — load only code you trust (same as any
  dependency); there is no sandbox.
- The factory contract is checked at runtime; a bad plugin fails fast at startup/first use.
- Protocol signatures are fixed; if you need richer context than a method passes, read it from `cfg`
  at construction. Widening a Protocol is a future versioned change.
- `ProvenanceTracker` (the `provenance` kind) is now pluggable; only the audit sink remains infra.
- **Validated fail-fast:** `python -m agentbelt --check` (and a normal boot) constructs every provider
  via `agentbelt/validate.py`, so a bad built-in name or an unimportable plugin path is reported at
  startup with `ERROR: provider[<kind>]=...`, not at first request.

## Tested

`tests/test_plugins.py`: registry resolution (built-in name, default, dotted path, unknown→error)
and an **end-to-end** test where a custom scorer selected only via `providers.risk` deflects a
trigger turn while admitting a normal one.
