from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from math import ceil

import httpx

from project_invest.domain.models import Candle
from project_invest.providers.base import MarketDataProviderError


class YahooFinanceProvider:
    name = "yahoo"

    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://finance.yahoo.com",
            "Referer": "https://finance.yahoo.com/",
        }

    async def fetch_candles(self, symbol: str, interval: str, lookback_bars: int) -> list[Candle]:
        now = datetime.now(timezone.utc)
        history_window = self._history_window(interval, lookback_bars)
        period1 = int((now - history_window).timestamp())
        period2 = int(now.timestamp())

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {
            "period1": period1,
            "period2": period2,
            "interval": interval,
            "includePrePost": "false",
            "events": "div,splits",
        }

        payload = await self._fetch_payload(url, params)

        chart = payload.get("chart", {})
        error = chart.get("error")
        if error:
            raise MarketDataProviderError(str(error))

        results = chart.get("result") or []
        if not results:
            raise MarketDataProviderError(f"No Yahoo data returned for {symbol}.")

        result = results[0]
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        candles: list[Candle] = []
        for index, ts in enumerate(timestamps):
            try:
                open_price = float(opens[index])
                high_price = float(highs[index])
                low_price = float(lows[index])
                close_price = float(closes[index])
                volume = float(volumes[index] or 0.0)
            except (IndexError, TypeError, ValueError):
                continue

            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                    data_source=self.name,
                )
            )

        if not candles:
            raise MarketDataProviderError(f"Yahoo returned only empty bars for {symbol}.")

        return candles[-lookback_bars:]

    async def _fetch_payload(self, url: str, params: dict[str, str | int]) -> dict[str, object]:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=self.headers, follow_redirects=True) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    if exc.response.status_code != 429 or attempt == 2:
                        break
                    await asyncio.sleep(1.25 * (attempt + 1))
                except httpx.HTTPError as exc:
                    raise MarketDataProviderError(f"Yahoo request failed: {exc}") from exc

        if isinstance(last_error, httpx.HTTPStatusError):
            raise MarketDataProviderError(
                f"Yahoo request failed with status {last_error.response.status_code}: {last_error.response.text[:200]}"
            ) from last_error
        raise MarketDataProviderError("Yahoo request failed for an unknown reason.")

    def _interval_to_delta(self, interval: str) -> timedelta:
        if interval.endswith("m"):
            return timedelta(minutes=int(interval[:-1]))
        if interval.endswith("h"):
            return timedelta(hours=int(interval[:-1]))
        if interval.endswith("d") and interval[:-1].isdigit():
            return timedelta(days=int(interval[:-1]))
        return timedelta(days=1)

    def _history_window(self, interval: str, lookback_bars: int) -> timedelta:
        if lookback_bars <= 0:
            return timedelta(days=5)

        if interval.endswith("m") and interval[:-1].isdigit():
            interval_minutes = int(interval[:-1])
            return timedelta(days=self._intraday_calendar_days(lookback_bars, interval_minutes, max_days=60))

        if interval.endswith("h") and interval[:-1].isdigit():
            interval_minutes = int(interval[:-1]) * 60
            return timedelta(days=self._intraday_calendar_days(lookback_bars, interval_minutes, max_days=180))

        if interval.endswith("d") and interval[:-1].isdigit():
            trading_days = int(interval[:-1]) * lookback_bars
            calendar_days = ceil(trading_days * (7 / 5)) + 10
            return timedelta(days=max(calendar_days, 30))

        return self._interval_to_delta(interval) * lookback_bars

    def _intraday_calendar_days(
        self,
        lookback_bars: int,
        interval_minutes: int,
        max_days: int,
    ) -> int:
        total_trading_minutes = max(1, lookback_bars * interval_minutes)
        trading_days = total_trading_minutes / 390
        calendar_days = ceil(trading_days * (7 / 5)) + 4
        return max(5, min(calendar_days, max_days))
