# LLD: Multi-Turn Risk Scoring + Annotation-Driven Tier Resolution

Two augmentations to the pluggable proxy, both shipped and tested. Neither requires any agent code
change. Realizes [ADR-0004](../decisions/ADR-0004-multi-turn-risk.md) and the tier precedence in
[`../configurability.md`](../configurability.md) §3 / [ADR-0003](../decisions/ADR-0003-cedar-policy-schema.md).

## 1. Multi-turn (Crescendo) risk scoring — `agentbelt/risk.py`

Augments the input guard (H1) with session-level state to catch gradual escalation.

- `CrescendoRiskScorer.score_turn(session, user_text, scope_verdict, cfg) -> RiskResult`
- Per turn: `risk = risk*decay + verdict_weight + cue_weight*#cues`; `tripped = risk >= threshold`.
- Escalation cues (`ESCALATION_CUES`) are soft persuasion phrases kept **separate** from the scope
  guard's `hard_deny` (benign individually, dangerous in accumulation).

**Proxy wiring** (`app.py`), right after the scope guard:

```
verdict = scope_guard.evaluate(...)            # per-turn
rr = risk.score_turn(session, last_user, verdict, cfg.risk)
effective_verdict = "offscope" if rr.tripped else verdict
# Cedar AdmitInput(scope_verdict=effective_verdict) -> deflect (no upstream call) if offscope
```

So a tripped session reuses the existing deflection path; `risk_score`/`tripped` are logged.
Worked numerics (defaults `decay=0.8, unknown_weight=0.15, cue_weight=0.4`), one cue/turn,
unknown scope: `0.55 → 0.99 → 1.34(trip)`. A single such turn (`0.55`) is admitted.

## 2. Annotation-driven tier resolution — `agentbelt/tooltier.py`

Makes H3 tool-sensitivity tiering generic. `resolve_tier(name, tool_tiers, trusted_servers,
annotations, server)` precedence (first match wins):

1. **Operator override** (`tool_tiers[name]`) — authoritative.
2. **Trusted-server MCP `ToolAnnotations`** — only if `server ∈ trusted_servers` (the MCP spec's
   "untrusted unless from a trusted server" caveat). `readOnlyHint:true → low`; `destructiveHint`
   (omitted ⇒ **destructive** ⇒ `high`); else `medium`.
3. **Name heuristic** — read prefixes (`get_/list_/read_/…`) → `low`; write tokens
   (`send/delete/transfer/refund/…`) → `high`; else none.
4. **Default-sensitive** → `high`.

**Proxy wiring** (`app.py`): the tool-mediation loop builds `tool_meta` from the request's
`tools[]` — reading optional `function.annotations` and `function.x_mcp_server` (the prototype
convention for what the MCP proxy would discover) — then calls `resolve_tier` instead of a flat
lookup. The resolved tier feeds the Cedar `InvokeTool` decision (capability-downgrade + verification).

## Tests

- Unit: `tests/test_risk.py` (decay/trip/cues), `tests/test_tooltier.py` (precedence + caveat).
- Integration (`tests/test_integration.py`): a single borderline turn is admitted; a sustained
  Crescendo sequence trips and deflects; a `readOnlyHint` tool from a **trusted** server resolves
  `low` and is allowed even under untrusted provenance; the **same** annotation from an untrusted
  server is ignored → default `high` → blocked. Full suite: **60 passing**.

## Limitations

- Risk scoring is heuristic (keyword + decay) — a floor, swappable for a learned model via the
  `RiskScorer` interface (ADR-0004). An alternative **semantic charter-drift** scorer is now
  shipped (`agentbelt/risk_semantic.py`, `risk.scorer: semantic`) as a deterministic proxy for a
  learned model.
- The `x_mcp_server`/`annotations` fields on tool defs are a prototype convention. **MCP
  server-manifest discovery is now implemented** (`agentbelt/mcp_discovery.py`,
  `discover_annotations`): `create_app(..., mcp_fetch=...)` fetches `tools/list` from trusted
  servers and the proxy falls back to those annotations when a request omits them.
- Tier resolution trusts operator config for `trusted_tool_servers`; annotations are never trusted
  from unlisted servers (enforced in both the request and discovery paths).
