from __future__ import annotations

from pathlib import Path
import pytest
from pydantic import ValidationError

from project_invest.config import Settings


def test_settings_parse_csv_symbols_and_storage_backend() -> None:
    configured = Settings(
        research_symbols="RELIANCE.NS,TCS.NS,INFY.NS",
        execution_markets="NSE,US",
        storage_backend="POSTGRES",
    )

    assert configured.research_symbols == ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    assert configured.execution_markets == ["NSE", "US"]
    assert configured.storage_backend == "postgres"
    assert configured.execution_mode == "paper"


def test_settings_normalize_and_validate_base_currency() -> None:
    assert Settings(base_currency=" usd ").base_currency == "USD"
    with pytest.raises(ValidationError, match="base_currency"):
        Settings(base_currency="rupees")


@pytest.mark.parametrize("execution_mode", ["live", "LIVE", "unsupported"])
def test_settings_reject_unsupported_execution_modes(execution_mode: str) -> None:
    with pytest.raises(ValidationError, match="execution_mode"):
        Settings(execution_mode=execution_mode)


def test_mock_data_requires_explicit_test_or_development_opt_in() -> None:
    with pytest.raises(ValidationError, match="Mock market data requires"):
        Settings(market_data_provider="mock")

    configured = Settings(
        environment="test",
        market_data_provider="mock",
        allow_mock_data=True,
    )
    assert configured.market_data_provider == "mock"


def test_documented_environment_example_loads_safely() -> None:
    example = Path(__file__).parents[1] / ".env.example"
    configured = Settings(_env_file=example)

    assert configured.execution_mode == "paper"
    assert configured.market_data_provider == "yahoo"
    assert configured.allow_mock_fallback is False
