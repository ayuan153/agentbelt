"""Agentbelt core types — the LOCKED contract shared by all guard modules.

Implements the data model for the MVP denial-of-wallet slice
(docs/lld/mvp-denial-of-wallet-slice.md). Names mirror ADR-0003
(Cedar schema) and ADR-0001 (interception contract).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

# --- shared enums / literals -------------------------------------------------

ScopeVerdict = Literal["onscope", "offscope", "unknown"]
Effect = Literal["allow", "deny"]
# Cedar context.provenance_max_trust; MVP has no provenance tracking -> "user".
TrustTier = Literal["trusted", "user", "untrusted"]


# --- wire / runtime ----------------------------------------------------------


@dataclass
class Message:
    role: str  # "system" | "developer" | "user" | "assistant" | "tool"
    content: str


@dataclass
class Session:
    id: str
    principal_key: str
    cost_used: float = 0.0
    window_start: float = 0.0
    risk_score: float = 0.0
    # provenance state (H2): content hashes already seen, to detect what is NEW this turn
    seen_hashes: set[str] = field(default_factory=set)


# --- operator config (loaded from YAML) --------------------------------------


@dataclass
class ScopeContract:
    charter: str
    allow_intents: list[str] = field(default_factory=list)
    hard_deny: list[str] = field(default_factory=list)  # category names, e.g. "code_generation"
    on_offscope: str = "deflect"  # deflect | refuse | escalate
    deflect_message: str = "I can only help with in-scope requests."
    examples: list[dict] = field(default_factory=list)  # [{"text":..., "label":"onscope|offscope"}]


@dataclass
class BudgetConfig:
    cost_units_per_window: float
    window_seconds: int = 3600
    output_token_weight: float = 5.0  # output tokens cost more (see harness-design §3.7)
    input_token_weight: float = 1.0


@dataclass
class EgressConfig:
    allow_domains: list[str] = field(default_factory=list)
    render_links: bool = False


@dataclass
class FailPosture:
    # behavior when a control errors/is unavailable: "closed" | "open_with_alert"
    default: str = "closed"
    scope_check: str = "open_with_alert"


@dataclass
class RiskConfig:
    """Multi-turn (Crescendo) session-risk scoring knobs."""
    threshold: float = 1.0      # tripped when accumulated score >= threshold
    decay: float = 0.8          # prior score multiplier each turn (one-offs fade)
    offscope_weight: float = 0.5
    unknown_weight: float = 0.15
    cue_weight: float = 0.4     # per escalation cue found in the turn
    scorer: str = "crescendo"   # "crescendo" (keyword) | "semantic" (charter drift)


@dataclass
class AgentbeltConfig:
    agent: str
    scope: ScopeContract
    budget: BudgetConfig
    egress: EgressConfig
    fail_posture: FailPosture = field(default_factory=FailPosture)
    upstream_base_url: str = "https://api.openai.com"
    # tool sensitivity tiers (H3): tool name -> "low" | "medium" | "high"; unlisted => default-sensitive
    tool_tiers: dict = field(default_factory=dict)
    trusted_tool_servers: list[str] = field(default_factory=list)
    risk: "RiskConfig" = field(default_factory=lambda: RiskConfig())
    # provider selection per extension point: name (built-in) or "module:factory" (your own)
    providers: dict = field(default_factory=dict)


# --- guard results -----------------------------------------------------------


@dataclass
class ScopeResult:
    verdict: ScopeVerdict
    matched: list[str] = field(default_factory=list)  # hard_deny categories / reasons hit


@dataclass
class RiskResult:
    score: float
    tripped: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class BudgetResult:
    allowed: bool
    cost_used: float
    budget_remaining: float
    reason: str = ""


@dataclass
class EgressResult:
    sanitized_text: str
    blocked: list[str] = field(default_factory=list)  # links/destinations removed
    allowed: bool = True


# --- PDP (Cedar) -------------------------------------------------------------


@dataclass
class AuthzRequest:
    """What a PEP hands the PDP. action is the Cedar action id
    ("AdmitInput" | "InvokeTool" | "ReturnAnswer" | "Egress")."""

    principal_id: str
    action: str
    resource_type: str  # "Agentbelt::Answer" | "Agentbelt::Tool" | "Agentbelt::Destination"
    resource_id: str
    context: dict = field(default_factory=dict)
    resource_attrs: dict = field(default_factory=dict)  # e.g. {"allowlisted": True} / {"tier": "high"}


@dataclass
class Decision:
    effect: Effect
    reasons: list[str] = field(default_factory=list)


# --- telemetry ---------------------------------------------------------------


@dataclass
class TelemetryRecord:
    session_id: str
    principal_key: str
    action: str
    decision: str  # "allow" | "deny" | "deflect" | "throttle"
    reasons: list[str] = field(default_factory=list)
    scope_verdict: str | None = None
    cost_used: float = 0.0
    extra: dict = field(default_factory=dict)


# --- guard interfaces (Protocols) --------------------------------------------


class ScopeGuard(Protocol):
    def evaluate(self, messages: list[Message], scope: ScopeContract) -> ScopeResult: ...


class RiskScorer(Protocol):
    def score_turn(self, session: Session, user_text: str, scope_verdict: str, cfg: RiskConfig) -> RiskResult: ...


class BudgetGovernor(Protocol):
    def check(self, session: Session, cfg: BudgetConfig) -> BudgetResult: ...
    def record(self, session: Session, input_tokens: int, output_tokens: int, cfg: BudgetConfig) -> None: ...


class EgressGuard(Protocol):
    def sanitize(self, text: str, cfg: EgressConfig) -> EgressResult: ...


class PolicyDecisionPoint(Protocol):
    def decide(self, req: AuthzRequest) -> Decision: ...


class ProvenanceProvider(Protocol):
    # H2 context firewall: returns this turn's provenance_max_trust ("trusted"|"user"|"untrusted")
    def turn_trust(self, session: Session, messages: list[dict]) -> str: ...
