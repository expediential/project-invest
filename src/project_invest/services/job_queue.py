from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from project_invest.domain.models import ResearchJob, ResearchJobStatus
from project_invest.storage.repositories import ResearchJobRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LocalResearchJobExecutor:
    """Single-concurrency, durable local executor for non-trading research cycles."""

    def __init__(
        self,
        storage: ResearchJobRepository,
        research_lab,
        poll_interval_seconds: int = 2,
        job_timeout_seconds: int = 1800,
    ) -> None:
        self.storage = storage
        self.research_lab = research_lab
        self.poll_interval_seconds = max(1, poll_interval_seconds)
        self.job_timeout_seconds = max(30, job_timeout_seconds)
        self.worker_id = f"local-job-executor-{uuid4().hex[:12]}"
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self.current_job_id: str | None = None
        self.last_error: str | None = None
        self.last_success_at: datetime | None = None

    async def start(self) -> None:
        self.recover_interrupted_jobs()
        if self._task is None:
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def submit_research(self, symbols: list[str] | None = None, purpose: str = "On-demand research cycle") -> ResearchJob:
        job = ResearchJob(
            purpose=purpose[:240],
            execution_backend="local",
            experiment_config={"symbols": list(symbols or []), "execute_trades": False},
        )
        self.storage.create_job(job)
        return job

    def request_cancel(self, job_id: str) -> ResearchJob | None:
        job = self.storage.get_job(job_id)
        if job is None or job.status in {ResearchJobStatus.SUCCEEDED, ResearchJobStatus.FAILED, ResearchJobStatus.CANCELLED}:
            return job
        now = _utc_now()
        job.cancellation_requested_at = now
        job.updated_at = now
        if job.status == ResearchJobStatus.QUEUED:
            job.status = ResearchJobStatus.CANCELLED
            job.completed_at = now
        self.storage.update_job(job)
        return job

    def recover_interrupted_jobs(self) -> None:
        """Mark prior-process running work failed; do not silently restart it."""
        for job in self.storage.list_jobs():
            if job.status != ResearchJobStatus.RUNNING:
                continue
            job.status = ResearchJobStatus.FAILED
            job.failure_reason = "Executor stopped before the job completed; manual resubmission is required."
            job.completed_at = _utc_now()
            job.updated_at = job.completed_at
            self.storage.update_job(job)

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            job = self.storage.claim_next_job(self.worker_id)
            if job is not None:
                await self._execute(job)
                continue
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def _execute(self, job: ResearchJob) -> None:
        self.current_job_id = job.job_id
        heartbeat_task = asyncio.create_task(self._heartbeat(job.job_id))
        try:
            job.heartbeat_at = _utc_now()
            job.updated_at = job.heartbeat_at
            self.storage.update_job(job)
            symbols = job.experiment_config.get("symbols", [])
            if not isinstance(symbols, list) or not all(isinstance(item, str) for item in symbols):
                raise ValueError("Job symbols must be a list of strings.")
            report = await asyncio.wait_for(
                self.research_lab.run_cycle(symbols or None, execute_trades=False),
                timeout=self.job_timeout_seconds,
            )
            current = self.storage.get_job(job.job_id) or job
            now = _utc_now()
            current.heartbeat_at = now
            current.updated_at = now
            current.completed_at = now
            current.progress = 1.0
            current.result_reference = f"research-report:{getattr(report, 'report_id', job.job_id)}"
            if current.cancellation_requested_at is not None:
                current.status = ResearchJobStatus.CANCELLED
                current.failure_reason = "Cancellation was requested while the non-interruptible research cycle was completing."
            else:
                current.status = ResearchJobStatus.SUCCEEDED
                self.last_success_at = now
            self.storage.update_job(current)
            self.last_error = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            current = self.storage.get_job(job.job_id) or job
            now = _utc_now()
            current.status = ResearchJobStatus.FAILED
            current.failure_reason = str(exc)[:500]
            current.completed_at = now
            current.heartbeat_at = now
            current.updated_at = now
            self.storage.update_job(current)
            self.last_error = current.failure_reason
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            self.current_job_id = None

    async def _heartbeat(self, job_id: str) -> None:
        while True:
            await asyncio.sleep(5)
            job = self.storage.get_job(job_id)
            if job is None or job.status != ResearchJobStatus.RUNNING:
                return
            job.heartbeat_at = _utc_now()
            job.updated_at = job.heartbeat_at
            self.storage.update_job(job)


def summarize_jobs(storage: ResearchJobRepository, limit: int = 20) -> dict[str, object]:
    jobs = storage.list_jobs(limit=limit)
    now = _utc_now()
    counts = {status.value: 0 for status in ResearchJobStatus}
    for job in jobs:
        counts[job.status.value] += 1
    stale = [
        job.job_id
        for job in jobs
        if job.status == ResearchJobStatus.RUNNING
        and job.heartbeat_at is not None
        and now - job.heartbeat_at > timedelta(minutes=2)
    ]
    return {
        "counts": counts,
        "stale_job_ids": stale,
        "jobs": jobs,
        "note": "Interrupted running jobs are marked failed at executor startup and are never restarted automatically.",
    }
