"""Token-weighted budget governor (hook H0) — defends T7 denial-of-wallet."""

import time

from seatbelt.types import BudgetConfig, BudgetResult, Session


class TokenWeightedBudgetGovernor:
    """Stateless governor that mutates the caller-owned Session to track spend."""

    def check(self, session: Session, cfg: BudgetConfig, *, now: float | None = None) -> BudgetResult:
        now = now if now is not None else time.time()

        # Reset window on first use or expiry.
        if session.window_start == 0.0 or (now - session.window_start >= cfg.window_seconds):
            session.cost_used = 0.0
            session.window_start = now

        allowed = session.cost_used < cfg.cost_units_per_window
        remaining = max(0.0, cfg.cost_units_per_window - session.cost_used)
        return BudgetResult(
            allowed=allowed,
            cost_used=session.cost_used,
            budget_remaining=remaining,
            reason="" if allowed else "budget exhausted",
        )

    def record(self, session: Session, input_tokens: int, output_tokens: int, cfg: BudgetConfig, *, now: float | None = None) -> None:
        # Output tokens weighted heavier per harness-design §3.7 (default 5x input).
        cost_units = (input_tokens * cfg.input_token_weight + output_tokens * cfg.output_token_weight) / 1000.0
        session.cost_used += cost_units
