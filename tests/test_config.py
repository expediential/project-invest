from __future__ import annotations

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
