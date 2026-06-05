# ADR-0006: Naming & distribution (PyPI / npm)

## Status

**Proposed** — the recommendation below is actionable now for the Python package; the "do not
rebrand" call awaits the maintainer's explicit acceptance before we treat it as final, because a
later rebrand gets more expensive the longer we wait.

## Context

Before publishing, we have to settle what the project is *called* on public registries and whether
the name "Seatbelt" is a liability. Findings (verified June 2026 — see sources in
[`docs/roadmap.md`](../roadmap.md) open questions and the research below):

- **Name collision (moderate–high).** [GhostPack Seatbelt](https://github.com/GhostPack/Seatbelt) is
  a well-known (~4.6k★) **C# Windows host-survey tool** used in offensive security. It is *not* a
  PyPI package, so there is **no namespace clash** — but it dominates search for "seatbelt security
  tool," and it sits in the *same broad security domain* as us (offensive host-recon vs. defensive
  AI-agent guardrails). The term is not trademarked by either party.
- **PyPI.** `seatbelt-harness` is **available**; bare `seatbelt` is **taken** (an abandoned v0.1.4).
  Distinct alternatives that are free: `agentbelt`, `agent-seatbelt`, `agentchaperone`, `guardproxy`.
  Taken: `agent-harness`, `bulwark`, `chaperone`, `beltway`.
- **npm.** The `@seatbelt` **scope is owned by another user**, so our TypeScript client cannot be
  published as `@seatbelt/client`. Unscoped `seatbelt` is also taken (dormant, 9 years). So the bare
  "Seatbelt" identity is already crowded *across* registries, not just on GitHub.

The PyPI distribution name has been `seatbelt-harness` since the packaging commit; publish-prep does
not depend on resolving the brand question.

## Decision

**Keep the name "Seatbelt" and ship the Python package as `seatbelt-harness`. Do not rebrand.**

1. **Python (primary artifact): `seatbelt-harness`.** It is available, descriptive, and the
   `-harness` suffix is sufficient differentiation: a PyPI Python library for *AI-agent* defense is
   not going to be confused with a C#/Windows offensive-recon binary by the audience that installs
   it. The "one belt, any vehicle" metaphor is load-bearing across the existing docs and worth
   keeping.
2. **Positioning over renaming.** Mitigate the GhostPack overlap in *copy*, not by churn: always
   introduce the project as **"Seatbelt — a protective harness for AI agents"** (the tagline already
   does this), so the defensive/AI framing is immediate. The two tools are trivially distinguishable
   once described.
3. **Fix the npm client name (the one real blocker).** `@seatbelt/client` is unpublishable. Rename
   the TypeScript client to the unscoped **`seatbelt-harness-client`** (matching the Python dist), or
   defer its npm publish entirely — interop already works via a `base_url` swap, so the client is
   pure DX sugar (Phase 3) and is *not* on the critical path for the Python release.

### Alternative considered (runner-up): rebrand to `agentbelt`

If the maintainer decides the same-domain collision is unacceptable for long-term brand clarity, the
recommended rebrand target is **`agentbelt`**: it preserves the "belt" metaphor, scopes it to the AI
domain (disambiguating from GhostPack), is **available on PyPI**, and likely frees an `@agentbelt`
npm scope (verify before committing). This is the only option that buys a clean *cross-registry*
namespace. It is the runner-up purely on cost: it touches every doc, the README identity, and the
GitHub repo URL, for a confusion risk we judge manageable today. Revisit if/when the project seeks
broader public adoption.

## Consequences

- **Positive:** unblocks the v0.1.0 publish immediately with zero rename churn; preserves existing
  brand equity and documentation; the dist name already encodes the "harness" framing.
- **Negative / accepted risk:** "Seatbelt" remains ambiguous in web search against GhostPack, and we
  do **not** own the bare name on PyPI/npm or the `@seatbelt` npm scope. We accept this for now and
  lean on positioning + the `-harness` suffix.
- **Follow-ups:** (a) rename `clients/typescript` package to `seatbelt-harness-client` or mark its
  npm publish deferred; (b) if a rebrand is ever chosen, do it *before* the project gains adoption —
  `agentbelt` is the front-runner and should be reserved on PyPI/npm proactively if there's any
  intent to switch.

## Why this is reversible enough

Nothing here claims the bare `seatbelt` name (already taken) or burns a rename we can't undo. The
`seatbelt-harness` dist name can coexist with a future `agentbelt` rebrand (publish under both, or
alias), so choosing to ship now does not foreclose the runner-up later.
