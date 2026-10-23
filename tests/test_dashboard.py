from __future__ import annotations

from project_invest.api.dashboard import render_dashboard


def test_active_dashboard_keeps_operational_controls_and_data_views() -> None:
    html = render_dashboard("<Project Invest>", auto_local_auth=True)

    assert "&lt;Project Invest&gt;" in html
    assert "Run Research Cycle" in html
    assert "Run Trading Cycle" in html
    assert "/api/research/run" in html
    assert "/api/trading/run" in html
    assert "/api/portfolio" in html
    assert "Local controls enabled" in html
    assert "fetchWithTimeout" in html
    assert "Workers have not reported a heartbeat yet" in html
