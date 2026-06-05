# ADR-0006: Naming & distribution (PyPI / npm)

## Status

**Accepted** (2026-06-05) — the project is renamed from **"Seatbelt"** to **`agentbelt`** (import
package, CLI command, and brand). It is distributed on PyPI as **`agentbelt-harness`** because PyPI's
name-similarity guard rejected the exact `agentbelt` distribution (see Context). Because nothing had
been published yet (zero users), the rename is clean: no back-compat aliases for the old import
package, CLI command, or environment variables.

## Context

Before publishing, we had to settle what the project is *called* on public registries and whether
the original name "Seatbelt" was a liability. Findings (verified June 2026):

- **Name collision (moderate–high).** [GhostPack Seatbelt](https://github.com/GhostPack/Seatbelt) is
  a well-known (~4.6k★) **C# Windows host-survey tool** used in offensive security. It is *not* a
  PyPI package, so there was no namespace clash — but it dominates search for "seatbelt security
  tool," and it sits in the *same broad security domain* as us (offensive host-recon vs. defensive
  AI-agent guardrails). The term is not trademarked by either party.
- **PyPI.** Bare `seatbelt` is taken (an abandoned v0.1.4). `agentbelt` returns a 404 (no *exact*
  package), **but PyPI's anti-typosquatting name-similarity guard rejects registering it** ("too
  similar to an existing project") — so the *distribution* is `agentbelt-harness` while the import
  package and CLI stay `agentbelt`. Lesson: 404-availability ≠ registrable; the similarity guard is
  stricter than an exact-name check.
- **npm.** The `@seatbelt` **scope is owned by another user**, so a `@seatbelt/client` package was
  never an option. Unscoped `seatbelt` is also taken (dormant). The bare "Seatbelt" identity was
  therefore already crowded *across* registries, not just on GitHub.

## Decision

**Rebrand to `agentbelt`** across the board:

1. **Python:** import package `agentbelt`, console script `agentbelt`, PyPI distribution
   `agentbelt-harness` (PyPI's similarity guard blocked the exact `agentbelt` dist name; this mirrors
   the earlier `seatbelt-harness` → import `seatbelt` split — `pip install agentbelt-harness`, then
   run `agentbelt`).
2. **Environment & config:** `AGENTBELT_CONFIG` / `AGENTBELT_AUDIT_LOG` / `AGENTBELT_BASE_URL`, and
   the scaffolded config file `agentbelt.yaml`. No `SEATBELT_*` aliases (clean break, pre-release).
3. **TypeScript client:** unscoped **`agentbelt-client`** on npm (the `@agentbelt` scope is not
   required, and `@seatbelt` was unavailable anyway). Its npm publish remains optional/deferred —
   interop works via a `base_url` swap without any client package.
4. **Brand/positioning:** keep the "belt" metaphor ("one belt, any vehicle"); `agentbelt` scopes it
   to the AI-agent domain, which disambiguates cleanly from GhostPack's Windows recon tool.

`agentbelt` was chosen over the alternatives (`agent-seatbelt`, `agentchaperone`, `guardproxy`)
because it best preserves the existing metaphor and identity while being available and unambiguous.

### Alternative considered and rejected

An earlier draft recommended **keeping "Seatbelt" and shipping `seatbelt-harness`**, mitigating the
GhostPack overlap with positioning instead of a rename. Rejected: doing the rename *now*, while the
package is unpublished and has zero users, is essentially free, whereas a later rename (after
adoption) would be costly. Owning a clean, collision-free namespace across PyPI and npm is worth the
one-time churn.

## Consequences

- **Positive:** a clean, distinct, collision-free brand (`agentbelt`) across PyPI (distribution
  `agentbelt-harness`) and npm (`agentbelt-client`); no ongoing confusion with GhostPack Seatbelt.
  Import package and CLI are both `agentbelt`; only the PyPI distribution carries the `-harness`
  suffix (forced by PyPI's name-similarity guard).
- **Cost (paid):** a one-time rename touching the package, tests, config, and all docs (verified by
  the full test suite staying green).
- **Follow-up (maintainer, web-only):** rename the GitHub repository `seatbelt → agentbelt` (GitHub
  auto-redirects old URLs). The PyPI Trusted Publisher is configured under project name
  `agentbelt-harness` (repo `ayuan153/agentbelt`, workflow `release.yml`, environment `pypi`). See
  [RELEASING.md](../RELEASING.md).
