from __future__ import annotations

import asyncio
from contextlib import suppress
from time import monotonic
from typing import Literal

from project_invest.domain.models import RuntimeComponentState, RuntimeComponentStatus, utc_now
from project_invest.services.research_lab import ResearchLab
from project_invest.services.trading_lab import TradingLab
from project_invest.storage.repositories import RuntimeStatusRepository


class _WorkerStatusReporter:
    def __init__(
        self,
        storage: RuntimeStatusRepository | None,
        component: Literal["research_worker", "trading_worker"],
    ) -> None:
        self.storage = storage
        self.component = component
        self.started_at = utc_now()
        self.last_success_at = None
        self.last_error: str | None = None
        self.last_error_at = None

    def publish(
        self,
        state: RuntimeComponentState,
        *,
        cycle_started_at=None,
        last_cycle_duration_seconds: float | None = None,
    ) -> None:
        if self.storage is None:
            return
        now = utc_now()
        try:
            self.storage.save_runtime_status(
                RuntimeComponentStatus(
                    component=self.component,
                    state=state,
                    updated_at=now,
                    heartbeat_at=now,
                    started_at=self.started_at,
                    cycle_started_at=cycle_started_at,
                    last_success_at=self.last_success_at,
                    last_error=self.last_error,
                    last_error_at=self.last_error_at,
                    last_cycle_duration_seconds=last_cycle_duration_seconds,
                )
            )
        except Exception:
            # Status diagnostics must never crash a paper-trading or research worker.
            return

    def succeeded(self, duration_seconds: float) -> None:
        self.last_success_at = utc_now()
        self.last_error = None
        self.last_error_at = None
        self.publish(RuntimeComponentState.IDLE, last_cycle_duration_seconds=duration_seconds)

    def failed(self, error: Exception, duration_seconds: float) -> None:
        self.last_error = str(error)
        self.last_error_at = utc_now()
        self.publish(RuntimeComponentState.FAILED, last_cycle_duration_seconds=duration_seconds)


async def _report_cycle_heartbeats(
    reporter: _WorkerStatusReporter,
    cycle_started_at,
) -> None:
    """Keep an active cycle observable even when an upstream request is slow."""
    while True:
        await asyncio.sleep(30)
        reporter.publish(RuntimeComponentState.RUNNING, cycle_started_at=cycle_started_at)


class BackgroundResearchWorker:
    def __init__(
        self,
        research_lab: ResearchLab,
        interval_seconds: int,
        symbols: list[str],
        execute_trades: bool = True,
        run_lock: asyncio.Lock | None = None,
        status_repository: RuntimeStatusRepository | None = None,
    ) -> None:
        self.research_lab = research_lab
        self.interval_seconds = max(10, interval_seconds)
        self.symbols = symbols
        self.execute_trades = execute_trades
        self.last_error: str | None = None
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._run_lock = run_lock
        self._status = _WorkerStatusReporter(status_repository, "research_worker")

    async def start(self) -> None:
        if self._task is None:
            self._status.publish(RuntimeComponentState.STARTING)
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._status.publish(RuntimeComponentState.STOPPED)

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            cycle_started_at = utc_now()
            cycle_started_at_monotonic = monotonic()
            self._status.publish(RuntimeComponentState.RUNNING, cycle_started_at=cycle_started_at)
            heartbeat_task = asyncio.create_task(
                _report_cycle_heartbeats(self._status, cycle_started_at)
            )
            try:
                if self._run_lock is None:
                    await self.research_lab.run_cycle(self.symbols, execute_trades=self.execute_trades)
                else:
                    async with self._run_lock:
                        await self.research_lab.run_cycle(self.symbols, execute_trades=self.execute_trades)
                self.last_error = None
                self._status.succeeded(monotonic() - cycle_started_at_monotonic)
            except Exception as exc:
                self.last_error = str(exc)
                self._status.failed(exc, monotonic() - cycle_started_at_monotonic)
            finally:
                heartbeat_task.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat_task

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue


