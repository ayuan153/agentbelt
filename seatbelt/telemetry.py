"""Telemetry / audit sink (H0).

Records decisions + redacted metadata — never raw transcripts (see D6 in
docs/open-questions.md). Emits a JSON line per decision and keeps an in-memory
ring for inspection/testing.
"""
from __future__ import annotations

import dataclasses
import json
import logging

from seatbelt.types import TelemetryRecord

_log = logging.getLogger("seatbelt.audit")


class AuditSink:
    def __init__(self, keep: int = 1000) -> None:
        self.records: list[TelemetryRecord] = []
        self._keep = keep

    def emit(self, record: TelemetryRecord) -> None:
        self.records.append(record)
        if len(self.records) > self._keep:
            self.records.pop(0)
        _log.info(json.dumps(dataclasses.asdict(record)))
