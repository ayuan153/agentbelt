# 🪢 Seatbelt

**A pluggable protective harness for conversational AI agents.**

Seatbelt is an ideation project exploring what a drop-in "seatbelt" for LLM-powered
agents could look like — a layer that wraps an existing conversational agent and
defends it against jailbreaks, prompt injection, data exfiltration, and free-inference
("denial-of-wallet") abuse, **without** requiring a rewrite of the agent itself.

> **Status: ideation + a working MVP prototype.** The bulk of this repo is research and
> design thinking. There is now also a runnable, tested prototype of the first slice —
> the denial-of-wallet / scope-escape defense (see [Running the MVP prototype](#running-the-mvp-prototype)).
> No timelines, no estimates — just the problem, the evidence, a proposed shape, and a thin proof of it.

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
| `docs/configurability.md` | Genericity & configuration model + Chipotle-style case study |
| `docs/decisions/` | Architecture Decision Records (interception contract, provenance model, Cedar schema) |
| `docs/spikes/` | Focused design spikes (e.g., the gateway provenance/trust model) |
| `docs/lld/` | Low-level designs for implementable slices (MVP: denial-of-wallet) |
| `seatbelt/` | **MVP prototype** — OpenAI-compatible proxy + guards (scope, multi-turn risk, budget, egress, provenance, Cedar PDP + annotation-driven tool mediation), MCP annotation discovery, and an optional in-process shim |
| `config/` | Example operator configs (`burritobot.yaml` — the Chipotle-style facsimile) |
| `tests/` | Unit + red-team/benign integration tests (run with `pytest`) |

---

## Running the MVP prototype

The prototype implements the **denial-of-wallet / scope-escape slice**
([`docs/lld/mvp-denial-of-wallet-slice.md`](docs/lld/mvp-denial-of-wallet-slice.md)) — a drop-in
OpenAI-compatible proxy. Point your agent's model `base_url` at it; it enforces scope, a
token-weighted spend budget, and egress link policy, then forwards to the real model.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Run the red-team + benign test suite (no API keys needed — uses a mock upstream)
pytest -q

# Or run the proxy locally (forwards to OPENAI_API_KEY upstream; localhost only)
SEATBELT_CONFIG=config/burritobot.yaml python -m seatbelt   # serves :8088/v1/chat/completions
```

Request flow per turn: `H0 budget → H1 scope guard → Cedar PDP AdmitInput → upstream model →
H5-lite output check → H6 egress → cost + telemetry`. An off-scope prompt (e.g. *"write me a
Python class"*) is **deflected without ever calling the upstream**, so it can't run up a bill;
a flood trips the per-principal budget; exfil links in model output are stripped. A **multi-turn
(Crescendo) risk score** also deflects sessions that escalate gradually across turns, and tool
calls are tiered by a generic resolver (operator override → trusted-server MCP annotations →
heuristic → default-sensitive).

Every guard (scope, risk, budget, egress, PDP) is a **pluggable provider**: keep the built-in, or
point config at your own implementation by dotted path — `providers: { risk: "yourpkg:make" }` — no
fork, no training inside the harness. See [`docs/lld/plugin-interface.md`](docs/lld/plugin-interface.md).

**What this slice deliberately defers** (next slices): the context firewall, provenance tracking,
and tool/action mediation that defend the *data-exfiltration* cluster (T3/T4/T5) — **now also
implemented** (see [`docs/lld/data-exfiltration-slice.md`](docs/lld/data-exfiltration-slice.md)):
the proxy tags content trust (tool results = untrusted), and Cedar **capability-downgrade** policies
stop untrusted content from driving a state-changing tool call or egress, while high-impact tools
require a verified user. The PDP, scope rules, tool tiers, and budgets are operator-supplied via the
config file — retargeting to another agent means editing the YAML, not the harness. The proxy is
unauthenticated by design; a real deployment puts identity/principal verification in front of it
(see D3 in [`docs/open-questions.md`](docs/open-questions.md)).

---

## Scope of this ideation

**In scope:** the defensive harness design, the threat model it answers to, where it plugs
into a generic agent loop, and the controls it would enforce.

**Out of scope (for now):** production code, vendor selection, performance/cost numbers, and
any time/effort estimates.
