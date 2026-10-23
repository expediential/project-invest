from __future__ import annotations

from typing import Protocol

from project_invest.domain.models import ResearchJob


class ExecutionBackend(Protocol):
    name: str

    def submit(self, job: ResearchJob) -> ResearchJob:
        """Submit a structured job specification."""

    def status(self, job_id: str) -> dict[str, object]:
        """Return a non-secret backend status."""

    def results(self, job_id: str) -> dict[str, object]:
        """Return backend result metadata, not fabricated output."""


class UnconfiguredCosmosBackend:
    name = "cosmos"

    def submit(self, job: ResearchJob) -> ResearchJob:
        raise RuntimeError("Cosmos is not configured; no remote job was submitted.")

    def status(self, job_id: str) -> dict[str, object]:
        return {"state": "unavailable", "job_id": job_id, "reason": "Cosmos access has not been configured."}

    def results(self, job_id: str) -> dict[str, object]:
        return {"state": "unavailable", "job_id": job_id, "reason": "Cosmos access has not been configured."}
