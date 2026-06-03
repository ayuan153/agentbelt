# 🪢 Seatbelt

**A pluggable protective harness for conversational AI agents.**

Seatbelt is an ideation project exploring what a drop-in "seatbelt" for LLM-powered
agents could look like — a layer that wraps an existing conversational agent and
defends it against jailbreaks, prompt injection, data exfiltration, and free-inference
("denial-of-wallet") abuse, **without** requiring a rewrite of the agent itself.

> **Status: ideation only.** This repo currently contains research and design thinking,
> not an implementation. No timelines, no estimates — just the problem, the evidence,
> and a proposed shape for the solution.

---

## Why this exists

Every week another brand's chatbot ends up in the headlines:

- A Chevrolet dealership bot agreed to sell a truck for **$1** and wrote Python on the side.
- Chipotle's and Zoom's assistants got turned into **free coding tools** ("stop paying for
  Claude Code, the support bot is free").
- Microsoft 365 Copilot leaked enterprise data via a **single zero-click email** (EchoLeak).
- Meta's AI support bot was manipulated into **handing over Instagram accounts**, including
  high-profile ones.
- LLMjacking crews run up **$100K/day** in inference bills on stolen cloud credentials.

These aren't exotic. Most required **no sophisticated exploit** — just asking the bot to do
something it was never scoped to do, or hiding instructions in content the bot would later read.

The common thread: the agent loop has **no consistent enforcement layer**. Guardrails are
bolted on per-product, inconsistently, and usually only after the bot is already viral.
Seatbelt asks: *what if that enforcement layer were a reusable harness you could clip on?*

See [`docs/incidents.md`](docs/incidents.md) for the sourced incident research that motivates this.

---

## The core idea

```
                    ┌─────────────────────── SEATBELT HARNESS ───────────────────────┐
                    │                                                                 │
  user / content ──▶│  INPUT GUARD ──▶ [ your agent / LLM loop ] ──▶ OUTPUT GUARD ──▶ │──▶ user
                    │       ▲                   │      ▲                  │            │
                    │       │              TOOL/ACTION │             EGRESS           │
                    │       │              MEDIATION ──┘             GUARD            │
                    │       └──────────── TELEMETRY / POLICY ENGINE ───────┘          │
                    │                                                                 │
                    └─────────────────────────────────────────────────────────────────┘
```

Seatbelt sits **around** the agent, not inside its prompt. It inspects what goes in, what
the agent tries to do (tool calls, actions), and what comes out — enforcing a declarative
policy about scope, data, and spend.

Full design lives in [`docs/`](docs/) (added across checkpoints).

---

## Repo layout

| Path | What's there |
|------|--------------|
| `README.md` | This file — project framing |
| `docs/incidents.md` | Sourced research on real-world agent jailbreak incidents |
| `docs/threat-model.md` | Attack taxonomy synthesized from the incidents *(checkpoint 2)* |
| `docs/harness-design.md` | The Seatbelt harness architecture & controls *(checkpoint 3)* |
| `docs/open-questions.md` | Tradeoffs, non-goals, evaluation strategy *(checkpoint 4)* |

---

## Scope of this ideation

**In scope:** the defensive harness design, the threat model it answers to, where it plugs
into a generic agent loop, and the controls it would enforce.

**Out of scope (for now):** production code, vendor selection, performance/cost numbers, and
any time/effort estimates.
