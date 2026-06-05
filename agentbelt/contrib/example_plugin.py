"""Example plugin: bring your own RiskScorer.

Select it in config without touching the harness:

    providers:
      risk: "agentbelt.contrib.example_plugin:make"

`make(cfg)` is the provider factory (receives the whole AgentbeltConfig). It returns any object
implementing the `RiskScorer` protocol from `agentbelt.types`. Swap the body of `_predict` for a
call into your own model/service — that's the whole integration.
"""
from agentbelt.types import RiskResult


class KeywordModelScorer:
    """Stand-in for a user-supplied model. Implements RiskScorer.score_turn(...)."""

    def __init__(self, trip_words: list[str]):
        self.trip_words = [w.lower() for w in trip_words]

    def _predict(self, text: str) -> float:
        # >>> Replace this with your own model/service call (returns a risk score in [0, 1]). <<<
        return 1.0 if any(w in text.lower() for w in self.trip_words) else 0.0

    def score_turn(self, session, user_text, scope_verdict, cfg) -> RiskResult:
        score = self._predict(user_text)
        tripped = score >= cfg.threshold
        return RiskResult(score=score, tripped=tripped, reasons=["custom_model"] if tripped else [])


def make(cfg):
    """Provider factory. Reads anything it needs from cfg; here, a demo trip-word list."""
    trip_words = (cfg.providers.get("risk_params", {}) or {}).get("trip_words", ["banana"])
    return KeywordModelScorer(trip_words)
