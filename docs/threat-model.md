# Threat Model & Attack Taxonomy

Synthesized from the sourced incidents in [`incidents.md`](incidents.md). The goal here is to
turn ~14 real events into a structured model the Agentbelt harness can be designed against.

---

## 1. What we're protecting (assets)

| Asset | Examples from incidents |
|-------|-------------------------|
| **Confidential data in context** | M365 mailbox/docs (EchoLeak), CRM records (ForcedLeak), private Slack channels |
| **Privileged actions the agent can take** | Account email re-binding / password reset (Meta), refunds (Air Canada), order/commitment actions |
| **The system prompt / policy itself** | Bing "Sydney" leak |
| **Inference budget / compute** | Chevy, Chipotle, Zoom (prompt layer); LLMjacking, Ollama (infra layer) |
| **Brand & legal standing** | DPD rogue output; Air Canada liability ruling |
| **Secrets/credentials reachable by the agent** | API keys, tokens in tools/env (LLMjacking-adjacent) |

---

## 2. Trust boundaries — where untrusted data enters the loop

A conversational agent has **more than one mouth**. Every place external text reaches the model
is an injection surface:

```
        ┌─────────────────────────── AGENT TRUST BOUNDARY ───────────────────────────┐
        │                                                                            │
  (A) direct user turn ─────────────▶                                                │
  (B) retrieved docs / RAG ─────────▶   [ SYSTEM PROMPT + CONTEXT ] ──▶ [ LLM ] ──┐   │
  (C) tool / API results ───────────▶                                          │   │
  (D) ingested content:             ▶                                          ▼   │
      email, calendar, form field,                                      [ TOOL CALLS ]
      web page, log line, file                                          [ ACTIONS    ]──▶ (E) egress
        │                                                                            │
        └────────────────────────────────────────────────────────────────────────────┘
```

- **(A) Direct input** — the user themself is the adversary (jailbreak, scope escape).
- **(B)/(C)/(D) Indirect input** — a *third party* plants instructions in content the agent will
  later read. The current user may be an innocent victim.
- **(E) Egress** — where data/actions leave: rendered links/images, outbound tool calls, written
  records. The dominant exfiltration channel.

**Core insight from the incidents:** the model **cannot reliably tell instructions from data**.
Everything in the context window competes for control. So the boundary can't live *inside* the
prompt — it has to be enforced *around* the loop.

---

## 3. Attack taxonomy

Eight classes, each grounded in real incidents.

### T1 — Scope escape / off-purpose use *(→ free inference)*
The user simply asks the bot to do something outside its job and it complies.
- **Mechanism:** persona override ("you are now…"), or just a plain off-topic request.
- **Payoff:** free general-purpose LLM; embarrassing output.
- **Incidents:** Chevy "$1 car" + Python, Chipotle "free Claude Code", Zoom code-gen.
- **Key lesson:** *refusal text ≠ enforcement* — Zoom's bot refused, then complied.

### T2 — Direct prompt injection / instruction override
Adversarial **direct** input that overrides the configured instructions.
- **Mechanism:** "ignore previous instructions", "print your initial prompt", DAN-style framing.
- **Payoff:** system-prompt/policy extraction; safety bypass.
- **Incidents:** Bing "Sydney" leak; "grandma exploit" (semantic variant that beats keyword filters).

### T3 — Indirect prompt injection (the big one for data leaks)
Instructions hidden in content the agent **ingests**, not typed by the current user.
- **Mechanism:** hidden text in email (EchoLeak), a form's Description field (ForcedLeak), a public
  Slack message pulled via RAG, a calendar-invite description, a log line / `User-Agent` (Gemini).
- **Payoff:** the agent executes attacker instructions with the victim's privileges/context.
- **Incidents:** EchoLeak, ForcedLeak, Slack AI, Gemini Trifecta/Calendar.
- **Key lesson:** zero-click — the victim need only use the assistant normally.

### T4 — Confused-deputy / authorization bypass
The agent holds privileges; natural-language manipulation substitutes for a real authZ check.
- **Mechanism:** talk the agent into performing a sensitive action "on behalf of" someone.
- **Payoff:** account takeover, unauthorized state change.
- **Incidents:** Meta AI support bot re-binding emails / resetting passwords without verification.
- **Key lesson:** the agent must not be the **sole** authority for sensitive actions.

### T5 — Exfiltration-channel abuse
Even with data in context, the attacker needs a way **out**. They reuse a trusted egress path.
- **Mechanism:** auto-rendered Markdown **image/link** that beacons data to an attacker URL;
  a **stale/over-broad allowlisted domain** (ForcedLeak bought an expired allowlisted domain for ~$5).
- **Payoff:** completes the data-leak chain.
- **Incidents:** EchoLeak (CSP/link trick), ForcedLeak (allowlist), Slack AI (rendered link).
- **Key lesson:** **egress allowlisting and link/render policy** is as important as input filtering.

### T6 — Sensitive-data egress / insider leakage
Data leaves the trust boundary *into* an LLM or third party — not always adversarial.
- **Mechanism:** pasting secrets/source into an external model; agent echoing PII/secrets in output.
- **Payoff:** trade-secret / PII exposure.
- **Incidents:** Samsung source-code paste into ChatGPT.
- **Key lesson:** harness must inspect **outbound** content for secrets/PII, both ways.

### T7 — Denial-of-wallet / unbounded consumption
Driving cost up rather than stealing data. Two layers:
- **Prompt layer:** expensive off-scope generations at scale (T1 at volume; Chevy got 3,000+
  attempts in a weekend).
- **Infra layer:** stolen credentials or **unauthenticated endpoints** running inference on the
  victim's compute — LLMjacking ($46K–$100K+/day), exposed Ollama, "Bizarre Bazaar" resale.