class BackgroundResearchSupervisor:
    def __init__(
        self,
        research_lab: ResearchLab,
        interval_seconds: int,
        symbol_groups: list[list[str]],
        execute_trades: bool = True,
        run_lock: asyncio.Lock | None = None,
        status_repository: RuntimeStatusRepository | None = None,
    ) -> None:
        self.research_lab = research_lab
        self.interval_seconds = max(10, interval_seconds)
        self.symbol_groups = [group for group in symbol_groups if group]
        self.last_error: str | None = None
        self._lock = run_lock or asyncio.Lock()
        self._workers = [
            BackgroundResearchWorker(
                research_lab=research_lab,
                interval_seconds=self.interval_seconds,
                symbols=group,
                execute_trades=execute_trades,
                run_lock=self._lock,
                status_repository=status_repository,
            )
            for group in self.symbol_groups
        ]

    async def start(self) -> None:
        for worker in self._workers:
            await worker.start()

    async def stop(self) -> None:
        for worker in self._workers:
            await worker.stop()

    def refresh_last_error(self) -> None:
        for worker in self._workers:
            if worker.last_error:
                self.last_error = worker.last_error
                return
        self.last_error = None


class BackgroundTradingWorker:
    def __init__(
        self,
        trading_lab: TradingLab,
        interval_seconds: int,
        symbols: list[str],
        run_lock: asyncio.Lock | None = None,
        status_repository: RuntimeStatusRepository | None = None,
    ) -> None:
        self.trading_lab = trading_lab
        self.interval_seconds = max(10, interval_seconds)
        self.symbols = symbols
        self.last_error: str | None = None
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._run_lock = run_lock
        self._status = _WorkerStatusReporter(status_repository, "trading_worker")

    async def start(self) -> None:
        if self._task is None:
            self._status.publish(RuntimeComponentState.STARTING)
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._status.publish(RuntimeComponentState.STOPPED)

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            cycle_started_at = utc_now()
            cycle_started_at_monotonic = monotonic()
            self._status.publish(RuntimeComponentState.RUNNING, cycle_started_at=cycle_started_at)
            heartbeat_task = asyncio.create_task(
                _report_cycle_heartbeats(self._status, cycle_started_at)
            )
            try:
                if self._run_lock is None:
                    await self.trading_lab.run_cycle(self.symbols)
                else:
                    async with self._run_lock:
                        await self.trading_lab.run_cycle(self.symbols)
                self.last_error = None
                self._status.succeeded(monotonic() - cycle_started_at_monotonic)
            except Exception as exc:
                self.last_error = str(exc)
                self._status.failed(exc, monotonic() - cycle_started_at_monotonic)
            finally:
                heartbeat_task.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat_task

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue


class BackgroundTradingSupervisor:
    def __init__(
        self,
        trading_lab: TradingLab,
        interval_seconds: int,
        symbol_groups: list[list[str]],
        run_lock: asyncio.Lock | None = None,
        status_repository: RuntimeStatusRepository | None = None,
    ) -> None:
        self.trading_lab = trading_lab
        self.interval_seconds = max(10, interval_seconds)
        self.symbol_groups = [group for group in symbol_groups if group]
        self.last_error: str | None = None
        self._lock = run_lock or asyncio.Lock()
        self._workers = [
            BackgroundTradingWorker(
                trading_lab=trading_lab,
                interval_seconds=self.interval_seconds,
                symbols=group,
                run_lock=self._lock,
                status_repository=status_repository,
            )
            for group in self.symbol_groups
        ]

    async def start(self) -> None:
        for worker in self._workers:
            await worker.start()

    async def stop(self) -> None:
        for worker in self._workers:
            await worker.stop()

    def refresh_last_error(self) -> None:
        for worker in self._workers:
            if worker.last_error:
                self.last_error = worker.last_error
                return
        self.last_error = None
