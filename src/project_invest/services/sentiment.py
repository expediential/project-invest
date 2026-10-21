from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

POSITIVE_WORDS = {
    "beat",
    "upgrade",
    "strong",
    "growth",
    "record",
    "surge",
    "profit",
    "bull",
    "optimistic",
    "positive",
}

NEGATIVE_WORDS = {
    "miss",
    "downgrade",
    "weak",
    "decline",
    "drop",
    "loss",
    "bear",
    "pessimistic",
    "negative",
    "fall",
}


@dataclass(frozen=True)
class SentimentSnapshot:
    score: float
    intensity: float
    publication_time: datetime | None = None
    observed_at: datetime | None = None


class SentimentProvider:
    def get_snapshot(self, symbol: str, as_of: datetime | None = None) -> SentimentSnapshot:
        raise NotImplementedError


class NeutralSentimentProvider(SentimentProvider):
    def get_snapshot(self, symbol: str, as_of: datetime | None = None) -> SentimentSnapshot:
        return SentimentSnapshot(score=0.0, intensity=0.0)


class LocalSentimentProvider(SentimentProvider):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.fallback_root = Path("runtime/data_lake/sentiment")

    def get_snapshot(self, symbol: str, as_of: datetime | None = None) -> SentimentSnapshot:
        payload = self._load_payload(symbol)
        if payload is None:
            return SentimentSnapshot(score=0.0, intensity=0.0)

        observations = payload.get("observations")
        if isinstance(observations, list):
            return self._snapshot_as_of(observations, as_of)

        # Legacy static payloads have no trustworthy availability timestamp.
        # They may be inspected for a current dashboard view but are never used
        # to reconstruct historical feature rows or backtests.
        if "score" in payload and "intensity" in payload and as_of is None:
            return SentimentSnapshot(score=float(payload.get("score", 0.0)), intensity=float(payload.get("intensity", 0.0)))

        headlines = payload.get("headlines", [])
        if not headlines:
            return SentimentSnapshot(score=0.0, intensity=0.0)

        score = self._score_headlines(headlines)
        intensity = min(1.0, len(headlines) / 20)
        return SentimentSnapshot(score=score, intensity=intensity)

    def _snapshot_as_of(self, observations: list[object], as_of: datetime | None) -> SentimentSnapshot:
        if as_of is None:
            return SentimentSnapshot(score=0.0, intensity=0.0)
        eligible: list[tuple[datetime, float, float, datetime]] = []
        for raw in observations:
            if not isinstance(raw, dict):
                continue
            published_at = self._parse_timestamp(raw.get("published_at"))
            observed_at = self._parse_timestamp(raw.get("observed_at"))
            if published_at is None or observed_at is None or observed_at > as_of:
                continue
            try:
                score = float(raw["score"])
                intensity = float(raw["intensity"])
            except (KeyError, TypeError, ValueError):
                continue
            eligible.append((published_at, score, intensity, observed_at))
        if not eligible:
            return SentimentSnapshot(score=0.0, intensity=0.0)
        latest_published, score, intensity, observed_at = max(eligible, key=lambda item: item[0])
        return SentimentSnapshot(
            score=max(-1.0, min(1.0, score)),
            intensity=max(0.0, min(1.0, intensity)),
            publication_time=latest_published,
            observed_at=observed_at,
        )

    def _parse_timestamp(self, value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)

    def _load_payload(self, symbol: str) -> dict | None:
        safe_symbol = symbol.replace("/", "_")
        search_roots: list[Path] = [self.root]
        if self.fallback_root != self.root:
            search_roots.append(self.fallback_root)

        for base_root in search_roots:
            for filename in (f"{safe_symbol}.json", "default.json"):
                path = base_root / filename
                if path.exists():
                    return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _score_headlines(self, headlines: list[str]) -> float:
        if not headlines:
            return 0.0
        score = 0.0
        for headline in headlines:
            lowered = headline.lower()
            for word in POSITIVE_WORDS:
                if word in lowered:
                    score += 1.0
            for word in NEGATIVE_WORDS:
                if word in lowered:
                    score -= 1.0
        normalized = score / max(len(headlines), 1)
        return max(-1.0, min(1.0, normalized))
