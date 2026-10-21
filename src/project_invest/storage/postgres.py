from __future__ import annotations

import re
from typing import Any

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


class PostgresResearchStorage:
    backend_name = "postgres"

    def __init__(self, dsn: str, schema: str = "project_invest") -> None:
        self.dsn = dsn
        self.schema = self._sanitize_identifier(schema)
        self._install()

    def _connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "Postgres storage selected but the 'psycopg' package is not installed. "
                "Install project dependencies or switch PROJECT_INVEST_STORAGE_BACKEND to 'local'."
            ) from exc
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def _install(self) -> None:
        statements = [
            f"CREATE SCHEMA IF NOT EXISTS {self.schema}",
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.market_candles (
                stage TEXT NOT NULL,
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                payload JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (stage, symbol, interval)
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.feature_sets (
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                payload JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (symbol, interval)
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.portfolio_state (
                state_key TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.portfolio_history (
                snapshot_id TEXT PRIMARY KEY,
                captured_at TIMESTAMPTZ NOT NULL,
                payload JSONB NOT NULL
            )
            """,
            f"""
            CREATE INDEX IF NOT EXISTS portfolio_history_captured_at_idx
            ON {self.schema}.portfolio_history (captured_at)
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.trade_history (
                trade_id TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.research_reports (
                report_key TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.research_events (
                event_id TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.trade_memory (
                memory_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                status TEXT NOT NULL,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.active_strategies (
                symbol TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.strategy_registry (
                symbol TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
        ]
        with self._connect() as connection:
            connection.autocommit = True
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)

    def store_candles(self, symbol: str, interval: str, candles: list[Candle], stage: str) -> None:
        payload = [candle.model_dump(mode="json") for candle in candles]
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.market_candles (stage, symbol, interval, payload, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (stage, symbol, interval)
            DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
            """,
            (stage, symbol, interval, payload),
        )

    def load_candles(self, symbol: str, interval: str, stage: str) -> list[Candle]:
        row = self._fetch_one(
            f"""
            SELECT payload
            FROM {self.schema}.market_candles
            WHERE stage = %s AND symbol = %s AND interval = %s
            """,
            (stage, symbol, interval),
        )
        if row is None:
            return []
        return [Candle.model_validate(item) for item in row["payload"]]

    def store_features(self, symbol: str, interval: str, rows: list[FeatureRow]) -> None:
        payload = [row.model_dump(mode="json") for row in rows]
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.feature_sets (symbol, interval, payload, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (symbol, interval)
            DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
            """,
            (symbol, interval, payload),
        )

    def load_features(self, symbol: str, interval: str) -> list[FeatureRow]:
        row = self._fetch_one(
            f"""
            SELECT payload
            FROM {self.schema}.feature_sets
            WHERE symbol = %s AND interval = %s
            """,
            (symbol, interval),
        )
        if row is None:
            return []
        return [FeatureRow.model_validate(item) for item in row["payload"]]

    def save_portfolio(self, portfolio: PortfolioSnapshot) -> None:
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.portfolio_state (state_key, payload, updated_at)
            VALUES ('latest', %s, NOW())
            ON CONFLICT (state_key)
            DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
            """,
            (portfolio.model_dump(mode="json"),),
        )
        snapshot = PortfolioHistorySnapshot.from_portfolio(portfolio)
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.portfolio_history (snapshot_id, captured_at, payload)
            VALUES (%s, %s, %s)
            ON CONFLICT (snapshot_id) DO NOTHING
            """,
            (snapshot.snapshot_id, snapshot.captured_at, snapshot.model_dump(mode="json")),
        )

    def load_portfolio(self) -> PortfolioSnapshot | None:
        row = self._fetch_one(
            f"""
            SELECT payload
            FROM {self.schema}.portfolio_state
            WHERE state_key = 'latest'
            """,
        )
        if row is None:
            return None
        return PortfolioSnapshot.model_validate(row["payload"])

    def load_portfolio_history(self, limit: int | None = None) -> list[PortfolioHistorySnapshot]:
        limit_clause = ""
        params: list[Any] = []
        order_clause = "ORDER BY captured_at ASC"
        if limit is not None:
            order_clause = "ORDER BY captured_at DESC"
            limit_clause = "LIMIT %s"
            params.append(limit)
        rows = self._fetch_all(
            f"""
            SELECT payload
            FROM {self.schema}.portfolio_history
            {order_clause}
            {limit_clause}
            """,
            tuple(params),
        )
        snapshots = [PortfolioHistorySnapshot.model_validate(row["payload"]) for row in rows]
        return snapshots if limit is None else list(reversed(snapshots))

    def append_trade(self, trade: ExecutionOrder) -> None:
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.trade_history (trade_id, payload, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (trade_id)
            DO UPDATE SET payload = EXCLUDED.payload
            """,
            (trade.trade_id, trade.model_dump(mode="json")),
        )

    def load_trades(self, limit: int | None = None) -> list[ExecutionOrder]:
        limit_clause = ""
        params: list[Any] = []
        order_clause = "ORDER BY created_at ASC"
        if limit is not None:
            order_clause = "ORDER BY created_at DESC"
            limit_clause = "LIMIT %s"
            params.append(limit)

        rows = self._fetch_all(
            f"""
            SELECT payload
            FROM {self.schema}.trade_history
            {order_clause}
            {limit_clause}
            """,
            tuple(params),
        )
        trades = [ExecutionOrder.model_validate(row["payload"]) for row in rows]
        if limit is None:
            return trades
        return list(reversed(trades))

    def save_latest_report(self, report: ResearchCycleReport, stream: str = "research") -> None:
        payload = report.model_dump(mode="json")
        historical_key = report.finished_at.strftime("%Y%m%dT%H%M%S")
        latest_key = f"latest:{stream}"
        historical_stream_key = f"{stream}:{historical_key}"
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.research_reports (report_key, payload, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (report_key)
            DO UPDATE SET payload = EXCLUDED.payload
            """,
            (latest_key, payload),
        )
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.research_reports (report_key, payload, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (report_key)
            DO UPDATE SET payload = EXCLUDED.payload
            """,
            (historical_stream_key, payload),
        )

    def load_latest_report(self, stream: str = "research") -> ResearchCycleReport | None:
        row = self._fetch_one(
            f"""
            SELECT payload
            FROM {self.schema}.research_reports
            WHERE report_key = %s
            """,
            (f"latest:{stream}",),
        )
        if row is None:
            return None
        return ResearchCycleReport.model_validate(row["payload"])

    def append_event(self, event: ResearchEvent) -> None:
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.research_events (event_id, payload, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (event_id)
            DO UPDATE SET payload = EXCLUDED.payload
            """,
            (event.event_id, event.model_dump(mode="json")),
        )

    def load_events(self, limit: int | None = None) -> list[ResearchEvent]:
        limit_clause = ""
        params: list[Any] = []
        order_clause = "ORDER BY created_at ASC"
        if limit is not None:
            order_clause = "ORDER BY created_at DESC"
            limit_clause = "LIMIT %s"
            params.append(limit)

        rows = self._fetch_all(
            f"""
            SELECT payload
            FROM {self.schema}.research_events
            {order_clause}
            {limit_clause}
            """,
            tuple(params),
        )
        events = [ResearchEvent.model_validate(row["payload"]) for row in rows]
        if limit is None:
            return events
        return list(reversed(events))

    def save_trade_memory(self, record: TradeMemoryRecord) -> None:
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.trade_memory (memory_id, symbol, status, payload, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (memory_id)
            DO UPDATE SET
                symbol = EXCLUDED.symbol,
                status = EXCLUDED.status,
                payload = EXCLUDED.payload,
                updated_at = NOW()
            """,
            (record.memory_id, record.symbol, record.status.value, record.model_dump(mode="json")),
        )

    def load_trade_memory(self, limit: int | None = None) -> list[TradeMemoryRecord]:
        limit_clause = ""
        params: list[Any] = []
        order_clause = "ORDER BY created_at ASC"
        if limit is not None:
            order_clause = "ORDER BY created_at DESC"
            limit_clause = "LIMIT %s"
            params.append(limit)

        rows = self._fetch_all(
            f"""
            SELECT payload
            FROM {self.schema}.trade_memory
            {order_clause}
            {limit_clause}
            """,
            tuple(params),
        )
        records = [TradeMemoryRecord.model_validate(row["payload"]) for row in rows]
        if limit is None:
            return records
        return list(reversed(records))

    def load_open_trade_memory(self, symbol: str) -> TradeMemoryRecord | None:
        row = self._fetch_one(
            f"""
            SELECT payload
            FROM {self.schema}.trade_memory
            WHERE symbol = %s AND status = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (symbol, TradeMemoryStatus.OPEN.value),
        )
        if row is None:
            return None
        return TradeMemoryRecord.model_validate(row["payload"])

    def save_active_strategy(self, symbol: str, genome: StrategyGenome) -> None:
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.active_strategies (symbol, payload, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (symbol)
            DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
            """,
            (symbol, genome.model_dump(mode="json")),
        )

    def load_active_strategy(self, symbol: str) -> StrategyGenome | None:
        row = self._fetch_one(
            f"""
            SELECT payload
            FROM {self.schema}.active_strategies
            WHERE symbol = %s
            """,
            (symbol,),
        )
        if row is None:
            return None
        return StrategyGenome.model_validate(row["payload"])

    def delete_active_strategy(self, symbol: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM {self.schema}.active_strategies WHERE symbol = %s",
                    (symbol,),
                )
            connection.commit()

    def save_strategy_registry(self, symbol: str, entries: list[StrategyRegistryEntry]) -> None:
        payload = [entry.model_dump(mode="json") for entry in entries]
        self._upsert_json(
            f"""
            INSERT INTO {self.schema}.strategy_registry (symbol, payload, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (symbol)
            DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
            """,
            (symbol, payload),
        )

    def load_strategy_registry(self, symbol: str) -> list[StrategyRegistryEntry]:
        row = self._fetch_one(
            f"""
            SELECT payload
            FROM {self.schema}.strategy_registry
            WHERE symbol = %s
            """,
            (symbol,),
        )
        if row is None:
            return []
        return [StrategyRegistryEntry.model_validate(item) for item in row["payload"]]

    def close(self) -> None:
        return None

    def _upsert_json(self, statement: str, params: tuple[Any, ...]) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, self._wrap_json_params(params))
            connection.commit()

    def _fetch_one(self, statement: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, params)
                return cursor.fetchone()

    def _fetch_all(self, statement: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, params)
                return list(cursor.fetchall())

    def _wrap_json_params(self, params: tuple[Any, ...]) -> tuple[Any, ...]:
        try:
            from psycopg.types.json import Jsonb
        except ImportError as exc:
            raise RuntimeError(
                "Postgres storage selected but the 'psycopg' package is not installed."
            ) from exc
        wrapped: list[Any] = []
        for value in params:
            if isinstance(value, (dict, list)):
                wrapped.append(Jsonb(value))
                continue
            wrapped.append(value)
        return tuple(wrapped)

    def _sanitize_identifier(self, value: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
        return sanitized or "project_invest"
