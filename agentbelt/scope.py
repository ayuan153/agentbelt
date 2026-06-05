"""Deterministic Input Scope Guard (hook H1) — MVP denial-of-wallet slice.

This is the deterministic default for the pluggable charter-driven classifier
described in docs/configurability.md. Uses regex + keyword overlap only;
NO LLM or network calls, ensuring stable and reproducible results.
"""
from __future__ import annotations

import re

from agentbelt.types import Message, ScopeContract, ScopeResult

# --- Layer-1: hard_deny category -> regex patterns ---------------------------

_HARD_DENY_PATTERNS: dict[str, list[re.Pattern]] = {
    # code_generation: code fences, import/def statements, coding phrases
    "code_generation": [
        re.compile(r"```"),
        re.compile(r"\bwrite\s+(?:me\s+)?(?:a\s+|some\s+)?(?:python|code|script|function|class|program|http\s*server)\b", re.I),
        re.compile(r"\bimport\s+\w", re.I),
        re.compile(r"\bdef\s+\w", re.I),
        re.compile(r"\bnavier\b", re.I),
    ],
    # general_knowledge: trivia, translation, math
    "general_knowledge": [
        re.compile(r"\bwho\s+won\b", re.I),
        re.compile(r"\bcapital\s+of\b", re.I),
        re.compile(r"\btranslate\b", re.I),
        re.compile(r"\bsolve\b", re.I),
        re.compile(r"\bwhat\s+is\s+the\b", re.I),
    ],
    # role_override: jailbreak / prompt injection attempts
    "role_override": [
        re.compile(r"\bignore\s+(?:all\s+)?previous\b", re.I),
        re.compile(r"\bdisregard\b", re.I),
        re.compile(r"\byou\s+are\s+now\b", re.I),
        re.compile(r"\bsystem\s+prompt\b", re.I),
        re.compile(r"\bdeveloper\s+mode\b", re.I),
        re.compile(r"\bno\s+takesies\b", re.I),
    ],
}

# Stop-words excluded from token overlap matching
_STOP_WORDS = frozenset(
    "i me my the a an is are was were be been do does did have has had "
    "to of in for on at by it its this that and or but not".split()
)


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP_WORDS and len(w) > 1}


class DeterministicScopeGuard:
    """Regex + keyword-overlap scope classifier. Implements ScopeGuard protocol."""

    def evaluate(self, messages: list[Message], scope: ScopeContract) -> ScopeResult:
        # Find last user message
        user_text = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_text = msg.content
                break
        if not user_text:
            return ScopeResult(verdict="unknown")

        # Build allow-intent tokens for domain-awareness in hard_deny
        intent_kw = set()
        for intent in scope.allow_intents:
            intent_kw.update(intent.split("_"))

        # Layer-1: hard_deny regex check (only enforced categories)
        for category in scope.hard_deny:
            patterns = _HARD_DENY_PATTERNS.get(category, [])
            for pat in patterns:
                if pat.search(user_text):
                    # For general_knowledge 'what is the' — skip if text contains domain keywords
                    if category == "general_knowledge" and pat.pattern == r"\bwhat\s+is\s+the\b":
                        if _tokenize(user_text) & intent_kw:
                            continue
                    return ScopeResult(verdict="offscope", matched=[category])

        # Build token sets for layer-2
        user_tokens = _tokenize(user_text)
        if not user_tokens:
            return ScopeResult(verdict="unknown")

        # Layer-2: intent keyword match
        intent_tokens: set[str] = set()
        for intent in scope.allow_intents:
            intent_tokens.update(intent.split("_"))
        onscope_example_tokens: set[str] = set()
        offscope_example_tokens: set[str] = set()
        for ex in scope.examples:
            if ex.get("label") == "onscope":
                onscope_example_tokens.update(_tokenize(ex["text"]))
            elif ex.get("label") == "offscope":
                offscope_example_tokens.update(_tokenize(ex["text"]))

        allow_tokens = intent_tokens | onscope_example_tokens
        onscope_overlap = user_tokens & allow_tokens
        if len(onscope_overlap) >= 1:
            return ScopeResult(verdict="onscope", matched=list(onscope_overlap))

        # Layer-2b: offscope example overlap
        if offscope_example_tokens:
            offscope_overlap = user_tokens & offscope_example_tokens
            if len(offscope_overlap) >= 2:
                return ScopeResult(verdict="offscope", matched=list(offscope_overlap))

        return ScopeResult(verdict="unknown")
