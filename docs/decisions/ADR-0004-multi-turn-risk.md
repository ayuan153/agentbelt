# ADR-0004: Multi-Turn (Crescendo) Session-Risk Scoring

## Status

**Accepted**

## Context

Per-turn input guards are stateless: each message is judged in isolation. The **Crescendo**
attack class (see [`../incidents.md`](../incidents.md) and the DeepContext research noted there)
exploits this — an attacker escalates gradually over several turns, each of which looks benign
enough to pass the scope guard, until the agent has been walked off-purpose. A harness that only
inspects single turns misses the most effective modern jailbreak pattern.

The threat model calls this out under T1/T2; requirement R1 ("enforce scope, not just refuse") and
R7 ("observe & detect") imply we need *session-level* state, not just per-turn checks.

## Decision

Add a **session-level risk accumulator** as an augmentation of the input guard (H1), implemented as
a pluggable `RiskScorer` (`agentbelt/risk.py`, default `CrescendoRiskScorer`). It is deterministic
(no LLM/network) so it is cheap and reproducible.

Each turn, the scorer updates `session.risk_score`:

```
risk = risk * decay                      # one-off borderline turns fade
     + (offscope_weight | unknown_weight) # contribution from this turn's scope verdict
     + cue_weight * (# escalation cues)    # soft persuasion phrases found this turn
```

- **Escalation cues** are *soft* persuasion phrases (`"pretend"`, `"hypothetically"`,
  `"just this once"`, `"step by step"`, `"my grandma"`, …) that are **deliberately separate** from
  the scope guard's `hard_deny` patterns: individually benign, dangerous only in accumulation.
- **Decay** (`0.8` default) means a single odd turn fades, while *sustained* pressure compounds.
- When `risk_score >= threshold` (default `1.0`), the turn's effective scope verdict is forced to
  `offscope`, so the existing Cedar `AdmitInput` policy **deflects it without calling the upstream**.
  The score and trip are recorded in telemetry (R7).

Config lives in `RiskConfig` (operator-tunable `threshold`, `decay`, weights). Defaults are shipped;
operators tune per risk appetite.

## Consequences

- Closes the stateless-guard gap for gradual escalation, at negligible cost, and reuses the existing
  deflection path (no new enforcement surface).
- Telemetry of accumulating risk gives operators an early-warning signal (R7).

### Limitations / residual gaps

- **Heuristic, not semantic.** A keyword/decay model will miss paraphrased escalation and can be
  evaded; it is a *floor*, not a guarantee. The pluggable interface allows swapping in a learned
  scorer (e.g. a DeepContext-style intent-drift model) later. An alternative **semantic charter-drift
  scorer** is already shipped (`agentbelt/risk_semantic.py`, selectable via `risk.scorer: semantic`) —
  a deterministic lexical-drift *proxy* for that learned model, demonstrating the interface is
  pluggable. See [`../lld/multi-turn-risk-and-tiering.md`](../lld/multi-turn-risk-and-tiering.md).
- **Session identity required.** Accuracy depends on a stable principal/session (see D3/D4 in
  [`../open-questions.md`](../open-questions.md)); an attacker who resets the session resets the score.
- **Tuning tradeoff.** Too low a threshold over-blocks long benign conversations; too high lets slow
  ramps through. Defaults are conservative; this is an operator dial.
- State is the ephemeral per-session `risk_score` only — no transcript retention (D6).

## Alternatives Considered

| Alternative | Why not (now) |
|-------------|---------------|
| Stateless per-turn only | The thing we're fixing — misses Crescendo by design |
| LLM-judge per turn over full history | Cost + its own injection surface; non-deterministic tests |
| Learned intent-drift model (DeepContext) | Higher fidelity but heavier; the `RiskScorer` interface keeps it swappable later |

---

*Related:* [ADR-0003](ADR-0003-cedar-policy-schema.md) (AdmitInput deflection path),
[`../lld/multi-turn-risk-and-tiering.md`](../lld/multi-turn-risk-and-tiering.md),
[`../threat-model.md`](../threat-model.md), [`../configurability.md`](../configurability.md).
