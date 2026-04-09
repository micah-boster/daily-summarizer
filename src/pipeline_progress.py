"""Pipeline progress reporter for JSON-line stdout output.

Used by the API subprocess pipeline runner to stream stage-by-stage
progress events. Each event is a single JSON line on stdout, enabling
the parent process to parse progress in real time.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field


@dataclass
class StageInfo:
    """Tracks a single pipeline stage."""

    name: str
    status: str = "pending"
    elapsed_s: float | None = None
    error: str | None = None
    started_at: float | None = None


class ProgressReporter:
    """Emits JSON progress lines to stdout for subprocess monitoring.

    Each call to stage_start / stage_complete / stage_failed / run_complete /
    run_failed writes a single JSON dict to stdout with flush=True so the
    parent process receives it immediately.
    """

    def __init__(self, run_id: str, target_date: str) -> None:
        self.run_id = run_id
        self.target_date = target_date
        self.stages: list[StageInfo] = []
        self.start_time = time.time()
        self._current_stage: str | None = None

    def stage_start(self, name: str) -> None:
        """Record that a stage has started."""
        stage = StageInfo(name=name, status="running", started_at=time.time())
        self.stages.append(stage)
        self._current_stage = name
        self._emit(status="running", stage=name)

    def stage_complete(self, name: str) -> None:
        """Record that a stage completed successfully."""
        for s in self.stages:
            if s.name == name:
                s.status = "complete"
                if s.started_at is not None:
                    s.elapsed_s = round(time.time() - s.started_at, 2)
                break
        self._emit(status="running", stage=name)

    def stage_failed(self, name: str, error: str) -> None:
        """Record that a stage failed."""
        for s in self.stages:
            if s.name == name:
                s.status = "failed"
                s.error = error
                if s.started_at is not None:
                    s.elapsed_s = round(time.time() - s.started_at, 2)
                break
        self._emit(status="running", stage=name, error=error)

    def run_complete(self) -> None:
        """Emit a final completion event."""
        self._emit(status="complete", stage=None)

    def run_failed(self, error: str) -> None:
        """Emit a final failure event."""
        self._emit(status="failed", stage=None, error=error)

    def _emit(
        self,
        status: str,
        stage: str | None,
        error: str | None = None,
    ) -> None:
        """Print a JSON event to stdout with flush."""
        event = {
            "run_id": self.run_id,
            "status": status,
            "stage": stage,
            "stages": [
                {
                    "name": s.name,
                    "status": s.status,
                    "elapsed_s": s.elapsed_s,
                }
                for s in self.stages
            ],
            "target_date": self.target_date,
            "elapsed_s": round(time.time() - self.start_time, 2),
            "error": error,
        }
        print(json.dumps(event), file=sys.stdout, flush=True)
