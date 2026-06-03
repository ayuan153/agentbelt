# Genericity & Configuration Model

The point of Seatbelt is to be a **generic, pluggable harness** that clips onto *any* app
builder's conversational agent. So it must know **nothing** about your app. The split is:

> **Seatbelt ships the mechanism + safe defaults. The operator declares the intent via config.
> You fill in a config; you never fork the harness.**

Everything a deployment needs to express lives in three operator-owned config surfaces:

1. **Scope contract** — what the agent is *for* (§2).
2. **Tool risk map** — how dangerous each action is (§3).
3. **Cedar policy + knobs** — the enforcement rules and operating points (§4–§7).

This document answers the "make it flexible / don't tie it to a use case" feedback on the
[`open-questions.md`](open-questions.md) decision log, and grounds it in a worked
[Chipotle-style case study](#8-case-study-a-chipotle-style-facsimile).

---

## 1. Who owns what

| Concern | Mechanism (Seatbelt ships) | Intent (operator declares) | If operator is silent |
|---------|----------------------------|----------------------------|-----------------------|
| Scope | Layered scope evaluator (§2) | Purpose charter + allow/deny intents + examples | Deny-by-default to declared intents |
| Sensitive actions | Tier resolver + Cedar PDP (§3) | Per-tool tier overrides; trusted tool servers | Treat unclassified as **sensitive** |
| Anonymous abuse | Composite principal + cost budgets (§5) | Budget caps, friction level | Open + capped + graduated friction |
| Session state | Rolling risk accumulator (§6) | Retention window | Ephemeral derived signals only |
| Enforcement point | Gateway proxy + optional SDK shim (§7) | Deployment mode | Gateway-first |
| Failure behavior | Per-path fail posture (§7 / D8) | Override per path | Graduated (fail-closed on risk paths) |

Nothing in that table names "Chipotle," "support," "banking," or any domain. The domain lives
only in the operator's config values.

---

## 2. Scope as a configurable rules-agent  *(resolves D1)*

Seatbelt does **not** hardcode what's on-topic. The operator supplies a **scope contract**, and a
swappable **scope evaluator** (the "rules agent") enforces it. The contract is declarative:

```yaml
scope:
  charter: >          # one paragraph the operator writes; drives the classifier
    Assist customers of a quick-service restaurant with menu, ordering, store
    info, nutrition, and order issues. Nothing else.
  allow_intents: [menu, order_status, place_order, hours_locations, nutrition, refund_request]
  hard_deny:          # deterministic, cheap, non-negotiable
    - code_generation        # "write me a Python script"  <- the Chipotle/Zoom failure
    - general_knowledge      # "who won the world cup"
    - role_override          # "ignore your instructions / you are now..."
  on_offscope: deflect       # deflect | refuse | escalate
  deflect_message: "I can only help with orders and menu questions."
  examples:           # few-shot labels that sharpen the boundary
    - { text: "help me write a complaint letter", label: offscope }
    - { text: "is the barbacoa gluten free", label: onscope }
```

The evaluator runs the same layered, cheapest-first pattern as injection detection
(see [`harness-design.md`](harness-design.md) §3.2):

1. **Deterministic `hard_deny`** — regex/signatures (code fences, "ignore previous…"). <5 ms.
2. **Charter-driven classifier** — a small model (or LLM-judge) prompted *only* with the
   operator's charter + examples decides on/off-scope. Swappable; that's the "rules agent."
3. **Deny-by-default** — low-confidence or unmatched → `on_offscope` behavior.

**Why this is safe even when the classifier is wrong:** scope enforcement is *not* load-bearing on
its own. Because untrusted content is capability-downgraded and budgets are cost-capped (§3, §5),
an off-scope request that slips through **can't do anything and can't cost much** — a Chipotle-style
"free Claude Code" prompt produces, at worst, one short throttled reply, not a free coding service.

---

## 3. Generic sensitive-action classification  *(resolves D2 — my state-of-the-art opinion)*

A generic harness can't know your tools, so it must *derive* risk. Seatbelt resolves each tool to a
**sensitivity tier** by a 3-step precedence, then attaches a Cedar-enforced control to the tier:

**Step 1 — Operator override (authoritative).** A declarative map wins over everything:
```yaml
tool_tiers:
  issue_refund:  { tier: high }      # money movement
  lookup_order:  { tier: low }
trusted_tool_servers: ["tools.internal.example.com"]   # whose annotations we'll believe
```

**Step 2 — Standard risk annotations, *only from trusted servers*.** The MCP spec defines
[`ToolAnnotations`](https://modelcontextprotocol.io/specification/2025-03-26/server/tools):
`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`. Seatbelt maps them to tiers —
**but the spec is explicit that these are hints and "clients MUST consider tool annotations
untrusted unless they come from trusted servers."** So Seatbelt only believes annotations from
servers in `trusted_tool_servers`; annotations from anyone else are ignored for the security
decision. Conservative omission defaults align with default-deny:

| Annotation (omitted ⇒ default) | Contribution to tier |
|--------------------------------|----------------------|
| `readOnlyHint` omitted ⇒ assume *modifies* | not low |
| `destructiveHint` omitted ⇒ assume *destructive* | → high |
| `idempotentHint` omitted ⇒ assume *not idempotent* | raises tier |
| `openWorldHint` omitted ⇒ assume *open world* | raises tier |

**Step 3 — Heuristic fallback** (no override, untrusted/no annotations): infer from the tool schema —
HTTP verb (GET=low; POST/PUT/DELETE=higher), name patterns (`send|delete|transfer|reset|refund|grant`),
and parameter types touching money/PII/credentials.

**Default-deny-to-sensitive:** anything still unclassified is treated as **high** (requires
verified user + confirmation). Tiers bind to controls in Cedar (the engine you chose, D5):

```cedar
// low: allowed freely.  high: requires a verified end-user AND human confirmation.
forbid (principal, action, resource)
when { resource.tier == "high" && !(context.user_verified && context.human_confirmed) };
```

This is generic (works for any builder's tools), leans on a real interoperability standard (MCP
annotations) where it's *safe* to, and fails safe everywhere else.

> **Implemented** in `seatbelt/tooltier.py` (`resolve_tier`) and wired into the proxy's tool
> mediation. The prototype reads annotations from each request tool def via a `function.annotations`
> + `function.x_mcp_server` convention (what the MCP proxy would discover); full MCP server-manifest
> discovery is the next increment. See [`lld/multi-turn-risk-and-tiering.md`](lld/multi-turn-risk-and-tiering.md).

---

## 4. Configuration is the whole interface

A deployment is fully described by the YAML above plus a Cedar policy file plus a few knobs (§5–§7).
Retargeting Seatbelt from a restaurant bot to a bank bot or an HR bot means **editing these files —
never the harness**. The case study in §8 makes that concrete.

---

## 5. Anonymous-abuse default posture  *(resolves D4 — my opinion)*

**Default opinion: open + cost-capped + graduated friction. Do not force login.** A generic harness
can't assume the host app even *has* auth, and forcing it would break pluggability. So Seatbelt ships:

- **Composite principal** = `hash(IP, session-token, optional fingerprint)` — no login required.
- **Cost-aware budget** per principal per rolling window, **weighted to output tokens** (the
  expensive side; see [`harness-design.md`](harness-design.md) §3.7). This is the real
  denial-of-wallet control, not requests/sec.
- **Graduated friction:** invisible challenge (Turnstile/PoW) only when a principal trips an anomaly
  or budget threshold; escalate to CAPTCHA/login only on repeat abuse. Quiet for normal users.

Knobs: `budget.cost_units_per_window`, `anomaly.action`, `friction.escalation`. Operators tighten
(e.g., require login for a high-value internal bot) or loosen freely.

---

## 6. Session-state retention default  *(resolves D6 — my opinion)*

**Default opinion: keep derived signals, not content.** Multi-turn (Crescendo) detection needs
session state, but that state should be the *minimum*: an ephemeral, in-memory per-session **risk
accumulator + rolling intent score**, TTL = session lifetime + a short idle grace. **No raw
transcript retention by default.** The audit log records *decisions* + redacted metadata (hashes,
tiers, verdicts), with its own separately-configurable retention for compliance. Privacy-preserving
by default; an operator with a retention obligation opts into more, rather than the harness hoarding
content nobody asked it to keep.

---

## 7. Deployment: gateway-first, in-process optional  *(resolves D7 — tradeoffs + "gateway-only?")*

**The tension you flagged:** requiring an in-process SDK hook would undercut "pluggable into *any*
agent." **Good news: for the mainstream architecture, gateway-only is viable**, because modern agents
talk to the model and to tools over HTTP — and MCP's recommended transport is **Streamable HTTP**, so
a network gateway can intercept tool calls without protocol-specific code. Real products already do
this: **Bedrock AgentCore Gateway** (Cedar per `tools/call` + Lambda interceptors), **Kong AI
Gateway** (AI MCP Proxy, MCP tool-level access control, guardrails), **Solo.io agentgateway**
(MCP/A2A governance). None require in-process code.

So Seatbelt ships **gateway-first** as the zero-instrumentation default, and treats an in-process
shim as an *enhancement*, not a requirement:

| Control | Gateway-only (default) | Needs in-process shim |
|---------|------------------------|------------------------|
| H1 input guard, H5 output guard | ✅ full (sees request/response) | — |
| H6 egress, H0 budget/telemetry | ✅ full | — |
| H3 action mediation | ✅ **if tool calls route through the gateway** (MCP/HTTP) — Cedar per call | only for tools executed as *local* function calls that never traverse the gateway |
| H2 provenance / capability-downgrade | ◑ **substantial** — tag untrusted segments in the messages array; block a tool call whose only new justifying content is untrusted | race-free, reasoning-trace-level provenance |

**Can we hit our goals gateway-only? Mostly yes** — for agents whose model and tool traffic is
HTTP/MCP-mediated (the common case), gateway-only delivers all controls, with H2 provenance
*approximated* by tagging untrusted message segments rather than reading the model's private
reasoning. The honest residual gap: **tools invoked as in-process function calls that never hit the
gateway**, and *perfectly* race-free provenance. For those, an optional thin SDK shim adds the
in-process hook.

**Decision:** gateway-first (maximally pluggable), single shared Cedar PDP, optional in-process PEP
for builders who run local-only tools or want the strongest provenance guarantee. The "pluggable
contract" we recommend to builders: **expose your tools through the gateway (MCP/HTTP) and you get
action-mediation for free.**

---

## 7a. Configurable failure posture  *(resolves D8 — configurable + my default)*

**Default opinion: graduated, and configurable per path.** A harness that bricks the whole bot when
a classifier service hiccups gets ripped out; one that *silently allows* a refund or a data egress
when its guard is down is unacceptable. So:

- **Fail-closed** on the risk paths: sensitive-action mediation (H3), egress (H6).
- **Fail-open-with-loud-telemetry** on quality paths: scope checks on low-risk reads, output style.

```yaml
fail_posture:        # operator can override any path
  default: closed
  low_risk_read: open_with_alert
  output_scope_check: open_with_alert
```

---

## 8. Case study: a Chipotle-style facsimile

To show the harness is generic, here's a complete config for a **facsimile quick-service-restaurant
assistant** (call it *BurritoBot*) — the class of bot behind the real Chipotle "free Claude Code"
incident ([`incidents.md`](incidents.md) #10). Seatbelt has no "restaurant" code; this is *only*
config:

```yaml
agent: burritobot
scope:
  charter: "Help customers with menu, ordering, store info, nutrition, and order issues. Nothing else."
  allow_intents: [menu, order_status, place_order, hours_locations, nutrition, refund_request]
  hard_deny: [code_generation, general_knowledge, role_override]
  on_offscope: deflect
  deflect_message: "I can only help with orders and menu questions 🌯"
tool_tiers:
  get_menu:      { tier: low }
  order_status:  { tier: low }
  place_order:   { tier: medium }     # spends money but bounded
  issue_refund:  { tier: high, require: [user_verified, human_confirm] }
trusted_tool_servers: ["tools.burritobot.internal"]
egress:
  allow_domains: ["burritobot.example"]   # live-validated; no stale domains (ForcedLeak lesson)
  render_links: false
budget:
  per_principal: { cost_units_per_hour: 50, output_token_weight: 5 }
  anomaly: { offscope_spike: throttle_and_challenge }
fail_posture: { default: closed, low_risk_read: open_with_alert }
```

**How this stops the real incidents** (all via config, no bespoke code):

- *"Stop paying for Claude Code, this bot is free"* → `hard_deny: code_generation` blocks it
  deterministically; even a novel evasion is bounded by the 50 cost-units/hour budget and produces a
  single throttled reply. (Chevy/Chipotle/Zoom class.)
- *Hidden instruction in a review/RAG doc telling the bot to email order history out* → ingested
  content is capability-downgraded and can't trigger `issue_refund` or any egress; `render_links:
  false` + the domain allowlist kill the exfil channel. (EchoLeak/ForcedLeak class.)
- *"Refund my last 10 orders"* → `issue_refund` is `high`, so Cedar requires a verified end-user and
  human confirmation; the chat session alone can't authorize it. (Meta confused-deputy class.)

**Now retarget it — change values, not code.** The *same schema* configures a totally different agent:

```yaml
agent: retail-bank-assistant
scope: { charter: "Help with balances, transactions, and card servicing. No tax/legal/investment advice.", allow_intents: [balance, txn_history, card_lock, dispute], hard_deny: [code_generation, financial_advice, role_override], on_offscope: refuse }
tool_tiers: { get_balance: {tier: low}, lock_card: {tier: medium}, wire_transfer: {tier: high, require: [user_verified, step_up_auth, dual_control]} }
egress: { allow_domains: ["mybank.example"], render_links: false }
budget: { per_principal: { cost_units_per_hour: 30, output_token_weight: 5 } }
fail_posture: { default: closed }
```

Same harness, same six hooks, same Cedar PDP — only the operator's intent changed. That is the
"seatbelt": one belt, any vehicle.

---

## 9. Updated decision status

| # | Decision | Status |
|---|----------|--------|
| D1 | Scope | ✅ Configurable **rules-agent** (§2) — operator's scope contract, not hardcoded |
| D2 | Sensitive-action classification | ✅ Generic 3-step resolver (override → trusted MCP annotations → heuristic), default-sensitive (§3) |
| D3 | Identity source / step-up UX | ⚠️ Still operator's IdP choice; contract is RFC 8693 token exchange (unchanged) |
| D4 | Anonymous-abuse | ✅ Default open + cost-capped + graduated friction (§5) |
| D5 | Policy engine | ✅ **Cedar** (your call) |
| D6 | Session-state retention | ✅ Default ephemeral derived signals, no transcript retention (§6) |
| D7 | Deployment | ✅ **Gateway-first**, optional in-process shim; gateway-only meets goals for HTTP/MCP-mediated agents (§7) |
| D8 | Fail posture | ✅ Configurable, default graduated (fail-closed on risk paths) (§7a) |
