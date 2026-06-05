# ADR-0001: Interception Contract & First Integration Target

## Status

**Accepted**

## Context

Agentbelt needs a concrete integration surface that lets it observe and mediate all
communication between an agent and its model provider, as well as between the agent
and its tools — without requiring in-process instrumentation of the host application.

The [threat model](../threat-model.md) (T1–T8) and [requirements](../threat-model.md)
(R1–R8) demand visibility into the full prompt context (messages, tool definitions),
model responses (assistant text, tool_calls, usage), and tool invocations. The
[harness design](../harness-design.md) defines hook points H0–H6 that must be covered.

The dominant agent architecture today communicates with model providers and tools over
HTTP. An HTTP reverse-proxy approach requires **zero in-process code** from the builder.

## Decision

Agentbelt's first concrete form is an **HTTP reverse proxy** exposing two surfaces:

### 1. Model Proxy

- Endpoint: `POST /v1/chat/completions` (OpenAI-compatible, including streaming via SSE).
- The builder points their agent's model `base_url` at Agentbelt.
- Agentbelt inspects the full request (`messages[]`, `tools[]`, `model`, params) and
  the full response (assistant message, `tool_calls`, `usage`).
- Hook mapping: **H1** (input guard) on request, **H5** (output guard) on response.

### 2. Tool / MCP Proxy

- Agentbelt proxies MCP servers (Streamable HTTP transport) and/or plain HTTP tool
  endpoints, intercepting the `tools/call` method.
- Hook mapping: **H3** (tool/action mediation) on every `tools/call`, **H6** (egress
  guard) on outbound network calls the tool makes.

### Cross-cutting

- **H0** (budget + telemetry) wraps both surfaces.
- **Session correlation**: via an `X-Agentbelt-Session` request header. Fallback when
  absent: composite principal hash of `IP + token + optional fingerprint`.

### Out of first scope

- Anthropic Messages API adapter.
- Framework SDK shims (e.g., LangChain callback injection).
- The optional in-process shim (described in [harness-design](../harness-design.md)).

## Consequences

### Benefits

- Zero integration code for builders already using an OpenAI-compatible SDK.
- All hook points (H0–H6) are reachable from the proxy without agent modifications.
- Streaming support means latency overhead is limited to per-chunk inspection.
- The MCP proxy path covers the emerging open-tool standard natively.

### Limitations / residual gaps

- **Opacity to in-process state**: the proxy cannot observe the model's private
  chain-of-thought or agent-internal memory that isn't sent to the model API. Full
  causal provenance requires the future in-process shim.
- **Non-HTTP transports**: agents using gRPC, stdio-based MCP, or local function calls
  are not covered until additional adapters are built.
- **Session correlation fragility**: without the explicit `X-Agentbelt-Session` header,
  the composite-hash fallback may misattribute requests when clients share IPs/tokens.
- **Vendor drift**: if the OpenAI API introduces breaking changes, the proxy must be
  updated; mitigated by targeting the stable `/v1/` surface.

## Alternatives Considered

| Alternative | Why not chosen (first target) |
|-------------|-------------------------------|
| Anthropic Messages API proxy | Smaller ecosystem share; planned as second adapter |
| In-process SDK shim (middleware) | Requires per-framework integration; higher adoption friction |
| eBPF / network-level interception | Too low-level; can't parse structured messages easily |
| WASM plugin inside the agent runtime | Non-standard; limited language support today |

---

*Related:* [harness-design.md](../harness-design.md), [configurability.md](../configurability.md),
[threat-model.md](../threat-model.md).
