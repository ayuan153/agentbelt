# ADR-0002: Provenance & Trust-Propagation Model

## Status

**Accepted**

## Context

Prompt-injection attacks (threats T2, T4 in the [threat model](../threat-model.md))
exploit the fact that LLMs treat all input tokens with equal authority. To enforce the
capability-downgrade invariant — actions must only be authorized when justified by
operator or user intent, not by injected content — Seatbelt needs a model for tracking
the **provenance** (trust origin) of every piece of context the model consumes.

The detailed exploration of design options lives in
[../spikes/provenance-model.md](../spikes/provenance-model.md). This ADR records the
accepted decision.

## Decision

### Three trust tiers

| Tier | Source | Examples |
|------|--------|----------|
| **TRUSTED** | Operator / developer instructions; Seatbelt policy | `role=system`, `role=developer` messages |
| **USER** | End-user's direct conversational turn (semi-trusted) | `role=user` messages typed by the human |
| **UNTRUSTED** | Tool/function results, RAG/retrieved docs, ingested external content | `role=tool` messages; email/calendar/web/file content |

### Default derivation at the gateway

Derived from OpenAI message roles on every request through the model proxy:

- `role=system` / `role=developer` → **TRUSTED**
- `role=user` → **USER**
- `role=tool` → **UNTRUSTED**

### Embedded-content gap & resolution

RAG/retrieved text embedded *inside* a `role=user` message cannot be distinguished by
role alone. Resolution (in priority order):

1. **Optional host-app labeling convention** — structured content parts or a
   provenance-hint map keyed by content hash supplied by the host app.
2. **Conservative heuristic** — treat injected-looking segments as UNTRUSTED;
   apply spotlighting techniques to reduce injection surface.

### Load-bearing invariant: capability downgrade

> A tool call or egress action is authorized **only** if its justification traces to
> TRUSTED or USER content. If the newly-introduced content since the last decision
> point is exclusively UNTRUSTED, the action is **blocked or escalated**.

This invariant is enforced by the Cedar policy layer (see
[ADR-0003](ADR-0003-cedar-policy-schema.md), specifically the
`provenance_max_trust` context field).

### Stateless-gateway solution

Provenance state lives in a **shared session store** keyed by session ID
(`X-Seatbelt-Session` per [ADR-0001](ADR-0001-interception-contract.md)):

- Map: `content-hash → { trust_tier, new_untrusted_this_turn: bool }`
- Re-sent messages are matched by hash for cheap, consistent re-derivation across
  gateway replicas.
- The `new_untrusted_this_turn` flag feeds the capability-downgrade check at decision
  time.

## Consequences

### Benefits

- Enables principled defense against indirect prompt injection (T2) without requiring
  the model itself to be injection-proof.
- Works at the HTTP-proxy layer with no agent code changes (aligns with ADR-0001).
- The labeling convention gives sophisticated host apps full control while the heuristic
  provides a safe default.
- The session store approach keeps individual gateway instances stateless and
  horizontally scalable.

### Limitations / residual gaps

- **No true causal tracing**: the gateway cannot read the model's private
  chain-of-thought. "Justification" is **approximated** by content-trust accounting
  (what new content appeared), not by tracing which tokens actually influenced the
  model's decision. Exact causal provenance requires the optional in-process shim
  described in [harness-design.md](../harness-design.md). **This shim is now
  implemented** ([`../lld/in-process-shim.md`](../lld/in-process-shim.md)): it narrows
  the gap to agent-reported *per-decision* provenance, though it remains cooperative
  (not automatic taint propagation).
- **Heuristic false positives**: the conservative embedded-content heuristic may
  over-classify legitimate user text as UNTRUSTED, causing unnecessary escalations.
- **Hash collisions**: content-hash keying assumes collision-free hashes (SHA-256);
  an adversary who can forge a hash collision could poison the tier map — practically
  infeasible but noted for completeness.
- **Session store availability**: the shared store is a runtime dependency; if
  unavailable, the gateway must fail-closed (deny) which impacts availability.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| Binary trusted/untrusted (no USER tier) | Too coarse; would block all user-initiated tool use |
| Per-token taint tracking inside the model | Requires model-internal instrumentation; not feasible at the proxy layer |
| Signed content envelopes from host app (mandatory) | Too high an integration burden for first target; offered as optional convention instead |
| Stateful per-instance tracking (no shared store) | Breaks horizontal scaling; sticky sessions add operational complexity |

---

*Related:* [../spikes/provenance-model.md](../spikes/provenance-model.md),
[harness-design.md](../harness-design.md) (H2/H4 context firewall),
[threat-model.md](../threat-model.md) (T2, T4),
[../lld/mvp-denial-of-wallet-slice.md](../lld/mvp-denial-of-wallet-slice.md).
