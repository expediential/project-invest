from __future__ import annotations

from datetime import timedelta

from project_invest.domain.models import ResearchJob, ResearchJobStatus, utc_now
from project_invest.services.execution_backends import UnconfiguredCosmosBackend
from project_invest.services.job_queue import LocalResearchJobExecutor, summarize_jobs
from project_invest.storage.data_lake import LocalDataLake


def test_local_job_claim_is_atomic_across_storage_instances(tmp_path) -> None:
    first = LocalDataLake(tmp_path)
    second = LocalDataLake(tmp_path)
    job = ResearchJob()
    first.create_job(job)

    claimed = first.claim_next_job("worker-one")
    duplicate_claim = second.claim_next_job("worker-two")

    assert claimed is not None
    assert claimed.status is ResearchJobStatus.RUNNING
    assert duplicate_claim is None
    assert second.get_job(job.job_id).claimed_by == "worker-one"


def test_executor_recovers_interrupted_jobs_without_restarting_them(tmp_path) -> None:
    storage = LocalDataLake(tmp_path)
    job = ResearchJob(status=ResearchJobStatus.RUNNING, claimed_by="old-worker", started_at=utc_now())
    storage.create_job(job)

    executor = LocalResearchJobExecutor(storage, research_lab=object())
    executor.recover_interrupted_jobs()

    recovered = storage.get_job(job.job_id)
    assert recovered.status is ResearchJobStatus.FAILED
    assert "manual resubmission" in recovered.failure_reason


def test_cancel_queued_job_and_claim_local_research_without_trading(tmp_path) -> None:
    storage = LocalDataLake(tmp_path)
    executor = LocalResearchJobExecutor(storage, research_lab=object())
    cancelled = executor.submit_research(["TCS.NS"])
    executor.request_cancel(cancelled.job_id)
    assert storage.get_job(cancelled.job_id).status is ResearchJobStatus.CANCELLED

    submitted = executor.submit_research(["RELIANCE.NS"])
    claimed = storage.claim_next_job(executor.worker_id)

    assert claimed.job_id == submitted.job_id
    assert claimed.status is ResearchJobStatus.RUNNING
    assert claimed.experiment_config == {"symbols": ["RELIANCE.NS"], "execute_trades": False}


def test_stale_running_job_is_reported_and_cosmos_stays_unconfigured(tmp_path) -> None:
    storage = LocalDataLake(tmp_path)
    job = ResearchJob(
        status=ResearchJobStatus.RUNNING,
        heartbeat_at=utc_now() - timedelta(minutes=3),
    )
    storage.create_job(job)

    summary = summarize_jobs(storage)
    backend = UnconfiguredCosmosBackend()

    assert summary["stale_job_ids"] == [job.job_id]
    assert backend.status(job.job_id)["state"] == "unavailable"
