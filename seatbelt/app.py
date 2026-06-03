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
import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from seatbelt.budget import TokenWeightedBudgetGovernor
from seatbelt.egress import LinkPolicyEgressGuard
from seatbelt.pdp import CedarPDP
from seatbelt.scope import DeterministicScopeGuard
from seatbelt.telemetry import AuditSink
from seatbelt.types import AuthzRequest, Message, SeatbeltConfig, Session, TelemetryRecord

Upstream = Callable[[dict], dict]


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


def create_app(cfg: SeatbeltConfig, upstream: Upstream | None = None) -> FastAPI:
    app = FastAPI(title="Seatbelt", version="0.1.0")
    scope_guard = DeterministicScopeGuard()
    budget = TokenWeightedBudgetGovernor()
    egress = LinkPolicyEgressGuard()
    pdp = CedarPDP()
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
            sr = scope_guard.evaluate(msgs, cfg.scope)
            verdict = sr.verdict
        except Exception as e:  # graduated fail posture: scope_check = open_with_alert
            verdict = "unknown"
            audit.emit(TelemetryRecord(session.id, session.principal_key, "ScopeGuard",
                                       "error_open", [f"scope_error: {e}"], scope_verdict="unknown"))

        # --- Cedar PDP: AdmitInput ---
        decision = pdp.decide(AuthzRequest(
            principal_id=session.id, action="AdmitInput",
            resource_type="Seatbelt::Answer", resource_id="answer",
            context={"scope_verdict": verdict, "cost_used": int(session.cost_used),
                     "budget_remaining": int(br.budget_remaining)},
        ))
        if decision.effect == "deny":
            # Confident offscope -> deflect WITHOUT calling upstream (saves spend: defeats T1/T7).
            budget.record(session, _est_tokens(last_user), _est_tokens(cfg.scope.deflect_message), cfg.budget)
            audit.emit(TelemetryRecord(session.id, session.principal_key, "AdmitInput",
                                       "deflect", decision.reasons, scope_verdict=verdict,
                                       cost_used=session.cost_used))
            return JSONResponse(content=_completion(cfg.scope.deflect_message))

        # --- upstream model call ---
        resp = up(body)
        content = (resp.get("choices", [{}])[0].get("message", {}) or {}).get("content", "") or ""
        usage = resp.get("usage") or {}
        in_tok = usage.get("prompt_tokens") or _est_tokens(last_user)
        out_tok = usage.get("completion_tokens") or _est_tokens(content)

        # --- H5-lite: output scope check (catch "refused then complied", e.g. code in output) ---
        out_blocked = False
        if scope_guard.evaluate([Message("user", content)], cfg.scope).verdict == "offscope":
            content = cfg.scope.deflect_message
            out_blocked = True

        # --- H6: egress link/exfil-channel neutralization (fail-closed) ---
        try:
            eg = egress.sanitize(content, cfg.egress)
            content, blocked = eg.sanitized_text, eg.blocked
        except Exception as e:
            content, blocked = cfg.scope.deflect_message, [f"egress_error: {e}"]

        # --- H0: record cost + telemetry ---
        budget.record(session, int(in_tok), int(out_tok), cfg.budget)
        audit.emit(TelemetryRecord(session.id, session.principal_key, "ReturnAnswer",
                                   "allow", scope_verdict=verdict, cost_used=session.cost_used,
                                   extra={"egress_blocked": blocked, "output_blocked": out_blocked}))
        return JSONResponse(content=_completion(content, {
            "prompt_tokens": int(in_tok), "completion_tokens": int(out_tok),
            "total_tokens": int(in_tok) + int(out_tok)}))

    return app
