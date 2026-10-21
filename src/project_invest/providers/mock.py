from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from project_invest.domain.models import Candle


class MockMarketDataProvider:
    name = "mock"

    async def fetch_candles(self, symbol: str, interval: str, lookback_bars: int) -> list[Candle]:
        step = self._interval_to_delta(interval)
        now = datetime.now(timezone.utc)
        rng = random.Random(f"{symbol}:{interval}:{lookback_bars}")

        base_price = 1000 + (abs(hash(symbol)) % 2500)
        price = float(base_price)
        candles: list[Candle] = []

        for index in range(lookback_bars):
            timestamp = now - step * (lookback_bars - index)

            drift = 0.0007
            seasonal = 0.004 * ((index % 20) - 10) / 10
            shock = rng.uniform(-0.018, 0.018)
            close = max(1.0, price * (1 + drift + seasonal + shock))
            high = max(price, close) * (1 + rng.uniform(0.001, 0.01))
            low = min(price, close) * (1 - rng.uniform(0.001, 0.01))
            volume = float(rng.randint(1_000, 50_000))

            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=round(price, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(close, 2),
                    volume=volume,
                    data_source=self.name,
                )
            )
            price = close

        return candles

    def _interval_to_delta(self, interval: str) -> timedelta:
        if interval.endswith("m"):
            return timedelta(minutes=int(interval[:-1]))
        if interval.endswith("h"):
            return timedelta(hours=int(interval[:-1]))
        if interval.endswith("d") and interval[:-1].isdigit():
            return timedelta(days=int(interval[:-1]))
        return timedelta(days=1)

