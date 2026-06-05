# Distribution & Adoption Roadmap

How Agentbelt gets from "clone and run" to "a dev plays with it in 60 seconds and adopts it." Phased
by priority, not by date. ✅ = shipped.

## The on-ramp we're optimizing for

```
pip install agentbelt              # one install
agentbelt init                     # scaffold a config
# edit agentbelt.yaml
agentbelt check                    # validate, fail-fast
agentbelt serve                    # OpenAI-compatible proxy on :8088
# point your agent's base_url at http://localhost:8088/v1  — done, no agent code change
```

The proxy is **OpenAI-compatible HTTP**, so *any* language's agent (Python, JS/TS, Go, …) adopts it
with a one-line `base_url` change — no SDK required for interop.

---

## Phase 0 — Local dev experience  ✅ (shipped)

- ✅ `pip install` packaging (`pyproject.toml`, `agentbelt`) with an `agentbelt` console script.
- ✅ CLI: `init` (scaffold), `check` (fail-fast validation of config + every provider), `serve`.
- ✅ Pluggable providers (scope/risk/budget/egress/pdp/provenance) by built-in name or `module:factory`.
- ✅ Test suite runnable with zero API keys (mock upstream).

## Phase 1 — Publish & frictionless install

- **Publish to PyPI** so `pip install agentbelt` works for everyone (build with `python -m build`,
  upload via Trusted Publishing). Tag releases; semantic versioning. See [RELEASING.md](RELEASING.md).
- **`pipx` / `uvx` support** so `uvx agentbelt serve` runs it with zero env setup.
- **Container image** (`ghcr.io/.../agentbelt`) for `docker run` / sidecar deployment.
- A few **ready-made example configs** (support bot, RAG assistant, coding assistant) shipped in the
  package and listed by `agentbelt init --template <name>`.

## Phase 2 — Config ergonomics (SOTA configurability)

- **Interactive `agentbelt init`** wizard: prompt for purpose/scope/tools, generate a tuned config.
- **JSON Schema for the config** → editor autocomplete + inline validation in VS Code; `agentbelt
  check` already validates semantically, schema covers shape.
- ✅ **`agentbelt test`**: replays a bundled red-team corpus (the `incidents.md` attacks) against the
  user's config and reports which are blocked — a confidence check before going live. Exits non-zero
  if any attack is allowed, so it doubles as a CI gate. See
  [LLD](lld/dash-and-test-commands.md).
- Config **profiles / layering** (base + per-env overrides) and secret references for upstream keys.

## Phase 3 — Pluggability into local CLI agents & frameworks

- **Framework adapters** packaged as thin extras: LangChain / LlamaIndex / OpenAI-Agents drop-ins
  that set `base_url` and (optionally) wire the in-process shim's `ingest`/`guard_tool` for
  per-decision provenance.
- **In-process shim as decorators**: `@agentbelt.tool(tier="high")` around a tool fn, so embedding
  the harness is a one-import change for Python agents.
- **Optional npm package** (`agentbelt-client`): a thin TypeScript client + CLI wrapper for
  Node/Deno agents. *Interop already works without it* (base_url) — npm is purely DX sugar (typed
  config, `npx agentbelt serve` via a bundled runtime, shim helpers).
- MCP gateway mode: front MCP servers directly (discovery already implemented) so tool traffic is
  mediated without per-request annotations.

## Phase 4 — Observability & UI (ease of adoption)

- ✅ **`agentbelt dash`** (snapshot): a local `rich` summary over the audit-log JSONL — decisions,
  per-principal spend, recent blocks. Zero infra. A live-tail TUI (textual) and risk-score columns
  remain future work. See [LLD](lld/dash-and-test-commands.md).
- A small **web dashboard** (read-only over the telemetry stream) for teams; export to OTel/SIEM.
- **Config editor UI**: visualize scope/tiers/egress and preview a decision against a sample turn.

## Phase 5 — Production hardening

- **Proxy authentication / principal verification** (the documented D3 gap) — the harness assumes
  identity in front of it; provide first-class hooks/middleware.
- **Shared session store** (Redis) so budget + multi-turn risk + provenance work across replicas.
- **Streaming** responses (SSE) end-to-end through the guards.
- Performance: cheap-checks-first ordering, Cedar policy caching, async upstream.

## Cross-cutting: quality & community

- **CI** (GitHub Actions): tests + lint (ruff) + build on every PR; coverage badge; release on tag.
- `CONTRIBUTING.md`, issue/PR templates, a `good-first-issue` set (new built-in guards, adapters).
- A short **docs site** (mkdocs-material) from `docs/`.
- Security policy (`SECURITY.md`) + responsible-disclosure contact.

---

## Open product questions

- **UI surface**: TUI-first (zero infra, dev-friendly) vs. a hosted web dashboard (team-friendly)?
  Recommendation: ship the TUI first; it's the cheapest path to "I can see it working."
- **npm scope**: thin client only, or a full Node-native re-implementation of the guards? The proxy
  makes a re-implementation unnecessary; recommend the thin client unless a pure-JS in-process shim
  is in demand.
- **Naming**: ✅ *Resolved* — the project was originally "Seatbelt," which collided with GhostPack's
  well-known offensive-security tool **Seatbelt** (same security domain). We rebranded to
  **`agentbelt`**, which is free on PyPI and keeps the "belt" metaphor while scoping it to AI agents.
  See [ADR-0006](decisions/ADR-0006-naming-and-distribution.md).
- **Default upstream**: stay OpenAI-compatible only, or add native Anthropic Messages adapter
  (ADR-0001 deferred it). Most providers expose OpenAI-compatible endpoints, so this is low urgency.
