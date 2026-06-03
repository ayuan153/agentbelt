"""Seatbelt model proxy (ADR-0001) — OpenAI-compatible /v1/chat/completions.

Wires the MVP denial-of-wallet slice end to end
(docs/lld/mvp-denial-of-wallet-slice.md):

    client -> H0 budget admission -> H1 scope guard -> Cedar PDP AdmitInput
           -> upstream model (mockable) -> H5-lite output scope check
           -> H6 egress link-strip -> H0 record cost + telemetry -> client

Graduated fail posture (D8): budget/egress fail CLOSED; scope check fails
OPEN-with-alert. A *confident* offscope verdict is a deflection, not a failure.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import replace
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from seatbelt.mcp_discovery import discover_annotations
from seatbelt.plugins import resolve as resolve_provider
from seatbelt.provenance import ProvenanceTracker
from seatbelt.telemetry import AuditSink
from seatbelt.tooltier import resolve_tier
from seatbelt.types import AuthzRequest, Message, SeatbeltConfig, Session, TelemetryRecord

Upstream = Callable[[dict], dict]

_BLOCKED_ACTION_MSG = "I'm not able to complete that action."


def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _completion(content: str, usage: dict | None = None) -> dict:
    return {
        "id": f"seatbelt-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _default_upstream(base_url: str) -> Upstream:
    import httpx

    def call(body: dict) -> dict:
        key = os.environ.get("OPENAI_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        r = httpx.post(f"{base_url}/v1/chat/completions", json=body, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json()

    return call


def create_app(cfg: SeatbeltConfig, upstream: Upstream | None = None, mcp_fetch=None) -> FastAPI:
    app = FastAPI(title="Seatbelt", version="0.1.0")
    p = cfg.providers
    # Each guard is resolved via a provider (built-in name or "module:factory"). See seatbelt/plugins.py.
    scope_guard = resolve_provider("scope", p.get("scope"), cfg)
    budget = resolve_provider("budget", p.get("budget"), cfg)
    egress = resolve_provider("egress", p.get("egress"), cfg)
    pdp = resolve_provider("pdp", p.get("pdp"), cfg)
    risk = resolve_provider("risk", p.get("risk") or cfg.risk.scorer, cfg)  # risk.scorer kept for back-compat
    provenance = ProvenanceTracker()
    # Optional MCP annotation discovery from trusted servers (no startup network unless fetch given).
    registry = discover_annotations(cfg.trusted_tool_servers, fetch=mcp_fetch) if mcp_fetch else {}
    audit = AuditSink()
    sessions: dict[str, Session] = {}
    up = upstream or _default_upstream(cfg.upstream_base_url)

    app.state.audit = audit  # exposed for tests/ops

    def get_session(req: Request) -> Session:
        key = req.headers.get("X-Seatbelt-Session") or (req.client.host if req.client else "anon")
        s = sessions.get(key)
        if s is None:
            s = Session(id=key, principal_key=key)
            sessions[key] = s
        return s

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> JSONResponse:
        body = await request.json()
        session = get_session(request)
        msgs = [Message(m.get("role", ""), m.get("content", "") or "") for m in body.get("messages", [])]
        last_user = next((m.content for m in reversed(msgs) if m.role == "user"), "")

        # --- H0: budget admission (fail-closed) ---
        br = budget.check(session, cfg.budget)
        if not br.allowed:
            audit.emit(TelemetryRecord(session.id, session.principal_key, "AdmitInput",
                                       "throttle", [br.reason], cost_used=session.cost_used))
            return JSONResponse(status_code=429, content={"error": {"message": br.reason, "type": "rate_limit"}})

        # --- H1: scope guard (fail-open-with-alert on error) ---
        try:
            verdict = scope_guard.evaluate(msgs, cfg.scope).verdict
        except Exception as e:  # graduated fail posture: scope_check = open_with_alert
            verdict = "unknown"
            audit.emit(TelemetryRecord(session.id, session.principal_key, "ScopeGuard",
                                       "error_open", [f"scope_error: {e}"], scope_verdict="unknown"))

        # --- H1+: multi-turn (Crescendo) risk -> escalate a borderline turn to a deflect ---
        rr = risk.score_turn(session, last_user, verdict, cfg.risk)
        effective_verdict = "offscope" if rr.tripped else verdict

        # --- Cedar PDP: AdmitInput ---
        decision = pdp.decide(AuthzRequest(
            principal_id=session.id, action="AdmitInput",
            resource_type="Seatbelt::Answer", resource_id="answer",
            context={"scope_verdict": effective_verdict, "cost_used": int(session.cost_used),
                     "budget_remaining": int(br.budget_remaining)},
        ))
        if decision.effect == "deny":
            # Confident offscope (or risk-tripped) -> deflect WITHOUT calling upstream.
            reasons = decision.reasons + ([f"multiturn_risk:{rr.score:.2f}"] if rr.tripped else [])
            budget.record(session, _est_tokens(last_user), _est_tokens(cfg.scope.deflect_message), cfg.budget)
            audit.emit(TelemetryRecord(session.id, session.principal_key, "AdmitInput",
                                       "deflect", reasons, scope_verdict=effective_verdict,
                                       cost_used=session.cost_used,
                                       extra={"risk_score": round(rr.score, 3), "risk_tripped": rr.tripped}))
            return JSONResponse(content=_completion(cfg.scope.deflect_message))

        # --- H2: provenance of this turn (degrades to "untrusted" if NEW untrusted content) ---
        turn_trust = provenance.turn_trust(session, body.get("messages", []))

        # --- upstream model call ---
        resp = up(body)
        message = (resp.get("choices", [{}])[0].get("message", {})) or {}
        usage = resp.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or _est_tokens(last_user))

        # --- H3: tool/action mediation (capability-downgrade) ---
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            # tool metadata (MCP annotations + server) the host/MCP-proxy attached to tool defs
            tool_meta = {}
            for t in body.get("tools", []) or []:
                fn = t.get("function") or {}
                if fn.get("name"):
                    tool_meta[fn["name"]] = (fn.get("annotations"), fn.get("x_mcp_server"))
            kept: list = []
            denied: list = []
            for tc in tool_calls:
                name = (tc.get("function") or {}).get("name", "") or "unknown"
                ann, srv = tool_meta.get(name, (None, None))
                if ann is None and name in registry:  # fall back to discovered annotations
                    ann, srv = registry[name]
                tier = resolve_tier(name, cfg.tool_tiers, cfg.trusted_tool_servers,
                                    annotations=ann, server=srv)
                d = pdp.decide(AuthzRequest(
                    principal_id=session.id, action="InvokeTool",
                    resource_type="Seatbelt::Tool", resource_id=name,
                    context={"provenance_max_trust": turn_trust, "tier": tier,
                             "user_verified": False, "human_confirmed": False}))
                if d.effect == "allow":
                    kept.append(tc)
                else:
                    denied.append({"tool": name, "tier": tier, "reasons": d.reasons})
            budget.record(session, in_tok, _est_tokens(str(tool_calls)), cfg.budget)
            audit.emit(TelemetryRecord(session.id, session.principal_key, "InvokeTool",
                       "allow" if not denied else ("partial_deny" if kept else "deny"),
                       [d["tool"] for d in denied], scope_verdict=verdict,
                       cost_used=session.cost_used,
                       extra={"provenance": turn_trust, "denied": denied}))
            if not kept:
                return JSONResponse(content=_completion(_BLOCKED_ACTION_MSG))
            message["tool_calls"] = kept
            return JSONResponse(content=resp)  # forward upstream resp with denied calls stripped

        # --- content path: H5-lite output scope + H6 egress ---
        content = message.get("content", "") or ""
        out_tok = int(usage.get("completion_tokens") or _est_tokens(content))
        out_blocked = False
        if scope_guard.evaluate([Message("user", content)], cfg.scope).verdict == "offscope":
            content, out_blocked = cfg.scope.deflect_message, True

        # provenance-gated egress: an untrusted-driven turn may not render ANY links
        eg_cfg = replace(cfg.egress, render_links=False) if turn_trust == "untrusted" else cfg.egress
        try:
            eg = egress.sanitize(content, eg_cfg)
            content, blocked = eg.sanitized_text, eg.blocked
        except Exception as e:
            content, blocked = cfg.scope.deflect_message, [f"egress_error: {e}"]

        # --- H0: record cost + telemetry ---
        budget.record(session, in_tok, out_tok, cfg.budget)
        audit.emit(TelemetryRecord(session.id, session.principal_key, "ReturnAnswer",
                                   "allow", scope_verdict=verdict, cost_used=session.cost_used,
                                   extra={"egress_blocked": blocked, "output_blocked": out_blocked,
                                          "provenance": turn_trust}))
        return JSONResponse(content=_completion(content, {
            "prompt_tokens": in_tok, "completion_tokens": out_tok,
            "total_tokens": in_tok + out_tok}))

    return app
