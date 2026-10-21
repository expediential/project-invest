from __future__ import annotations

from contextlib import contextmanager
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from project_invest.domain.models import (
    Candle,
    ExecutionOrder,
    FeatureRow,
    PortfolioHistorySnapshot,
    PortfolioSnapshot,
    ResearchCycleReport,
    ResearchEvent,
    TradeMemoryRecord,
    TradeMemoryStatus,
    StrategyGenome,
    StrategyRegistryEntry,
)


class LocalDataLake:
    backend_name = "local"

    def __init__(self, root: Path) -> None:
        self.root = root
        for name in ("raw", "processed", "features", "reports", "state", "trades", "events", "trade_memory"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def _sanitize(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _read_json(self, path: Path, default: Any | None = None) -> Any:
        content = path.read_text(encoding="utf-8")
        content = content.replace("\x00", "")
        if not content.strip():
            return default
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                return self._recover_json_payload(content)
            except json.JSONDecodeError:
                if default is not None:
                    return default
                raise

    def _recover_json_payload(self, content: str) -> Any:
        decoder = json.JSONDecoder()
        index = 0
        recovered: list[Any] = []

        while index < len(content):
            while index < len(content) and content[index].isspace():
                index += 1
            if index >= len(content):
                break
            try:
                value, next_index = decoder.raw_decode(content, index)
            except json.JSONDecodeError:
                break
            recovered.append(value)
            index = next_index

        if not recovered:
            raise json.JSONDecodeError("Unable to recover JSON payload.", content, 0)

        if all(isinstance(item, list) for item in recovered):
            merged: list[Any] = []
            for item in recovered:
                merged.extend(item)
            return merged

        return recovered[-1]

    def _dataset_path(self, stage: str, symbol: str, interval: str) -> Path:
        safe_symbol = self._sanitize(symbol)
        safe_interval = self._sanitize(interval)
        return self.root / stage / f"{safe_symbol}-{safe_interval}.json"

    def _report_latest_path(self, stream: str) -> Path:
        safe_stream = self._sanitize(stream)
        if safe_stream == "research":
            return self.root / "reports" / "latest-research.json"
        return self.root / "reports" / f"latest-{safe_stream}.json"

    def _report_historical_path(self, stream: str, historical_name: str) -> Path:
        safe_stream = self._sanitize(stream)
        return self.root / "reports" / f"{safe_stream}-{historical_name}.json"

    def _lock_path(self, path: Path) -> Path:
        return path.with_name(f".{path.name}.lock")

    @contextmanager
    def _acquire_lock(self, path: Path, timeout_seconds: float = 10.0):
        lock_path = self._lock_path(path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        handle: int | None = None
        while handle is None:
            try:
                handle = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except FileExistsError:
                if time.monotonic() - start >= timeout_seconds:
                    raise TimeoutError(f"Timed out waiting for lock on {path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            os.close(handle)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def store_candles(self, symbol: str, interval: str, candles: list[Candle], stage: str) -> None:
        path = self._dataset_path(stage, symbol, interval)
        payload = [candle.model_dump(mode="json") for candle in candles]
        self._write_json(path, payload)

    def load_candles(self, symbol: str, interval: str, stage: str) -> list[Candle]:
        path = self._dataset_path(stage, symbol, interval)
        if not path.exists():
            return []
        return [Candle.model_validate(item) for item in (self._read_json(path, default=[]) or [])]

    def store_features(self, symbol: str, interval: str, rows: list[FeatureRow]) -> None:
        path = self._dataset_path("features", symbol, interval)
        payload = [row.model_dump(mode="json") for row in rows]
        self._write_json(path, payload)

    def load_features(self, symbol: str, interval: str) -> list[FeatureRow]:
        path = self._dataset_path("features", symbol, interval)
        if not path.exists():
            return []
        return [FeatureRow.model_validate(item) for item in (self._read_json(path, default=[]) or [])]

    def save_portfolio(self, portfolio: PortfolioSnapshot) -> None:
        path = self.root / "state" / "portfolio.json"
        with self._acquire_lock(path):
            self._write_json(path, portfolio.model_dump(mode="json"))
        self._append_portfolio_snapshot(portfolio)

    def load_portfolio(self) -> PortfolioSnapshot | None:
        path = self.root / "state" / "portfolio.json"
        if not path.exists():
            return None
        payload = self._read_json(path, default=None)
        if payload is None:
            return None
        return PortfolioSnapshot.model_validate(payload)

    def _append_portfolio_snapshot(self, portfolio: PortfolioSnapshot) -> None:
        path = self.root / "state" / "portfolio-history.json"
        snapshot = PortfolioHistorySnapshot.from_portfolio(portfolio)
        with self._acquire_lock(path):
            payload: list[dict[str, Any]] = []
            if path.exists():
                payload = self._read_json(path, default=[]) or []
            payload.append(snapshot.model_dump(mode="json"))
            self._write_json(path, payload)

    def load_portfolio_history(self, limit: int | None = None) -> list[PortfolioHistorySnapshot]:
        path = self.root / "state" / "portfolio-history.json"
        if not path.exists():
            return []
        snapshots = [
            PortfolioHistorySnapshot.model_validate(item)
            for item in (self._read_json(path, default=[]) or [])
        ]
        snapshots.sort(key=lambda item: (item.captured_at, item.snapshot_id))
        return snapshots if limit is None else snapshots[-limit:]

    def append_trade(self, trade: ExecutionOrder) -> None:
        path = self.root / "trades" / "history.json"
        with self._acquire_lock(path):
            payload: list[dict[str, Any]] = []
            if path.exists():
                payload = self._read_json(path, default=[]) or []
            existing = next((item for item in payload if item.get("trade_id") == trade.trade_id), None)
            if existing is not None:
                if existing != trade.model_dump(mode="json"):
                    raise ValueError(f"Conflicting duplicate trade id: {trade.trade_id}")
                return
            payload.append(trade.model_dump(mode="json"))
            self._write_json(path, payload)

    def load_trades(self, limit: int | None = None) -> list[ExecutionOrder]:
        path = self.root / "trades" / "history.json"
        if not path.exists():
            return []
        payload = [ExecutionOrder.model_validate(item) for item in (self._read_json(path, default=[]) or [])]
        if limit is None:
            return payload
        return payload[-limit:]

    def save_latest_report(self, report: ResearchCycleReport, stream: str = "research") -> None:
        latest_path = self._report_latest_path(stream)
        historical_name = report.finished_at.strftime("%Y%m%dT%H%M%S")
        historical_path = self._report_historical_path(stream, historical_name)
        payload = report.model_dump(mode="json")
        with self._acquire_lock(latest_path):
            self._write_json(latest_path, payload)
            if stream == "research":
                self._write_json(self.root / "reports" / "latest.json", payload)
            self._write_json(historical_path, payload)

    def load_latest_report(self, stream: str = "research") -> ResearchCycleReport | None:
        path = self._report_latest_path(stream)
        if stream == "research" and not path.exists():
            legacy_path = self.root / "reports" / "latest.json"
            if legacy_path.exists():
                path = legacy_path
        if not path.exists():
            return None
        payload = self._read_json(path, default=None)
        if payload is None:
            return None
        return ResearchCycleReport.model_validate(payload)

    def append_event(self, event: ResearchEvent) -> None:
        path = self.root / "events" / "events.json"
        with self._acquire_lock(path):
            payload: list[dict[str, Any]] = []
            if path.exists():
                payload = self._read_json(path, default=[]) or []
            payload.append(event.model_dump(mode="json"))
            self._write_json(path, payload)

    def load_events(self, limit: int | None = None) -> list[ResearchEvent]:
        path = self.root / "events" / "events.json"
        if not path.exists():
            return []
        payload = [ResearchEvent.model_validate(item) for item in (self._read_json(path, default=[]) or [])]
        if limit is None:
            return payload
        return payload[-limit:]

    def save_trade_memory(self, record: TradeMemoryRecord) -> None:
        path = self.root / "trade_memory" / "history.json"
        with self._acquire_lock(path):
            payload: list[dict[str, Any]] = []
            if path.exists():
                payload = self._read_json(path, default=[]) or []
            updated = False
            for index, item in enumerate(payload):
                if item.get("memory_id") == record.memory_id:
                    payload[index] = record.model_dump(mode="json")
                    updated = True
                    break
            if not updated:
                payload.append(record.model_dump(mode="json"))
            self._write_json(path, payload)

    def load_trade_memory(self, limit: int | None = None) -> list[TradeMemoryRecord]:
        path = self.root / "trade_memory" / "history.json"
        if not path.exists():
            return []
        payload = [TradeMemoryRecord.model_validate(item) for item in (self._read_json(path, default=[]) or [])]
        if limit is None:
            return payload
        return payload[-limit:]

    def load_open_trade_memory(self, symbol: str) -> TradeMemoryRecord | None:
        records = self.load_trade_memory()
        for record in reversed(records):
            if record.symbol == symbol and record.status == TradeMemoryStatus.OPEN:
                return record
        return None

    def save_active_strategy(self, symbol: str, genome: StrategyGenome) -> None:
        safe_symbol = self._sanitize(symbol)
        path = self.root / "state" / "strategies" / f"{safe_symbol}.json"
        with self._acquire_lock(path):
            self._write_json(path, genome.model_dump(mode="json"))

    def load_active_strategy(self, symbol: str) -> StrategyGenome | None:
        safe_symbol = self._sanitize(symbol)
        path = self.root / "state" / "strategies" / f"{safe_symbol}.json"
        if not path.exists():
            return None
        payload = self._read_json(path, default=None)
        if payload is None:
            return None
        return StrategyGenome.model_validate(payload)

    def delete_active_strategy(self, symbol: str) -> None:
        safe_symbol = self._sanitize(symbol)
        path = self.root / "state" / "strategies" / f"{safe_symbol}.json"
        with self._acquire_lock(path):
            if path.exists():
                path.unlink()

    def save_strategy_registry(self, symbol: str, entries: list[StrategyRegistryEntry]) -> None:
        safe_symbol = self._sanitize(symbol)
        path = self.root / "state" / "strategy_registry" / f"{safe_symbol}.json"
        payload = [entry.model_dump(mode="json") for entry in entries]
        with self._acquire_lock(path):
            self._write_json(path, payload)

    def load_strategy_registry(self, symbol: str) -> list[StrategyRegistryEntry]:
        safe_symbol = self._sanitize(symbol)
        path = self.root / "state" / "strategy_registry" / f"{safe_symbol}.json"
        if not path.exists():
            return []
        return [StrategyRegistryEntry.model_validate(item) for item in (self._read_json(path, default=[]) or [])]

    def close(self) -> None:
        return None
