# Open Questions, Tradeoffs & Non-Goals

The honest part of the ideation: where Seatbelt's design is uncertain, what it deliberately
won't do, and how we'd know if it works. Read after [`harness-design.md`](harness-design.md).

---

## 1. Hard tradeoffs

- **Security vs. utility.** Tight scope enforcement (R1) is exactly what stops the Chevy/Chipotle
  abuse — and exactly what frustrates legitimate edge-case users (the DPD customer was *trying* to
  get help). Too strict and the bot feels broken; too loose and it's a free LLM. The scope
  boundary is a product decision the policy must make explicit, not a setting we can default well.
- **Latency & cost of guarding.** Classifiers, DLP scans, and a sidecar PDP add a hop and tokens to
  every turn. Ironically, a guard built from LLM calls has its *own* denial-of-wallet surface.
  Cheap deterministic checks should gate expensive model-based ones.
- **False positives vs. false negatives.** Fail-safe/default-deny (R8) trades availability for
  safety. For a refund bot that's fine; for a medical-intake bot, over-blocking has its own harm.
  The right operating point is per-deployment, not universal.
- **Centralized policy vs. agent autonomy.** The more the harness constrains tool use, the less
  "agentic" the agent is. Multi-step autonomous agents will chafe against per-action mediation.
- **Spotlighting/delimiting is not a proof.** Tagging ingested content as "data, not instructions"
  (R2) raises the bar but doesn't mathematically prevent the model from following it. The
  capability-downgrade (untrusted content can't trigger tools/egress) is the load-bearing control;
  the prompt-level tagging is a helper, not the guarantee.

---

## 2. Evasion concerns (how Seatbelt itself gets attacked)

- **Multi-turn / slow-burn jailbreaks.** Splitting an attack across turns to stay under per-turn
  classifier thresholds. Needs session-level state, not just per-turn checks.
- **Obfuscated injection.** Base64, homoglyphs, zero-width chars, translation, code comments,
  image-embedded text (OCR path). The Context Firewall's scanner is in an arms race here.
- **Encoded exfiltration.** Leaking data through allowed channels: DNS-ish tricks, steganography in
  permitted text, slow leakage a few tokens per turn under DLP thresholds.
- **Guard-model injection.** If guards are themselves LLMs, the same injection can target *them*
  ("ignore your moderation instructions"). Guard prompts must be isolated and ideally not
  LLM-based for the critical decisions.
- **Allowlist drift.** Domains expire and get repurchased (ForcedLeak). Allowlists need continuous
  ownership validation, not one-time configuration.
- **Semantic scope ambiguity.** "Help me write a complaint letter" to a support bot — on-scope or
  free writing assistant? Adversaries will live in the gray zone.

---

## 3. Non-goals (explicitly out of scope for the harness)

- **Infra-layer denial-of-wallet.** LLMjacking and exposed-Ollama/"Bizarre Bazaar" abuse stem from
  stolen credentials and unauthenticated endpoints. Those are solved by IAM, secret management,
  network policy, and endpoint auth — *below* the agent's prompt boundary. Seatbelt assumes the
  model endpoint is already authenticated and rate-limited at the infra layer.
- **Model-internal alignment / safety tuning.** Seatbelt is an external harness; it does not retrain
  or fine-tune the model. It assumes the base model is fallible and wraps it accordingly.
- **Hallucination correctness.** The Air Canada failure was a *wrong* answer, not an attack. Output
  scope/brand checks help, but factual accuracy/grounding is a separate (RAG/eval) discipline.
- **General content moderation.** Toxicity/abuse classification is adjacent and could be a plugin,
  but Seatbelt's focus is jailbreak / injection / exfiltration / denial-of-wallet, not a full
  trust-and-safety stack.
- **Endpoint/runtime hardening of tools themselves.** If a tool is insecure (SQL injection in the
  backend it calls), that's the tool's problem; Seatbelt mediates *whether/how* it's called.

---

## 4. Open design questions — worked through

Each question below carries a status: **✅ Resolved** (a defensible design choice exists today,
grounded in current tooling/standards) or **⚠️ Needs operator's call** (a genuine product/risk
decision Seatbelt can't make for you). The decisions in the second bucket are consolidated in
[§4.7](#47-decisions-that-need-the-operator-flagged).

### 4.1 Where should the Context Firewall's instruction-detection run? — ✅ Resolved

**Answer: all three, layered — but detection is *not* the load-bearing control.** The research is
blunt: every standalone injection classifier has been broken. Azure **Prompt Shields** and Meta
**Prompt Guard** were evaded up to ~100% with character-injection / adversarial-ML techniques
([arXiv:2504.11168](https://arxiv.org/abs/2504.11168)); Prompt Guard fell to a *trivial* "space out
the characters" trick at 99.8% ([Cisco](https://blogs.cisco.com/security/bypassing-metas-llama-classifier)).
OWASP keeps prompt injection at #1 and states no single detector suffices.

So Seatbelt should layer cheapest-first and treat detection as attack-surface reduction, not a wall:

| Layer | Mechanism | Latency | Role |
|-------|-----------|---------|------|
| 1 | Deterministic: unicode-normalize, strip zero-width/homoglyphs, signature/regex | <5 ms | kill scripted/obfuscated attacks |
| 2 | Small classifier (Prompt Guard 2 86M/22M, Azure Prompt Shields, Lakera) | ~10–50 ms | catch known injection/jailbreak families |
| 3 | **Spotlighting / datamarking** (delimit + encode untrusted data) | ~0 ms | indirect-injection: Microsoft reports attack success >50% → **<2%** ([arXiv:2403.14720](https://arxiv.org/abs/2403.14720)) |
| 5 | **Capability downgrade** (untrusted content can't trigger tools/egress) | — | the actual guarantee |

This vindicates the design: the firewall's **capability-downgrade** (harness-design §3.3) is the
boundary; the detectors are defense-in-depth in front of it. OpenAI states the same philosophy —
*"design agents so the impact of manipulation is constrained, even if it succeeds"*
([OpenAI, Mar 2026](https://openai.com/index/designing-agents-to-resist-prompt-injection)); Microsoft
pairs Spotlighting + Prompt Shields + capability restriction rather than relying on detection.
**Don't** run detection as the main model judging itself — same injection can target the judge.

### 4.2 How is "the verified end-user" established for sensitive-action authZ? — ✅ Resolved (pattern) / ⚠️ vendor + sensitivity list

**Answer: the host app must hand Seatbelt a delegated identity token tied to the real end-user, and
Seatbelt default-denies any sensitive action lacking one.** The settled building block is
**OAuth 2.0 Token Exchange, [RFC 8693](https://www.rfc-editor.org/rfc/rfc8693.html)**: the agent
exchanges its token for a scoped token naming the user as `sub` and the agent as the `act` (actor)
claim. Effective authority is the *intersection* of user × agent permissions and only ever shrinks
across hops — structurally the anti-confused-deputy property the Meta incident needed. OWASP
**LLM06 "Excessive Agency"** prescribes exactly this: least-privilege scoped tokens + human approval
for impactful actions.

Agent-native "named-agent consent" flows are still **IETF drafts** (`draft-oauth-ai-agents-on-behalf-of-user`,
`draft-klrc-aiagent-auth`, MCP authorization) — promising but not standardized; don't build on them
as a hard dependency yet. **The contract:** Seatbelt requires a verified end-user assertion per
sensitive action; it never treats "the chat session asked nicely" as authorization.
*Flagged for you:* the IdP/vendor and whether step-up is in-band vs out-of-band, and **which actions
count as "sensitive"** (a risk decision) — see §4.7.

### 4.3 What is the "principal" for rate-limiting an anonymous public chatbot? — ✅ Resolved (pattern) / ⚠️ friction tolerance

**Answer: there is no single principal — use a composite key with cost-aware budgets.** No standalone
signal holds: IP collapses under CGNAT/IPv6/VPN, cookies/sessions are trivially reset, visible
CAPTCHAs are largely solved by 2026. Best practice is layered:

- **Edge:** coarse IP + bot-score limits (Cloudflare/AWS WAF) — stops volumetric floods.
- **App:** **cost-aware budgeting** — meter token-weighted "cost units" per session, not requests/sec.
  This is the LLM-specific control that directly answers denial-of-wallet
  ([cost-aware rate limiting](https://handsonarchitects.com/blog/2025/denial-of-wallet-cost-aware-rate-limiting-part-1/)),
  and it weights **output tokens** heavily (harness-design §3.7).
- **Behavioral:** anomaly scoring (all-LLM-fallback traffic, abnormal lengths, rapid sequences).
- **Optional friction:** invisible challenge (Turnstile / reCAPTCHA v3 scoring) before login.

So Seatbelt's "principal" = `composite(IP, session token, optional fingerprint)` carrying a
cost-unit budget. *Flagged for you:* how much friction (challenge/login) you'll impose vs. abuse you'll
tolerate — pure UX/business tradeoff (§4.7).

### 4.4 Policy authoring: how much inferred vs. hand-authored? — ✅ Resolved (pattern) / ⚠️ scope + engine

**Answer: hybrid — infer the mechanics from the tool schema, hand-author the intent.** The tool
schema *is* the resource model: policy-as-code engines map tool names → actions and tool params →
context. **AWS Cedar** (default-deny, forbid-wins, formally verifiable, fast) is purpose-built for
the `permit(principal, action, resource)` shape that tool-call mediation needs; **OPA/Rego** is more
expressive when you need data joins. Amazon **Bedrock AgentCore** already enforces Cedar per
tool-call at its gateway and can even *generate* Cedar from natural language, validated against the
tool schema ([AWS](https://aws.amazon.com/blogs/machine-learning/secure-ai-agents-with-policy-in-amazon-bedrock-agentcore/));
Microsoft's Agent Governance Toolkit runs OPA/Rego **and** Cedar.

- **Inferable (auto-scaffold):** the action list, argument validation, and a default sensitivity
  guess (read-only = low; write/external = high).
- **Irreducibly hand-authored:** the **scope** (what the bot is *for*), data-class sensitivity, which
  actions demand human confirmation, and the egress allowlist. These encode business intent.

A too-hard-to-write policy *is* the real-world failure mode, so: generate a draft from the schema,
make the human edit only the intent fields. *Flagged for you:* the scope definition itself and the
engine choice (§4.7).

### 4.5 Stateful vs. stateless guards? — ✅ Resolved: stateful is required

**Answer: session state is mandatory, or you miss the most effective modern attack class.**
**Crescendo** multi-turn jailbreaks escalate across individually-benign turns and hit ~97–100%
success while every *stateless* per-turn filter passes them
([arXiv:2404.01833](https://arxiv.org/abs/2404.01833)). Most production guardrails are stateless —
that's the gap. **DeepContext** (Feb 2026) tracks intent-drift across turns and scores F1≈0.84 vs.
~0.67 for per-turn Prompt Guard 2 on multi-turn benchmarks, at sub-20 ms
([arXiv:2602.16935](https://arxiv.org/abs/2602.16935)). Minimum viable design: a per-session rolling
**risk accumulator + sliding-window intent score** feeding the Input Guard. *Flagged for you:* the
**data-retention/privacy policy** for that session state (what's stored, for how long) — a
privacy/compliance call (§4.7).

### 4.6 Gateway visibility gap — proxy vs. SDK? — ✅ Resolved: use both, one shared PDP

**Answer: the strong controls require an in-process hook; the gateway covers what it can't.** This is
the settled PDP/PEP (decision-point / enforcement-point) split applied as defense-in-depth:

| Placement | Can enforce | Blind to |
|-----------|-------------|----------|
| **Gateway / proxy PEP** | HTTP auth/headers/IP, rate & cost limits, payload size, prompt/response content, HTTP tool routing, cross-session spend | internal reasoning, in-memory context, **which** reasoning branch triggered a call, in-process (non-HTTP) tool calls |
| **In-process SDK PEP** | full loop state, plan/reasoning, **tool args + provenance before execution**, context-aware decisions, pre-exec budget checks | cross-service enforcement, infra controls (TLS/DDoS/IP) |

Seatbelt's two load-bearing controls — **provenance tagging (H2)** and the **provenance-gated action
mediation (H3)** that asks *"did this tool call originate from untrusted content?"* — are only
answerable **in-process**, because a network gateway can't see the causal link. So: in-process PEP
for H2/H3, gateway PEP for auth/rate/egress/audit, both consulting **one shared PDP** (Cedar/OPA).
Real precedents: AWS AgentCore (Cedar at gateway), AWS Rex (in-process Cedar SDK intercepting every
op), NeMo Guardrails (in-process rails). Pure reverse-proxy mode is a *valid minimal* deployment but
**cannot** deliver the indirect-injection guarantee — that limitation should be stated honestly.

### 4.7 Decisions that need the operator (flagged)

These are genuine product/risk/deployment calls — Seatbelt provides the mechanism, you provide the
intent. (Per project scope, specific vendor *selection* stays out of this ideation; these are the
shapes of the decisions.)

| # | Decision | Why it's yours, not mine | Default if unspecified |
|---|----------|--------------------------|------------------------|
| D1 | **Scope definition** — what the agent is *for* and the off-purpose line | Encodes business intent; the #1 real-world failure mode (§4.4). "Help me write a complaint letter" — in or out? | Deny-by-default to a narrow allowlist of declared intents |
| D2 | **Sensitive-action list** — which tools require step-up auth / human confirm / dual control | A risk-appetite call tied to blast radius (refund $ caps, account changes) (§4.2) | Any write/external/irreversible action → require verified user + confirm |
| D3 | **Identity source & step-up UX** — which IdP, in-band vs out-of-band step-up | Depends on your existing auth stack (§4.2) | RFC 8693 token-exchange contract; deny sensitive actions without a user token |
| D4 | **Anonymous-abuse tolerance** — challenge/login friction vs. openness, per-principal budget caps | Pure UX/business tradeoff (§4.3) | Composite principal + conservative cost-unit budget + invisible challenge |
| D5 | **Policy engine** — Cedar vs. OPA/Rego | Depends on existing investment & policy complexity (§4.4) | Cedar (fits tool-call authZ, verifiable) |
| D6 | **Session-state retention** — what guard state is stored, how long | Privacy/compliance decision (§4.5) | Ephemeral rolling risk score; no raw transcript retention beyond session |
| D7 | **Deployment mode mix** — gateway-only (minimal) vs. gateway + in-process (full) | Constrained by whether you can modify agent code (§4.6) | Both; gateway-only flagged as not covering indirect injection |
| D8 | **Fail-open vs. fail-closed per surface** — availability vs. safety operating point | Domain-specific harm tradeoff (open-questions §1) | Fail-closed on sensitive actions/egress; fail-open-with-log on low-risk reads |

**Update — most of these are now resolved** as generic, configurable mechanisms in
[`configurability.md`](configurability.md): D1 scope is a configurable *rules-agent*, D2 sensitive
actions use a generic resolver (operator override → trusted MCP `ToolAnnotations` → heuristic,
default-sensitive), D4 defaults to open + cost-capped + graduated friction, **D5 = Cedar**, D6
defaults to ephemeral derived state, D7 is **gateway-first** (gateway-only meets the goals for
HTTP/MCP-mediated agents), and D8 is configurable with a graduated default. Only **D3** (which IdP)
remains a genuine operator choice; the contract stays RFC 8693 token exchange.

---

## 5. How we'd know it works (evaluation strategy)

- **Red-team replay corpus.** Encode each `incidents.md` attack (Chevy off-scope, EchoLeak-style
  indirect injection, ForcedLeak egress, Meta confused-deputy, Zoom code-gen) as a test case;
  require Seatbelt to break the chain. Regression-test against it.
- **Benign task suite.** A matched set of *legitimate* on-scope interactions to measure the
  false-positive / over-blocking rate. Track both numbers together — a guard that blocks everything
  scores perfectly on attacks and is useless.
- **Adaptive red-teaming.** Automated/crowd attackers who adapt (mirrors the "3,000 attempts in a
  weekend" reality). Measure time-to-bypass and which control caught it.
- **Channel-coverage audit.** Enumerate every input surface (A–D) and egress path (E) for a given
  deployment; verify a control owns each. Gaps are findings.
- **Decision-quality metrics.** Per control: catch rate, false-positive rate, added latency/cost,
  and "defense-in-depth depth" (how many independent controls an attack must beat).

---

## 6. Final ideation summary

**The problem, in one line:** conversational agents fail because the agent loop has *no consistent
enforcement layer* — the model can't tell instructions from data, so it gets talked off-scope (free
inference), tricked via ingested content (data exfiltration), or manipulated into privileged actions
(account takeover).

**The evidence (`incidents.md`):** 14 sourced incidents cluster into two payoffs — **data
exfiltration**, dominated by *indirect prompt injection + a weak egress channel* (EchoLeak,
ForcedLeak, Slack, Gemini, Meta), and **free inference / denial-of-wallet**, dominated by *plain
scope escape* (Chevy, Chipotle, Zoom, DPD) plus an infra-layer variant (LLMjacking, Ollama). Most
needed no real exploit.

**The model (`threat-model.md`):** 8 attack classes (T1–T8) over 5 trust boundaries, a unifying
kill chain (entry → injection → escalation → action/exfil → channel), and 8 requirements (R1–R8).

**The proposal (`harness-design.md`):** Seatbelt — an *around-the-loop*, operator-owned, declarative
harness with six hook points. The two load-bearing ideas:
1. **Capability downgrade of ingested content** — untrusted text can never, on its own, drive a tool
   call or egress. This structurally breaks the indirect-injection data-leak chain.
2. **Egress as a first-class boundary** — destination allowlists + link/render policy + outbound DLP,
   because every data leak needed a way *out*.
Around those: scope-enforcing input/output guards (behavior, not refusal text), authZ-backed action
mediation (the agent is never the sole authority), per-principal budgets, and pervasive telemetry.

**What makes it a "seatbelt":** one declarative policy enforced identically whether deployed as a
gateway, an SDK middleware, or a sidecar — clip it on without rewriting the agent or swapping the
model.

**The honest caveat:** no layer is a proof. Seatbelt is *defense in depth* — it aims to break the
kill chain at several independent points so one bypass isn't catastrophic, while keeping the bot
useful enough that operators actually leave the belt fastened.
