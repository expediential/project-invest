from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from project_invest.services.sentiment import LocalSentimentProvider


def test_local_sentiment_provider_uses_fallback_root(tmp_path) -> None:
    configured_root = tmp_path / "runtime" / "sentiment"
    fallback_root = tmp_path / "runtime" / "data_lake" / "sentiment"
    fallback_root.mkdir(parents=True)
    (fallback_root / "default.json").write_text(
        json.dumps({"score": 0.25, "intensity": 0.4}),
        encoding="utf-8",
    )

    provider = LocalSentimentProvider(configured_root)
    provider.fallback_root = fallback_root

    snapshot = provider.get_snapshot("RELIANCE.NS")

    assert snapshot.score == 0.25
    assert snapshot.intensity == 0.4


def test_local_sentiment_provider_excludes_future_or_unavailable_observations(tmp_path) -> None:
    root = tmp_path / "sentiment"
    root.mkdir()
    decision_time = datetime(2025, 1, 5, tzinfo=timezone.utc)
    payload = {
        "observations": [
            {"published_at": "2025-01-02T09:00:00Z", "observed_at": "2025-01-02T09:05:00Z", "score": 0.2, "intensity": 0.4},
            {"published_at": "2025-01-04T09:00:00Z", "observed_at": "2025-01-06T09:05:00Z", "score": -0.9, "intensity": 1.0},
        ]
    }
    (root / "RELIANCE.NS.json").write_text(json.dumps(payload), encoding="utf-8")

    snapshot = LocalSentimentProvider(root).get_snapshot("RELIANCE.NS", as_of=decision_time)

    assert snapshot.score == 0.2
    assert snapshot.intensity == 0.4
