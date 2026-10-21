from __future__ import annotations

from project_invest.api.terminal_dashboard import render_dashboard


def test_terminal_dashboard_has_all_monitoring_pages_and_safe_data_sources() -> None:
    html = render_dashboard("<Project Invest>", auto_local_auth=True)

    for label in (
        "Overview",
        "Portfolio",
        "Positions",
        "Orders &amp; Trades",
        "Opportunities",
        "Strategies",
        "Experiments",
        "Research Jobs / Cosmos",
        "Data Quality",
        "System Health",
        "Settings",
    ):
        assert label in html

    assert "&lt;Project Invest&gt;" in html
    assert "Local controls enabled" in html
    assert "/api/portfolio/summary" in html
    assert "/api/data-quality" in html
    assert "/api/research/compute-status" in html
    assert "No fabricated history" in html
    assert "PAPER TRADING" in html
    assert "/api/market" not in html
