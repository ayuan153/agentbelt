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

## 4. Open design questions

1. **Where should the Context Firewall's instruction-detection run** — deterministic scanner only,
   a small dedicated classifier, or the main model with a hardened meta-prompt? Each has a different
   cost/evasion profile.
2. **How is "the verified end-user" established** for sensitive-action authZ (R3/R4)? Seatbelt
   depends on an identity signal it doesn't itself produce — what's the contract with the host app?
3. **Per-principal budget identity (R5):** what is a "principal" for an anonymous public chatbot?
   IP? Session? Without a stable principal, denial-of-wallet caps are easy to reset.
4. **Policy authoring ergonomics.** A policy too hard to write won't be written correctly — the
   biggest real-world failure mode. How much can be inferred from the agent's tool list + a few
   declarations vs. hand-authored?
5. **Stateful vs. stateless guards.** Multi-turn attacks demand session memory in the harness; that
   adds storage, privacy, and consistency concerns.
6. **Gateway visibility gap.** In pure reverse-proxy mode, can the harness see enough loop state to
   enforce H2/H3 well, or is an SDK hook required for the strong controls?

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
