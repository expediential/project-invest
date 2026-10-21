from __future__ import annotations

from datetime import datetime, timedelta, timezone

from project_invest.domain.models import Candle
from project_invest.services.feature_engineering import FeatureEngineeringEngine
from project_invest.services.sentiment import LocalSentimentProvider
import json


def make_candles(count: int, base_price: float = 100.0) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles: list[Candle] = []
    price = base_price
    for index in range(count):
        close = price + 1.5 + (index % 3)
        candles.append(
            Candle(
                symbol="TEST",
                timestamp=start + timedelta(days=index),
                open=price,
                high=close + 1,
                low=price - 1,
                close=close,
                volume=1000 + (index * 25),
            )
        )
        price = close
    return candles


def test_feature_engine_builds_expected_indicators() -> None:
    engine = FeatureEngineeringEngine()
    rows = engine.build_feature_rows(make_candles(30))

    assert len(rows) == 30
    assert rows[-1].sma_5 is not None
    assert rows[-1].sma_20 is not None
    assert rows[-1].ema_12 is not None
    assert rows[-1].ema_26 is not None
    assert rows[-1].rsi_14 is not None
    assert rows[-1].momentum_5 is not None
    assert rows[-1].volatility_10 is not None
    assert rows[-1].volume_zscore_20 is not None


def test_feature_rows_only_use_sentiment_available_at_each_timestamp(tmp_path) -> None:
    root = tmp_path / "sentiment"
    root.mkdir()
    (root / "TEST.json").write_text(
        json.dumps({"observations": [
            {"published_at": "2025-01-09T08:00:00Z", "observed_at": "2025-01-09T08:01:00Z", "score": 0.9, "intensity": 0.8}
        ]}),
        encoding="utf-8",
    )
    rows = FeatureEngineeringEngine(LocalSentimentProvider(root)).build_feature_rows(make_candles(12))

    assert rows[0].sentiment_score == 0.0
    assert rows[8].sentiment_score == 0.0
    assert rows[9].sentiment_score == 0.9

