# LLD: Optional In-Process Shim (cooperative PEP)

The optional in-process Policy Enforcement Point anticipated by
[ADR-0001](../decisions/ADR-0001-interception-contract.md) (deployment modes) and
[ADR-0002](../decisions/ADR-0002-provenance-model.md) (provenance). It narrows the gateway's
provenance **approximation** by letting the agent report, in-process, the trust of the content it
actually consumed — so tool mediation uses *agent-reported causal* provenance rather than the
gateway's "any untrusted content in the messages array this turn" heuristic.

## API — `agentbelt/shim.py`

```python
shim = AgentbeltShim(tool_tiers, trusted_servers)   # holds one CedarPDP, shares the same policies
shim.begin_turn()                                  # reset per-turn taint
shim.ingest(trust)                                 # agent reports each consumed item: 'trusted'|'user'|'untrusted'
decision = shim.guard_tool(name, annotations=?, server=?, user_verified=?, human_confirmed=?)
```

`guard_tool` resolves the tier via the same `resolve_tier` precedence, sets
`provenance_max_trust = "untrusted"` iff any ingested item this turn was untrusted, and calls the
**same `CedarPDP`** as the gateway. So the policy is identical across deployment modes — only the
*provenance signal source* differs.

## How an agent uses it

```python
shim.begin_turn()
for item in retrieved_context:
    shim.ingest(item.trust)          # e.g. RAG doc -> "untrusted", user turn -> "user"
if shim.guard_tool("issue_refund", user_verified=auth.ok).effect == "allow":
    issue_refund(...)
```

## Why this is finer-grained than the gateway

| | Gateway (proxy) | In-process shim |
|---|-----------------|-----------------|
| Provenance source | hashes of the `messages[]` array; "new untrusted content this turn" | the agent's *actual* declaration of what it consumed for *this* decision |
| Granularity | per-turn | per-decision |
| Plug-in cost | zero (base_url swap) | agent calls `ingest`/`guard_tool` |

## Honest limitations

- **Cooperative, not automatic.** The shim relies on the agent calling `ingest`/`guard_tool`
  truthfully; it does **not** do automatic taint propagation through the agent's variables. True
  language-level taint tracking is out of scope. It is *finer-grained* than the gateway, not a
  formal guarantee.
- Shares the gateway's Cedar policies, so the capability-downgrade / confused-deputy semantics are
  identical — only provenance fidelity improves.
- Best used **with** the gateway (defense in depth): gateway for the controls that need no code
  change, shim where the agent runs local tools or wants per-decision provenance.

## Tests

`tests/test_shim.py`: untrusted ingest blocks a medium tool (capability-downgrade); `begin_turn`
reset re-allows it; a high-tier tool needs `user_verified` + `human_confirmed`; a low-tier tool is
allowed even after an untrusted ingest. Verified against real cedarpy.