- **Maps to:** OWASP LLM "Unbounded Consumption."
- **Key lesson:** scope + per-principal budgets at the prompt layer; auth + network controls at infra.

### T8 — Brand-safety, reputational & liability harm
The output itself is the damage, even with no data loss.
- **Mechanism:** coax offensive/defamatory/false statements, or rely on hallucinated policy.
- **Payoff:** reputational damage; **legal liability** (operator owns the bot's words).
- **Incidents:** DPD rogue poems/swearing; Air Canada hallucinated refund policy (held liable).

---

## 4. Incident → taxonomy map

| Incident | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 |
|----------|----|----|----|----|----|----|----|----|
| Meta AI support → IG takeover | | | ● | ● | | | | ● |
| EchoLeak (M365 Copilot) | | | ● | | ● | | | |
| ForcedLeak (Agentforce) | | | ● | | ● | | | |
| Slack AI private-channel leak | | | ● | | ● | | | |
| Gemini Trifecta / Calendar | | | ● | | ● | | | |
| Samsung code → ChatGPT | | | | | | ● | | ● |
| Bing "Sydney" sysprompt leak | | ● | | | | | | |
| Chevy "$1 car" + code | ● | ● | | | | | ● | ● |
| Dealership wave (Fullpath) | ● | | | | | | ● | ● |
| Chipotle "free Claude Code" | ● | | | | | | ● | |
| Zoom AI Companion code-gen | ● | | | | | | ● | |
| DPD rogue chatbot | ● | ● | | | | | | ● |
| LLMjacking | | | | | | | ● | |
| Bizarre Bazaar / Ollama | | | | | | | ● | |
| Air Canada (context) | | | | | | | | ● |
| Grandma exploit (technique) | | ● | | | | | | |

**Reading the map:** the data-leak cluster (rows 1–5) is overwhelmingly **T3 + T5** — indirect
injection paired with an egress channel. The free-inference cluster (rows 8–12) is **T1 + T7**.
Defending both clusters well requires controls at **three** points: input, action, and egress.

---

## 5. Attack lifecycle (kill chain)

A unifying chain Agentbelt's controls should be able to break at multiple links:

```
  1. ENTRY        2. INJECTION/        3. ESCALATION       4. ACTION / EXFIL     5. CHANNEL OUT
  pick a surface  SCOPE-BREAK          gain control        invoke tool / leak    deliver to attacker
  (A user turn,   (override persona    (use victim creds   (read CRM, reset      (rendered link,
   D ingested     or inject via         / context, ignore   account, write code)  allowlisted domain,
   content)        ingested text)       policy)                                   outbound API)
       │                │                    │                    │                     │
   ┌───┴────┐      ┌────┴─────┐         ┌────┴─────┐         ┌─────┴─────┐         ┌─────┴─────┐
   │ INPUT  │      │ INPUT    │         │ POLICY/  │         │ TOOL /    │         │ EGRESS    │
   │ GUARD  │      │ GUARD +  │         │ IDENTITY │         │ ACTION    │         │ GUARD     │
   │        │      │ data/    │         │ ENGINE   │         │ MEDIATION │         │           │
   │        │      │ instr.   │         │ (re-auth │         │ (allow-   │         │ (dest +   │
   │        │      │ separation│        │ sensitive)│        │ list,     │         │ render +  │
   │        │      │          │         │          │         │ confirm)  │         │ DLP)      │
   └────────┘      └──────────┘         └──────────┘         └───────────┘         └───────────┘
```

**Defense-in-depth principle:** no single control is reliable (filters get bypassed, models get
talked around). Break the chain at as many links as possible so one failure isn't fatal.

---

## 6. Attacker profiles

| Profile | Motivation | Sophistication | Representative incident |
|---------|------------|----------------|-------------------------|
| **Curious/prankster crowd** | Lulz, clout | Low; copies viral prompts | Chevy, DPD, Chipotle |
| **Cost parasite** | Free compute | Low–medium | Zoom, dealership wave |
| **Criminal operator** | Money, account theft, resale | Medium–high | Meta takeover, LLMjacking, Bizarre Bazaar |
| **Security researcher** | Disclosure | High | EchoLeak, ForcedLeak, Slack, Gemini |
| **Innocent insider** | Just trying to get work done | N/A | Samsung |

Design implication: defend against **mass low-skill probing** (it arrives by the thousands within
hours of a public flaw) *and* **targeted indirect injection** (zero-click, victim is innocent).

---

## 7. Requirements this implies for the harness

Distilled into what [`harness-design.md`](harness-design.md) must answer:

- **R1 — Enforce scope, not just refuse.** Constrain *behavior/output*, not just block jailbreak
  strings (counters T1; Zoom lesson).
- **R2 — Treat all ingested content as data, never instructions.** Separate/quarantine untrusted
  content from the instruction channel (counters T3).
- **R3 — Mediate tool calls & actions.** Allowlist tools, require real authZ / human confirmation
  for sensitive actions; the agent is never the sole authority (counters T4).
- **R4 — Control egress.** Strict destination allowlists, link/image render policy, outbound DLP
  for secrets/PII (counters T5, T6).
- **R5 — Budget & rate-limit per principal.** Cap spend/turns; detect off-scope generation volume
  (counters T7 prompt layer).
- **R6 — Protect the policy itself.** Don't rely on a secret system prompt as a boundary; assume
  it leaks (counters T2).
- **R7 — Observe & detect.** Telemetry, anomaly detection, and audit so mass probing and novel
  attacks are caught and reviewable (counters all; supports liability defense, T8).
- **R8 — Fail safe & be operator-owned.** Defaults deny on uncertainty; the operator, not the
  model, owns policy (counters T8 liability).
