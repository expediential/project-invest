from __future__ import annotations

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
from project_invest.storage.cache import JsonCache
from project_invest.storage.repositories import ResearchStorage


class CachedResearchStorage:
    def __init__(self, durable_storage: ResearchStorage, cache: JsonCache) -> None:
        self.durable_storage = durable_storage
        self.cache = cache
        self.backend_name = f"{durable_storage.backend_name}+{cache.backend_name}"

    def store_candles(self, symbol: str, interval: str, candles: list[Candle], stage: str) -> None:
        self.durable_storage.store_candles(symbol, interval, candles, stage)
        key = self._candles_key(stage, symbol, interval)
        payload = [candle.model_dump(mode="json") for candle in candles]
        self.cache.set(key, payload)

    def load_candles(self, symbol: str, interval: str, stage: str) -> list[Candle]:
        key = self._candles_key(stage, symbol, interval)
        cached = self.cache.get(key)
        if cached is not None:
            return [Candle.model_validate(item) for item in cached]
        candles = self.durable_storage.load_candles(symbol, interval, stage)
        if candles:
            payload = [candle.model_dump(mode="json") for candle in candles]
            self.cache.set(key, payload)
        return candles

    def store_features(self, symbol: str, interval: str, rows: list[FeatureRow]) -> None:
        self.durable_storage.store_features(symbol, interval, rows)
        key = self._features_key(symbol, interval)
        payload = [row.model_dump(mode="json") for row in rows]
        self.cache.set(key, payload)

    def load_features(self, symbol: str, interval: str) -> list[FeatureRow]:
        key = self._features_key(symbol, interval)
        cached = self.cache.get(key)
        if cached is not None:
            return [FeatureRow.model_validate(item) for item in cached]
        rows = self.durable_storage.load_features(symbol, interval)
        if rows:
            payload = [row.model_dump(mode="json") for row in rows]
            self.cache.set(key, payload)
        return rows

    def save_portfolio(self, portfolio: PortfolioSnapshot) -> None:
        self.durable_storage.save_portfolio(portfolio)
        self.cache.set("portfolio:latest", portfolio.model_dump(mode="json"))

    def load_portfolio(self) -> PortfolioSnapshot | None:
        cached = self.cache.get("portfolio:latest")
        if cached is not None:
            return PortfolioSnapshot.model_validate(cached)
        portfolio = self.durable_storage.load_portfolio()
        if portfolio is not None:
            self.cache.set("portfolio:latest", portfolio.model_dump(mode="json"))
        return portfolio

    def load_portfolio_history(self, limit: int | None = None) -> list[PortfolioHistorySnapshot]:
        return self.durable_storage.load_portfolio_history(limit=limit)

    def append_trade(self, trade: ExecutionOrder) -> None:
        self.durable_storage.append_trade(trade)
        history = self.cache.get("trades:history")
        if history is None:
            return
        payload = trade.model_dump(mode="json")
        existing_index = next(
            (index for index, item in enumerate(history) if item.get("trade_id") == trade.trade_id),
            None,
        )
        if existing_index is None:
            history.append(payload)
        elif history[existing_index] != payload:
            history[existing_index] = payload
        self.cache.set("trades:history", history)

    def load_trades(self, limit: int | None = None) -> list[ExecutionOrder]:
        history = self.cache.get("trades:history")
        if history is None:
            trades = self.durable_storage.load_trades()
            history = [trade.model_dump(mode="json") for trade in trades]
            self.cache.set("trades:history", history)
        trades = [ExecutionOrder.model_validate(item) for item in history]
        if limit is None:
            return trades
        return trades[-limit:]

    def save_latest_report(self, report: ResearchCycleReport, stream: str = "research") -> None:
        self.durable_storage.save_latest_report(report, stream=stream)
        self.cache.set(f"reports:latest:{stream}", report.model_dump(mode="json"))

    def load_latest_report(self, stream: str = "research") -> ResearchCycleReport | None:
        cached = self.cache.get(f"reports:latest:{stream}")
        if cached is not None:
            return ResearchCycleReport.model_validate(cached)
        report = self.durable_storage.load_latest_report(stream=stream)
        if report is not None:
            self.cache.set(f"reports:latest:{stream}", report.model_dump(mode="json"))
        return report

    def append_event(self, event: ResearchEvent) -> None:
        self.durable_storage.append_event(event)
        history = self.cache.get("events:history")
        if history is None:
            return
        history.append(event.model_dump(mode="json"))
        self.cache.set("events:history", history)

    def load_events(self, limit: int | None = None) -> list[ResearchEvent]:
        history = self.cache.get("events:history")
        if history is None:
            events = self.durable_storage.load_events()
            history = [event.model_dump(mode="json") for event in events]
            self.cache.set("events:history", history)
        events = [ResearchEvent.model_validate(item) for item in history]
        if limit is None:
            return events
        return events[-limit:]

    def save_trade_memory(self, record: TradeMemoryRecord) -> None:
        self.durable_storage.save_trade_memory(record)
        history = self.cache.get("trade-memory:history")
        if history is None:
            return
        updated = False
        for index, item in enumerate(history):
            if item.get("memory_id") == record.memory_id:
                history[index] = record.model_dump(mode="json")
                updated = True
                break
        if not updated:
            history.append(record.model_dump(mode="json"))
        self.cache.set("trade-memory:history", history)

    def load_trade_memory(self, limit: int | None = None) -> list[TradeMemoryRecord]:
        history = self.cache.get("trade-memory:history")
        if history is None:
            records = self.durable_storage.load_trade_memory()
            history = [record.model_dump(mode="json") for record in records]
            self.cache.set("trade-memory:history", history)
        records = [TradeMemoryRecord.model_validate(item) for item in history]
        if limit is None:
            return records
        return records[-limit:]

    def load_open_trade_memory(self, symbol: str) -> TradeMemoryRecord | None:
        records = self.load_trade_memory()
        for record in reversed(records):
            if record.symbol == symbol and record.status == TradeMemoryStatus.OPEN:
                return record
        return None

    def save_active_strategy(self, symbol: str, genome: StrategyGenome) -> None:
        self.durable_storage.save_active_strategy(symbol, genome)
        self.cache.set(self._active_strategy_key(symbol), genome.model_dump(mode="json"))

    def load_active_strategy(self, symbol: str) -> StrategyGenome | None:
        key = self._active_strategy_key(symbol)
        cached = self.cache.get(key)
        if cached is not None:
            return StrategyGenome.model_validate(cached)
        genome = self.durable_storage.load_active_strategy(symbol)
        if genome is not None:
            self.cache.set(key, genome.model_dump(mode="json"))
        return genome

    def delete_active_strategy(self, symbol: str) -> None:
        self.durable_storage.delete_active_strategy(symbol)
        self.cache.delete(self._active_strategy_key(symbol))

    def save_strategy_registry(self, symbol: str, entries: list[StrategyRegistryEntry]) -> None:
        self.durable_storage.save_strategy_registry(symbol, entries)
        payload = [entry.model_dump(mode="json") for entry in entries]
        self.cache.set(self._strategy_registry_key(symbol), payload)

    def load_strategy_registry(self, symbol: str) -> list[StrategyRegistryEntry]:
        key = self._strategy_registry_key(symbol)
        cached = self.cache.get(key)
        if cached is not None:
            return [StrategyRegistryEntry.model_validate(item) for item in cached]
        entries = self.durable_storage.load_strategy_registry(symbol)
        if entries:
            payload = [entry.model_dump(mode="json") for entry in entries]
            self.cache.set(key, payload)
        return entries

    def close(self) -> None:
        self.durable_storage.close()
        self.cache.close()

    def _candles_key(self, stage: str, symbol: str, interval: str) -> str:
        return f"candles:{stage}:{symbol}:{interval}"

    def _features_key(self, symbol: str, interval: str) -> str:
        return f"features:{symbol}:{interval}"

    def _active_strategy_key(self, symbol: str) -> str:
        return f"strategy:active:{symbol}"

    def _strategy_registry_key(self, symbol: str) -> str:
        return f"strategy:registry:{symbol}"
