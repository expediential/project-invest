from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Project Invest"
    base_currency: str = "INR"
    environment: Literal["development", "test", "production"] = "development"
    execution_mode: Literal["paper"] = "paper"
    market_data_provider: Literal["yahoo", "mock"] = "yahoo"
    allow_mock_data: bool = False
    allow_mock_fallback: bool = False
    api_auth_token: SecretStr | None = None
    storage_backend: str = "local"
    research_symbols: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    )
    symbol_groups: Annotated[list[list[str]], NoDecode] = Field(default_factory=list)
    symbol_group_size: int = 0
    use_market_universes: bool = True
    market_universes: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["NSE"])
    execution_markets: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["NSE"])
    research_interval: str = "1d"
    lookback_bars: int = 365
    trading_interval: str = "5m"
    trading_lookback_bars: int = 240
    confirmation_intervals: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["30m", "1h"])
    confirmation_lookback_bars: int = 240
    confirmation_short_window: int = 10
    confirmation_long_window: int = 30
    confirmation_min_trend_strength: float = 0.0016
    research_loop_enabled: bool = False
    research_loop_seconds: int = 21600
    trading_loop_enabled: bool = False
    trading_loop_seconds: int = 900
    live_loop_enabled: bool = False
    live_loop_seconds: int = 300

    starting_capital: float = 100000.0
    max_risk_per_trade: float = 0.01
    live_max_risk_per_trade: float = 0.005
    max_daily_loss: float = 0.03
    max_positions: int = 12
    max_gross_exposure: float = 0.4
    max_position_pct: float = 0.08
    max_drawdown: float = 0.15

    order_slippage_bps: float = 8.0
    fee_bps: float = 3.0

    population_size: int = 40
    generations: int = 12
    evolution_seed: int = 42
    min_validation_sharpe: float = 0.0
    min_validation_return: float = 0.0
    max_validation_drawdown: float = 0.2
    min_validation_trades: int = 20
    min_validation_profit_factor: float = 1.0
    min_validation_win_rate: float = 0.5
    min_validation_trade_coverage: float = 0.05
    max_validation_return_gap: float = 0.15
    max_validation_sharpe_gap: float = 3.0

    regime_trend_threshold: float = 0.012
    regime_high_vol_threshold: float = 0.02
    regime_low_vol_threshold: float = 0.004
    regime_lookback: int = 80

    data_root: Path = Path("runtime/data_lake")
    postgres_dsn: str | None = None
    postgres_schema: str = "project_invest"
    redis_url: str | None = None
    redis_key_prefix: str = "project_invest"
    redis_default_ttl_seconds: int | None = 900
    storage_cache_enabled: bool = False

    sentiment_provider: str = "neutral"
    sentiment_data_root: Path = Path("runtime/sentiment")
    sentiment_min_intensity: float = 0.2
    sentiment_confidence_boost: float = 0.16
    sentiment_confidence_penalty: float = 0.24
    sentiment_reversal_block_threshold: float = 0.42
    sentiment_memory_enabled: bool = True
    sentiment_memory_lookback: int = 500
    sentiment_memory_min_records: int = 4

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PROJECT_INVEST_",
        extra="ignore",
    )

    @field_validator("research_symbols", mode="before")
    @classmethod
    def parse_symbols(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS"]

    @field_validator("symbol_groups", mode="before")
    @classmethod
    def parse_symbol_groups(cls, value: str | list[list[str]] | None) -> list[list[str]]:
        if value is None:
            return []
        if isinstance(value, list):
            return [group for group in value if group]
        if isinstance(value, str):
            groups = []
            for raw_group in value.split("|"):
                symbols = [item.strip() for item in raw_group.split(",") if item.strip()]
                if symbols:
                    groups.append(symbols)
            return groups
        return []

    @field_validator("market_universes", mode="before")
    @classmethod
    def parse_market_universes(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [item.strip().upper() for item in value if isinstance(item, str) and item.strip()]
        if isinstance(value, str):
            return [item.strip().upper() for item in value.split(",") if item.strip()]
        return []

    @field_validator("execution_markets", mode="before")
    @classmethod
    def parse_execution_markets(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [item.strip().upper() for item in value if isinstance(item, str) and item.strip()]
        if isinstance(value, str):
            return [item.strip().upper() for item in value.split(",") if item.strip()]
        return []

    @field_validator("confirmation_intervals", mode="before")
    @classmethod
    def parse_confirmation_intervals(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    @field_validator("execution_mode", "market_data_provider", "environment", mode="before")
    @classmethod
    def normalize_enum_value(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("storage_backend", mode="before")
    @classmethod
    def parse_storage_backend(cls, value: str) -> str:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"local", "postgres"}:
                return normalized
        return "local"

    @field_validator("base_currency", mode="before")
    @classmethod
    def normalize_base_currency(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("base_currency must be a three-letter ISO currency code.")
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("base_currency must be a three-letter ISO currency code.")
        return normalized

    @field_validator("sentiment_provider", mode="before")
    @classmethod
    def parse_sentiment_provider(cls, value: str) -> str:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"neutral", "local"}:
                return normalized
        return "neutral"

    @model_validator(mode="after")
    def validate_safe_operation(self) -> "Settings":
        if self.execution_mode != "paper":
            raise ValueError("Only paper execution is supported; live execution is disabled.")
        if self.allow_mock_fallback:
            raise ValueError("Mock-data fallback is disabled. Use an explicit development/test mock provider instead.")
        if self.market_data_provider == "mock" and (
            self.environment not in {"development", "test"} or not self.allow_mock_data
        ):
            raise ValueError(
                "Mock market data requires PROJECT_INVEST_ENVIRONMENT=development or test "
                "and PROJECT_INVEST_ALLOW_MOCK_DATA=true."
            )
        if any((self.research_loop_enabled, self.trading_loop_enabled, self.live_loop_enabled)):
            raise ValueError(
                "Embedded API loops are disabled. Run exactly one standalone research or trading worker."
            )
        if self.max_risk_per_trade <= 0 or self.max_risk_per_trade > 1:
            raise ValueError("max_risk_per_trade must be greater than 0 and no more than 1.")
        if self.order_slippage_bps < 0 or self.fee_bps < 0:
            raise ValueError("order_slippage_bps and fee_bps must be non-negative.")
        return self


settings = Settings()
