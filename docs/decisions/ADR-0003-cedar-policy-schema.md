# ADR-0003: Cedar Policy Schema & PDP/PEP Interface

## Status

**Accepted**

## Context

Agentbelt requires a declarative policy engine to evaluate authorization decisions at
each hook point. The choice of Cedar over OPA was already accepted (see
[../open-questions.md](../open-questions.md) and
[../configurability.md](../configurability.md)). This ADR defines the **entity schema**,
**decision-time context**, **policy shape**, and **PDP/PEP interface contract**.

The policies must encode the capability-downgrade invariant from
[ADR-0002](ADR-0002-provenance-model.md) and map cleanly to hook points H0–H6 in the
[harness design](../harness-design.md).

## Decision

### Entity schema

```
entity Agentbelt::Session {
    user_verified: Bool,
    step_up_satisfied: Bool,
    cost_used: Long
};

entity Agentbelt::Tool {
    tier: String    // "low" | "medium" | "high"
};

entity Agentbelt::Destination {
    allowlisted: Bool
};

entity Agentbelt::Answer {};
```

### Actions

```
action Agentbelt::Action::"AdmitInput"   appliesTo { principal: Agentbelt::Session, resource: Agentbelt::Answer };
action Agentbelt::Action::"InvokeTool"   appliesTo { principal: Agentbelt::Session, resource: Agentbelt::Tool };
action Agentbelt::Action::"ReturnAnswer" appliesTo { principal: Agentbelt::Session, resource: Agentbelt::Answer };
action Agentbelt::Action::"Egress"       appliesTo { principal: Agentbelt::Session, resource: Agentbelt::Destination };
```

### Decision-time context (supplied by PEP)

```json
{
  "user_verified": true,
  "human_confirmed": false,
  "step_up": false,
  "provenance_max_trust": "user",
  "tier": "medium",
  "cost_used": 4200,
  "budget_remaining": 5800,
  "scope_verdict": "onscope"
}
```

Fields: `provenance_max_trust` ∈ `{"trusted", "user", "untrusted"}`;
`tier` ∈ `{"low", "medium", "high"}`; `scope_verdict` ∈ `{"onscope", "offscope", "unknown"}`.

### Policy shape: DEFAULT-DENY

No `permit` ⇒ `deny`. Illustrative policies:

```cedar
// 1. Permit low-tier read-only tools unconditionally
permit (
    principal,
    action == Agentbelt::Action::"InvokeTool",
    resource
) when {
    context.tier == "low"
};
```

```cedar
// 2. Forbid high-tier tools unless user is verified AND human confirmed
forbid (
    principal,
    action == Agentbelt::Action::"InvokeTool",
    resource
) when {
    context.tier == "high" &&
    !(context.user_verified && context.human_confirmed)
};
```

```cedar
// 3. Capability-downgrade invariant: block tool/egress when provenance is untrusted
forbid (
    principal,
    action == Agentbelt::Action::"InvokeTool",
    resource
) when {
    context.provenance_max_trust == "untrusted"
};
```

```cedar
// 4. Block egress to non-allowlisted destinations
forbid (
    principal,
    action == Agentbelt::Action::"Egress",
    resource
) when {
    !resource.allowlisted
};
```

```cedar
// 5. Block off-scope requests at input
forbid (
    principal,
    action == Agentbelt::Action::"AdmitInput",
    resource
) when {
    context.scope_verdict == "offscope"
};
```

### Minimal authz-request example

```json
{
  "principal": { "type": "Agentbelt::Session", "id": "sess_abc123" },
  "action": { "type": "Agentbelt::Action", "id": "InvokeTool" },
  "resource": { "type": "Agentbelt::Tool", "id": "web_search" },
  "context": {
    "user_verified": true,
    "human_confirmed": false,
    "step_up": false,
    "provenance_max_trust": "user",
    "tier": "medium",
    "cost_used": 4200,
    "budget_remaining": 5800,
    "scope_verdict": "onscope"
  }
}
```

### PDP/PEP interface

- **PEP** (Policy Enforcement Point): lives in the gateway proxy (both model-proxy and
  tool-proxy paths) and optionally in the in-process shim. Builds the authz request
  (principal, action, resource, context) from hook-point data.
- **PDP** (Policy Decision Point): Cedar evaluation engine — deployed as an in-proc
  library **or** as a sidecar (Verified-Permissions-style service). Returns
  `Decision { allow | deny, reasons[] }`.
- **One shared PDP** serves both the gateway PEP and the optional in-process PEP,
  ensuring policy consistency.

## Consequences

### Benefits

- Cedar's formal verification tooling lets operators prove policy properties (e.g.,
  "no tool invocation is ever permitted when provenance is untrusted").
- DEFAULT-DENY ensures safe behavior for any action not explicitly permitted.
- The context-based approach keeps policies decoupled from session-store internals;
  the PEP translates runtime state into flat context fields.
- A single PDP shared across enforcement points prevents policy drift.

### Limitations / residual gaps

- **`scope_verdict` accuracy**: the scope classifier feeding this field is
  probabilistic; false "onscope" verdicts can allow off-topic abuse. Mitigated by
  layering budget controls (H0) and output guards (H5).
- **Policy complexity ceiling**: Cedar lacks higher-order functions; complex
  aggregation policies (e.g., sliding-window rate limits) must be computed outside
  Cedar and injected as context fields.
- **Schema evolution**: adding new resource types or context fields requires
  coordinated updates to schema, PEP, and deployed policies.
- **Single-PDP availability**: the shared PDP is a single logical dependency; if
  unavailable, the gateway must fail-closed (deny-all), impacting availability.
  Mitigation: local policy cache with bounded staleness.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| OPA / Rego | Evaluated and rejected — see [../open-questions.md](../open-questions.md); Cedar's formal analysis and simpler deny-override semantics preferred |
| Inline policy logic (hard-coded) | Not declarative; defeats configurability goal ([../configurability.md](../configurability.md)) |
| Per-hook-point separate policy engines | Fragmented; risks inconsistent enforcement across hook points |
| XACML | Overly complex; poor developer ergonomics for this use case |

---

*Related:* [ADR-0002](ADR-0002-provenance-model.md) (provenance feeds `provenance_max_trust`),
[harness-design.md](../harness-design.md) (hook points),
[configurability.md](../configurability.md) (Cedar engine choice),
[../lld/mvp-denial-of-wallet-slice.md](../lld/mvp-denial-of-wallet-slice.md).
