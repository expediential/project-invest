from __future__ import annotations

from statistics import fmean, pstdev

from project_invest.domain.models import Candle, FeatureRow
from project_invest.services.sentiment import SentimentProvider, SentimentSnapshot


class FeatureEngineeringEngine:
    def __init__(self, sentiment_provider: SentimentProvider | None = None) -> None:
        self.sentiment_provider = sentiment_provider

    def build_feature_rows(self, candles: list[Candle]) -> list[FeatureRow]:
        if not candles:
            return []

        closes = [candle.close for candle in candles]
        volumes = [candle.volume for candle in candles]
        ema_12 = self._ema_series(closes, 12)
        ema_26 = self._ema_series(closes, 26)
        rsi_14 = self._rsi_series(closes, 14)
        rows: list[FeatureRow] = []
        for index, candle in enumerate(candles):
            sentiment_snapshot = self._sentiment_snapshot(candle.symbol, candle.timestamp)
            rows.append(
                FeatureRow(
                    symbol=candle.symbol,
                    timestamp=candle.timestamp,
                    close=candle.close,
                    sma_5=self._window_mean(closes, index, 5),
                    sma_20=self._window_mean(closes, index, 20),
                    ema_12=ema_12[index],
                    ema_26=ema_26[index],
                    rsi_14=rsi_14[index],
                    momentum_5=self._momentum(closes, index, 5),
                    volatility_10=self._volatility(closes, index, 10),
                    volume_zscore_20=self._zscore(volumes, index, 20),
                    sentiment_score=sentiment_snapshot.score,
                    news_intensity=sentiment_snapshot.intensity,
                )
            )
        return rows

    def _window_mean(self, values: list[float], index: int, window: int) -> float | None:
        if index + 1 < window:
            return None
        return round(fmean(values[index - window + 1 : index + 1]), 6)

    def _ema_series(self, values: list[float], window: int) -> list[float | None]:
        if not values:
            return []
        multiplier = 2 / (window + 1)
        ema_values: list[float | None] = []
        ema: float | None = None
        for value in values:
            ema = value if ema is None else ((value - ema) * multiplier) + ema
            ema_values.append(round(ema, 6))
        return ema_values

    def _rsi_series(self, values: list[float], window: int) -> list[float | None]:
        rsi_values: list[float | None] = [None]
        if len(values) == 1:
            return rsi_values

        for index in range(1, len(values)):
            if index < window:
                rsi_values.append(None)
                continue

            deltas = [values[pos] - values[pos - 1] for pos in range(index - window + 1, index + 1)]
            gains = [delta for delta in deltas if delta > 0]
            losses = [-delta for delta in deltas if delta < 0]
            average_gain = sum(gains) / window if gains else 0.0
            average_loss = sum(losses) / window if losses else 0.0

            if average_loss == 0:
                rsi_values.append(100.0)
                continue

            relative_strength = average_gain / average_loss
            rsi = 100 - (100 / (1 + relative_strength))
            rsi_values.append(round(rsi, 6))

        return rsi_values

    def _momentum(self, values: list[float], index: int, window: int) -> float | None:
        if index < window:
            return None
        prior = values[index - window]
        if prior == 0:
            return None
        return round((values[index] / prior) - 1, 6)

    def _volatility(self, values: list[float], index: int, window: int) -> float | None:
        if index < window:
            return None
        sample = values[index - window : index + 1]
        returns = []
        for pos in range(1, len(sample)):
            previous = sample[pos - 1]
            if previous == 0:
                return None
            returns.append((sample[pos] / previous) - 1)
        if len(returns) < 2:
            return None
        return round(pstdev(returns), 6)

    def _zscore(self, values: list[float], index: int, window: int) -> float | None:
        if index + 1 < window:
            return None
        sample = values[index - window + 1 : index + 1]
        std_dev = pstdev(sample)
        if std_dev == 0:
            return 0.0
        mean_value = fmean(sample)
        return round((values[index] - mean_value) / std_dev, 6)

    def _sentiment_snapshot(self, symbol: str, as_of) -> SentimentSnapshot:
        if self.sentiment_provider is None:
            return SentimentSnapshot(score=0.0, intensity=0.0)
        return self.sentiment_provider.get_snapshot(symbol, as_of=as_of)
