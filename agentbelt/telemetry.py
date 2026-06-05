"""Telemetry / audit sink (H0).

Records decisions + redacted metadata — never raw transcripts (see D6 in
docs/open-questions.md). Emits a JSON line per decision, keeps an in-memory ring for
inspection/testing, and (optionally) appends to a JSONL file so `agentbelt dash` can read it.
"""
from __future__ import annotations

import dataclasses
import json
import logging

from agentbelt.types import TelemetryRecord

_log = logging.getLogger("agentbelt.audit")


class AuditSink:
    def __init__(self, keep: int = 1000, path: str | None = None) -> None:
        self.records: list[TelemetryRecord] = []
        self._keep = keep
        self._path = path  # optional JSONL file (set via AGENTBELT_AUDIT_LOG)

    def emit(self, record: TelemetryRecord) -> None:
        self.records.append(record)
        if len(self.records) > self._keep:
            self.records.pop(0)
        line = json.dumps(dataclasses.asdict(record))
        _log.info(line)
        if self._path:
            with open(self._path, "a") as f:
                f.write(line + "\n")
