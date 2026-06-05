# LLD: `agentbelt test` and `agentbelt dash` — confidence & observability commands

Two read-only CLI surfaces that turn the harness from "trust me, it defends you" into something a
developer can *see* working before adoption:

- **`agentbelt test`** — replays a bundled red-team corpus against the operator's own config and
  reports which known attacks are blocked. This is the roadmap **Phase 2** confidence check.
- **`agentbelt dash`** — renders the audit-log JSONL as a compact terminal summary (decisions,
  per-principal spend, recent blocks). This is the roadmap **Phase 4** observability surface.

Both are deliberately thin glue over engines that already exist and are independently tested
(`agentbelt/redteam.py`, `agentbelt/dash.py`); this slice only wires them into the CLI. The engines
were left untouched.

## Where they sit in the CLI

`main()` (in `agentbelt/cli.py`) dispatches by subcommand. The key distinction is **what each command
needs**:

| Command | Needs a valid config? | Needs the audit log? | Exit code semantics |
|---------|----------------------|----------------------|---------------------|
| `init`  | no (writes one)      | no                   | 0 ok / 1 if file exists |
| `dash`  | **no**               | **yes**              | 0 ok / 1 if no/absent log |
| `check` | yes                  | no                   | 0 ok / 1 on errors |
| `test`  | yes                  | no                   | **0 all blocked / 1 any allowed** |
| `serve` | yes                  | no                   | runs until stopped |

`dash` returns early — *before* the config-load/validate block — because it reads only the audit
log and must work even when no `agentbelt.yaml` is present (e.g. inspecting logs on a different box).
`test` runs *after* validation: red-teaming an invalid config is meaningless, so an invalid config
exits 1 before the corpus runs.

## `agentbelt test`

```
agentbelt test          # AGENTBELT_CONFIG or ./agentbelt.yaml
```

Flow (`_cmd_test(cfg)`):

1. `redteam.run(cfg)` builds an in-process app per attack (mock upstream — **no network, no API
   keys**) and fires the corpus through the real guard stack.
2. Results render as a `rich` table: attack name, mapped incident, `BLOCKED`/`ALLOWED` + detail.
3. `redteam.summary(results)` → `(blocked, total)`; exit `0` iff `blocked == total`, else `1`.

The non-zero exit on any allowed attack is the important contract: it makes `agentbelt test`
**CI-usable** as a regression gate — a config change that opens a hole fails the build.

Each corpus entry maps to a documented real-world incident (Chevrolet free-inference, Bing "Sydney"
prompt extraction, off-purpose use, DPD brand-safety, EchoLeak/Slack indirect tool injection,
Samsung-style data egress, and a multi-turn Crescendo ramp — see [`docs/incidents.md`](../incidents.md)),
so a green run is a concrete, sourced claim rather than a vague assurance.

## `agentbelt dash`

```
agentbelt dash [path]   # path arg, else $AGENTBELT_AUDIT_LOG
```

Flow (`_cmd_dash(path)`):

1. Resolve the log path: explicit arg → `AGENTBELT_AUDIT_LOG` env → error (exit 1) with a hint to set
   the var when running `serve`.
2. Missing file → exit 1 with a hint (the proxy only writes the log when `AGENTBELT_AUDIT_LOG` is
   set; see below).
3. `dash.render(path)` loads + aggregates (tolerant of blank/garbled lines) and prints summary,
   by-decision, top-principals-by-spend, and recent-blocks tables. It returns the aggregate dict, so
   the engine stays testable without parsing stdout.

It is a **snapshot, not a live tail** — zero infra, no watch loop. A live TUI remains a future
Phase-4 option (`open-questions.md`: TUI vs. hosted dashboard).

### The audit-log contract

`dash` reads what the telemetry sink writes. The sink (`agentbelt/telemetry.py`) appends one JSON
object per decision **only when `AGENTBELT_AUDIT_LOG` is set** (wired in `create_app`); otherwise it
keeps just the in-memory ring and `dash` has nothing to read. Fields consumed: `session_id`,
`principal_key`, `action`, `decision` (`allow|deflect|throttle|deny|partial_deny`), `reasons`,
`scope_verdict`, `cost_used`, `extra`. "Blocked" = any decision in
`{deflect, throttle, deny, partial_deny}`.

## Why thin glue (design choice)

The engines return structured data (`AttackResult`, the aggregate dict) and the CLI owns only
presentation + process exit codes. This keeps the decision logic testable in isolation and lets the
same engines back a future web dashboard or a programmatic API without a CLI rewrite — consistent
with the deployment-mode separation in
[ADR-0001](../decisions/ADR-0001-interception-contract.md).

## Honest limitations

- **`test` is only as good as its corpus.** Seven attacks spanning scope (H1), multi-turn risk
  (H1+), tool mediation (H3), and egress (H6) is a meaningful smoke test, not a proof of coverage; a
  green run means "blocks these known patterns," not "unbreakable." The corpus is meant to keep
  growing (a good first-issue area). Denial-of-wallet (budget, H0) is deliberately excluded from the
  must-block set because its blocking is volume/config-dependent and would make the gate flaky — it
  is covered directly in `tests/test_budget.py`.
- **`test` uses mock upstreams**, so it exercises the *guard* decisions, not real model behavior —
  which is the point (deterministic, key-free, fast), but it does not catch model-side regressions.
- **`dash` is a point-in-time snapshot** over a local file; it has no retention, rotation, or
  multi-replica aggregation (the shared-store work is Phase 5). Provenance in the proxy log is the
  gateway approximation, not the in-process shim's per-decision fidelity.

## Tests

`tests/test_cli.py` covers the wiring (engines are covered by `test_redteam.py` / `test_dash.py`):

- `test`: strict burrito config → exit 0 (all blocked, real engine); a monkeypatched allowed result
  → exit 1; invalid config → exit 1 before the corpus runs.
- `dash`: renders from a path arg → 0; resolves from `AGENTBELT_AUDIT_LOG` → 0; no path → 1; missing
  file → 1.
