from __future__ import annotations

from html import escape


def render_dashboard(app_name: str, auto_local_auth: bool = False) -> str:
    safe_app_name = escape(app_name)
    auth_control = (
        '<span class="local-auth">Local controls enabled</span>'
        if auto_local_auth
        else '<label>Operational token <input id="operational-token" type="password" autocomplete="off"></label>'
    )
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{safe_app_name} Terminal</title>
    <style>
      :root {{
        color-scheme: dark;
        --bg: #0f172a;
        --panel: #121c2f;
        --panel-2: #1e293b;
        --panel-3: #0b1324;
        --border: rgba(148, 163, 184, 0.18);
        --ink: #e2e8f0;
        --muted: #94a3b8;
        --accent: #38bdf8;
        --buy: #22c55e;
        --sell: #ef4444;
        --hold: #facc15;
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        font-family: Consolas, "SFMono-Regular", "Segoe UI", sans-serif;
        background: radial-gradient(circle at top, rgba(56, 189, 248, 0.08), transparent 45%), var(--bg);
        color: var(--ink);
        min-height: 100vh;
      }}

      .terminal {{
        max-width: 1560px;
        margin: 0 auto;
        padding: 20px 18px 40px;
      }}

      .workstation-shell {{
        display: grid;
        grid-template-columns: 224px minmax(0, 1fr);
        gap: 16px;
        align-items: start;
      }}

      .workspace-nav {{
        position: sticky;
        top: 16px;
        padding: 12px;
        border: 1px solid var(--border);
        border-radius: 18px;
        background: rgba(11, 19, 36, 0.92);
        box-shadow: 0 18px 30px rgba(2, 6, 23, 0.28);
      }}

      .workspace-nav .nav-title {{
        padding: 8px 10px 12px;
        color: var(--muted);
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
      }}

      .workspace-nav button {{
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: 2px 0;
        padding: 9px 10px;
        border-radius: 10px;
        border-color: transparent;
        background: transparent;
        color: var(--muted);
        font-size: 0.8rem;
        text-align: left;
      }}

      .workspace-nav button:hover,
      .workspace-nav button.active {{
        color: var(--ink);
        background: rgba(56, 189, 248, 0.12);
        border-color: rgba(56, 189, 248, 0.24);
        box-shadow: none;
      }}

      .workspace-content {{
        min-width: 0;
      }}

      .runtime-board {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-top: 16px;
      }}

      .runtime-card {{
        min-height: 134px;
        padding: 14px;
        border: 1px solid var(--border);
        border-radius: 16px;
        background: linear-gradient(180deg, rgba(18, 28, 47, 0.98), rgba(11, 19, 36, 0.96));
      }}

      .runtime-card h2 {{
        margin: 0 0 10px;
        color: var(--muted);
        font-size: 0.7rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
      }}

      .runtime-card .runtime-value {{
        font-size: 1rem;
        font-weight: 700;
        overflow-wrap: anywhere;
      }}

      .runtime-card .runtime-detail {{
        margin-top: 8px;
        color: var(--muted);
        font-size: 0.78rem;
        line-height: 1.45;
        overflow-wrap: anywhere;
      }}

      .data-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
      }}

      .data-table th,
      .data-table td {{
        padding: 10px 8px;
        border-bottom: 1px solid var(--border);
        text-align: left;
        white-space: nowrap;
      }}

      .data-table th {{
        color: var(--muted);
        font-size: 0.68rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
      }}

      .table-wrap {{
        overflow-x: auto;
      }}

      .topbar {{
        display: grid;
        gap: 12px;
        padding: 16px 20px;
        border-radius: 18px;
        background: linear-gradient(145deg, #0f1c35, #111827);
        border: 1px solid var(--border);
        box-shadow: 0 24px 36px rgba(15, 23, 42, 0.45);
      }}

      .overview-strip {{
        display: grid;
        gap: 14px;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin-top: 16px;
      }}

      .hero-kpi {{
        padding: 16px 18px;
        border-radius: 18px;
        border: 1px solid var(--border);
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.92));
        box-shadow: 0 18px 28px rgba(2, 6, 23, 0.28);
      }}

      .hero-kpi .label {{
        color: var(--muted);
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
      }}

      .hero-kpi .value {{
        margin-top: 8px;
        font-size: 1.45rem;
        font-weight: 700;
        line-height: 1.2;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      .hero-kpi .value.positive,
      .kpi .value.positive {{
        color: var(--buy);
      }}

      .hero-kpi .value.negative,
      .kpi .value.negative {{
        color: var(--sell);
      }}

      .hero-kpi .sub {{
        margin-top: 6px;
        color: var(--muted);
        font-size: 0.8rem;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      .topbar-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }}

      .brand {{
        font-size: 1.1rem;
        letter-spacing: 0.25em;
        text-transform: uppercase;
        font-weight: 700;
      }}

      .controls {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }}

      .controls-meta {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }}

      button {{
        border: none;
        border-radius: 999px;
        padding: 10px 16px;
        font-size: 0.9rem;
        font-weight: 700;
        cursor: pointer;
        background: var(--panel-2);
        color: var(--ink);
        border: 1px solid var(--border);
        transition: transform 120ms ease, box-shadow 120ms ease;
      }}

      button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 0 18px rgba(56, 189, 248, 0.3);
      }}

      button.primary {{
        background: linear-gradient(135deg, #0ea5e9, #38bdf8);
        color: #0b1324;
      }}

      button.secondary {{
        background: linear-gradient(135deg, #22c55e, #4ade80);
        color: #0b1324;
      }}

      button.ghost {{
        background: rgba(15, 23, 42, 0.45);
        color: var(--muted);
      }}

      .status-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
      }}

      .chip {{
        padding: 6px 12px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: var(--panel-2);
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }}

      .chip.active {{
        color: var(--ink);
        border-color: var(--accent);
        box-shadow: 0 0 14px rgba(56, 189, 248, 0.25);
      }}

      .chip.error {{
        color: #fecaca;
        border-color: rgba(239, 68, 68, 0.4);
        background: rgba(127, 29, 29, 0.45);
      }}

      .status-banner {{
        margin-top: 12px;
        padding: 10px 12px;
        border-radius: 14px;
        border: 1px solid var(--border);
        color: var(--ink);
        display: none;
      }}

      .status-banner.show {{
        display: block;
      }}

      .status-banner.info {{
        background: rgba(14, 165, 233, 0.12);
        border-color: rgba(56, 189, 248, 0.28);
      }}

      .status-banner.success {{
        background: rgba(34, 197, 94, 0.12);
        border-color: rgba(34, 197, 94, 0.32);
      }}

      .status-banner.error {{
        background: rgba(239, 68, 68, 0.12);
        border-color: rgba(239, 68, 68, 0.32);
      }}

      .signal-ticker {{
        display: flex;
        gap: 10px;
        overflow: auto;
        padding-bottom: 4px;
      }}

      .signal-ticker::-webkit-scrollbar {{
        height: 6px;
      }}

      .signal-ticker::-webkit-scrollbar-thumb {{
        background: rgba(148, 163, 184, 0.22);
        border-radius: 999px;
      }}

      .sync-meta {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        color: var(--muted);
        font-size: 0.84rem;
      }}

      .sync-dot {{
        width: 9px;
        height: 9px;
        border-radius: 999px;
        display: inline-block;
        background: rgba(148, 163, 184, 0.45);
      }}

      .sync-dot.active {{
        background: var(--accent);
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.5);
      }}

      .ticker-item {{
        min-width: max-content;
        padding: 8px 12px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: rgba(15, 23, 42, 0.55);
        color: var(--muted);
        font-size: 0.78rem;
        white-space: nowrap;
      }}

      .grid-main {{
        display: grid;
        gap: 16px;
        margin-top: 18px;
        grid-template-columns: minmax(200px, 0.95fr) minmax(500px, 2.5fr) minmax(240px, 1.05fr);
      }}

      .panel {{
        background: var(--panel);
        border-radius: 18px;
        border: 1px solid var(--border);
        padding: 16px;
        box-shadow: 0 18px 30px rgba(15, 23, 42, 0.35);
      }}

      .panel.soft {{
        background: linear-gradient(180deg, rgba(18, 28, 47, 0.95), rgba(11, 19, 36, 0.96));
      }}

      .panel h2 {{
        margin: 0 0 12px;
        font-size: 0.95rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }}

      .list {{
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        gap: 10px;
      }}

      .scroller {{
        max-height: 420px;
        overflow-y: auto;
        overflow-x: hidden;
        padding-right: 4px;
      }}

      .scroller::-webkit-scrollbar {{
        width: 8px;
      }}

      .scroller::-webkit-scrollbar-thumb {{
        background: rgba(148, 163, 184, 0.22);
        border-radius: 999px;
      }}

      .item {{
        padding: 12px 14px;
        border-radius: 14px;
        border: 1px solid var(--border);
        background: var(--panel-2);
        display: grid;
        gap: 6px;
        min-width: 0;
        overflow: hidden;
      }}

      .item-header {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 10px;
        min-width: 0;
      }}

      .item-title {{
        font-weight: 700;
        min-width: 0;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      .signal-meta {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
        align-items: flex-start;
        min-width: 0;
      }}

      .item-header > *,
      .signal-meta > * {{
        min-width: 0;
      }}

      .item.selectable {{
        cursor: pointer;
        transition: border 120ms ease, transform 120ms ease;
      }}

      .item.selectable:hover {{
        border-color: var(--accent);
        transform: translateY(-1px);
      }}

      .item.active {{
        border-color: var(--accent);
        box-shadow: 0 0 16px rgba(56, 189, 248, 0.2);
      }}

      .signal-buy {{
        color: var(--buy);
        font-weight: 700;
      }}

      .signal-sell {{
        color: var(--sell);
        font-weight: 700;
      }}

      .signal-hold {{
        color: var(--hold);
        font-weight: 700;
      }}

      .badge {{
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        border: 1px solid transparent;
        max-width: 100%;
      }}

      .badge.trending {{
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
        border-color: rgba(34, 197, 94, 0.35);
      }}

      .badge.sideways {{
        background: rgba(251, 191, 36, 0.12);
        color: #facc15;
        border-color: rgba(251, 191, 36, 0.3);
      }}

      .badge.high_vol {{
        background: rgba(248, 113, 113, 0.12);
        color: #f87171;
        border-color: rgba(248, 113, 113, 0.3);
      }}

      .badge.low_vol {{
        background: rgba(59, 130, 246, 0.12);
        color: #60a5fa;
        border-color: rgba(59, 130, 246, 0.3);
      }}

      .chart-toolbar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
        color: var(--muted);
        font-size: 0.85rem;
      }}

      .toolbar-group {{
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
      }}

      .chart-toolbar select {{
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: var(--panel-2);
        color: var(--ink);
      }}

      .chart-legend {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin: 12px 0 10px;
        color: var(--muted);
        font-size: 0.78rem;
      }}

      .legend-item {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid var(--border);
      }}

      .legend-swatch {{
        width: 10px;
        height: 10px;
        border-radius: 999px;
        display: inline-block;
      }}

      .legend-line {{
        width: 14px;
        height: 0;
        border-top: 2px solid currentColor;
        display: inline-block;
      }}

      .chart-snapshot {{
        display: grid;
        gap: 10px;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin: 0 0 14px;
      }}

      .snapshot-card {{
        padding: 12px 14px;
        border-radius: 14px;
        border: 1px solid var(--border);
        background: rgba(15, 23, 42, 0.48);
      }}

      .snapshot-card .label {{
        color: var(--muted);
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
      }}

      .snapshot-card .value {{
        margin-top: 6px;
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.25;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      .snapshot-card .sub {{
        margin-top: 4px;
        color: var(--muted);
        font-size: 0.78rem;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      .scanner-summary {{
        display: grid;
        gap: 10px;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 12px 0 14px;
      }}

      .scanner-stat {{
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: rgba(15, 23, 42, 0.45);
      }}

      .scanner-stat .label {{
        color: var(--muted);
        font-size: 0.68rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}

      .scanner-stat .value {{
        margin-top: 6px;
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.2;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      .chart-frame {{
        width: 100%;
        min-height: 520px;
        height: 640px;
      }}

      .chart-frame.small {{
        min-height: 300px;
        height: 340px;
      }}

      canvas {{
        width: 100%;
        height: 100%;
        display: block;
        border-radius: 16px;
        background: var(--panel-3);
        border: 1px solid var(--border);
      }}

      .grid-bottom {{
        display: grid;
        gap: 16px;
        margin-top: 16px;
        grid-template-columns: repeat(3, minmax(220px, 1fr));
      }}

      .panel-note {{
        margin-top: 10px;
        padding: 10px 12px;
        border-radius: 12px;
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid var(--border);
        color: var(--muted);
        font-size: 0.82rem;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      .timeline-meta {{
        margin-bottom: 12px;
      }}

      .timeline-chip {{
        display: inline-flex;
        align-items: center;
        padding: 4px 9px;
        border-radius: 999px;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border: 1px solid transparent;
      }}

      .timeline-chip.buy {{
        color: var(--buy);
        background: rgba(34, 197, 94, 0.14);
        border-color: rgba(34, 197, 94, 0.35);
      }}

      .timeline-chip.sell {{
        color: var(--sell);
        background: rgba(239, 68, 68, 0.14);
        border-color: rgba(239, 68, 68, 0.35);
      }}

      .timeline-chip.hold {{
        color: var(--hold);
        background: rgba(250, 204, 21, 0.12);
        border-color: rgba(250, 204, 21, 0.28);
      }}

      .kpi-grid {{
        display: grid;
        gap: 10px;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      }}

      .kpi {{
        padding: 12px;
        border-radius: 14px;
        border: 1px solid var(--border);
        background: var(--panel-2);
      }}

      .kpi .label {{
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
      }}

      .kpi .value {{
        margin-top: 6px;
        font-size: 1.1rem;
        font-weight: 700;
        line-height: 1.2;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      .muted {{
        color: var(--muted);
        font-size: 0.85rem;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      .empty-state {{
        padding: 16px;
        border-radius: 14px;
        border: 1px dashed var(--border);
        background: rgba(15, 23, 42, 0.4);
        color: var(--muted);
      }}

      .scanner-card .item-header {{
        flex-direction: column;
        gap: 4px;
      }}

      .scanner-card .signal-meta {{
        justify-content: flex-start;
        gap: 6px 12px;
      }}

      .scanner-family {{
        font-size: 0.78rem;
      }}

      @media (max-width: 1100px) {{
        .workstation-shell {{
          grid-template-columns: 1fr;
        }}

        .workspace-nav {{
          position: static;
          display: flex;
          overflow-x: auto;
          gap: 4px;
          padding: 8px;
        }}

        .workspace-nav .nav-title {{
          display: none;
        }}

        .workspace-nav button {{
          width: max-content;
          flex: 0 0 auto;
          white-space: nowrap;
        }}

        .runtime-board {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}

        .overview-strip {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}

        .grid-main {{
          grid-template-columns: 1fr;
        }}

        .grid-bottom {{
          grid-template-columns: 1fr;
        }}

        .chart-frame {{
          height: 520px;
        }}

        .chart-snapshot {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
      }}

      @media (max-width: 720px) {{
        .runtime-board {{
          grid-template-columns: 1fr;
        }}
        .overview-strip {{
          grid-template-columns: 1fr;
        }}

        .chart-snapshot,
        .scanner-summary {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="terminal">
      <div class="workstation-shell">
        <aside class="workspace-nav" aria-label="Terminal navigation">
          <div class="nav-title">Project Invest</div>
          <button class="active" data-jump="overview">Overview <span>01</span></button>
          <button data-jump="portfolio">Portfolio <span>02</span></button>
          <button data-jump="positions">Positions <span>03</span></button>
          <button data-jump="orders">Orders <span>04</span></button>
          <button data-jump="opportunities">Opportunities <span>05</span></button>
          <button data-jump="strategy-lab-panel">Strategy Lab <span>06</span></button>
          <button data-jump="learning-panel">Experiments <span>07</span></button>
          <button data-jump="risk-panel">Risk <span>08</span></button>
          <button data-jump="compute-panel">Compute <span>09</span></button>
          <button data-jump="data-quality-panel">Data Quality <span>10</span></button>
          <button data-jump="system-health">System Health <span>11</span></button>
          <button data-jump="settings-panel">Settings <span>12</span></button>
        </aside>

        <div class="workspace-content">
      <header class="topbar" id="overview">
        <div class="topbar-header">
          <div class="brand">{safe_app_name} Terminal</div>
          <div class="controls">
            {auth_control}
            <button class="primary" id="run-cycle">Run Research Cycle</button>
            <button class="secondary" id="run-trade">Run Trading Cycle</button>
            <button id="refresh">Refresh</button>
          </div>
        </div>
        <div class="status-row" id="status-row"></div>
        <div class="controls-meta">
          <div class="sync-meta" id="refresh-meta"><span class="sync-dot"></span> Waiting for first sync.</div>
          <button class="ghost" id="auto-refresh">Auto Refresh: On</button>
        </div>
        <div class="status-banner" id="status-banner"></div>
        <div class="signal-ticker" id="signal-ticker"></div>
      </header>

      <section class="runtime-board" id="system-health">
        <article class="runtime-card"><h2>Runtime</h2><div class="runtime-value" id="runtime-health-value">Waiting for health...</div><div class="runtime-detail" id="runtime-health-detail">The API reports only verified local process state.</div></article>
        <article class="runtime-card" id="compute-panel"><h2>Compute</h2><div class="runtime-value" id="compute-value">Waiting for compute status...</div><div class="runtime-detail" id="compute-detail">No remote capacity is assumed.</div></article>
        <article class="runtime-card" id="data-quality-panel"><h2>Data Quality</h2><div class="runtime-value" id="quality-value">Waiting for stored-data audit...</div><div class="runtime-detail" id="quality-detail">Reads do not trigger provider ingestion.</div></article>
        <article class="runtime-card" id="settings-panel"><h2>Settings</h2><div class="runtime-value" id="settings-value">Waiting for configuration...</div><div class="runtime-detail" id="settings-detail">Configuration is display-only here; secrets are never returned.</div></article>
      </section>

      <section class="overview-strip" id="portfolio"></section>

      <section class="grid-main" id="opportunities">
        <aside class="panel soft">
          <h2>Market Scanner</h2>
          <div class="muted" id="scanner-meta">Loading scan...</div>
          <div class="scanner-summary" id="scanner-summary"></div>
          <ul class="list scroller" id="scanner"></ul>
        </aside>

        <section class="panel soft">
          <h2>Chart</h2>
          <div class="chart-toolbar">
            <div class="toolbar-group">
              <label>Symbol <select id="chart-symbol"></select></label>
              <label>Interval <select id="chart-interval"></select></label>
            </div>
            <div class="toolbar-group">
              <div id="chart-meta">Loading market data...</div>
            </div>
          </div>
          <div class="chart-legend">
            <span class="legend-item"><span class="legend-swatch" style="background:#22c55e;"></span> Buy marker</span>
            <span class="legend-item"><span class="legend-swatch" style="background:#ef4444;"></span> Sell marker</span>
            <span class="legend-item" style="color:#38bdf8;"><span class="legend-line"></span> SMA 20</span>
            <span class="legend-item" style="color:#fbbf24;"><span class="legend-line"></span> EMA 12</span>
          </div>
          <div class="chart-snapshot" id="chart-snapshot"></div>
          <div class="chart-frame">
            <canvas id="chart"></canvas>
          </div>
        </section>

        <aside class="panel soft">
          <h2>Strategy Brain</h2>
          <ul class="list" id="brain"></ul>
          <div class="panel-note" id="brain-note">Waiting for strategy context.</div>
        </aside>
      </section>

      <section class="panel soft" id="orders" style="margin-top: 16px;">
        <h2>Trade Timeline</h2>
        <div class="muted timeline-meta" id="timeline-meta">Recent decisions and execution notes.</div>
        <ul class="list scroller" id="timeline"></ul>
      </section>

      <section class="grid-bottom">
        <article class="panel soft" id="strategy-lab-panel">
          <h2>Strategy Lab</h2>
          <ul class="list scroller" id="strategy-lab"></ul>
        </article>
        <article class="panel soft" id="risk-panel">
          <h2>Portfolio Risk</h2>
          <div class="kpi-grid" id="risk-kpis"></div>
        </article>
        <article class="panel soft" id="learning-panel">
          <h2>Learning Engine</h2>
          <div class="kpi-grid" id="learning-kpis"></div>
          <div class="panel-note" id="learning-note">Trade memory is warming up.</div>
          <ul class="list scroller" id="learning"></ul>
        </article>
      </section>

      <section class="panel soft" id="positions" style="margin-top: 16px;">
        <h2>Open Positions</h2>
        <div class="muted" id="positions-meta">Waiting for the paper portfolio summary.</div>
        <div class="table-wrap" id="positions-table"></div>
      </section>

      <section class="panel soft" style="margin-top: 16px;">
        <h2>Trade Replay</h2>
        <div class="chart-toolbar">
          <label>Trade <select id="replay-trade"></select></label>
          <div id="replay-meta">Select a trade to replay.</div>
        </div>
        <div class="chart-frame small">
          <canvas id="replay-chart"></canvas>
        </div>
        <div class="muted" id="replay-details">Trade details will appear here.</div>
      </section>
        </div>
      </div>
    </main>

    <script>
      const statusRow = document.getElementById("status-row");
      const statusBannerNode = document.getElementById("status-banner");
      const signalTickerNode = document.getElementById("signal-ticker");
      const overviewKpisNode = document.getElementById("overview-kpis");
      const scannerNode = document.getElementById("scanner");
      const scannerMetaNode = document.getElementById("scanner-meta");
      const scannerSummaryNode = document.getElementById("scanner-summary");
      const chartSymbolNode = document.getElementById("chart-symbol");
      const chartIntervalNode = document.getElementById("chart-interval");
      const chartMetaNode = document.getElementById("chart-meta");
      const chartSnapshotNode = document.getElementById("chart-snapshot");
      const chartCanvas = document.getElementById("chart");
      const brainNode = document.getElementById("brain");
      const brainNoteNode = document.getElementById("brain-note");
      const timelineNode = document.getElementById("timeline");
      const timelineMetaNode = document.getElementById("timeline-meta");
      const strategyLabNode = document.getElementById("strategy-lab");
      const riskKpisNode = document.getElementById("risk-kpis");
      const learningKpisNode = document.getElementById("learning-kpis");
      const learningNoteNode = document.getElementById("learning-note");
      const learningNode = document.getElementById("learning");
      const replayTradeNode = document.getElementById("replay-trade");
      const replayMetaNode = document.getElementById("replay-meta");
      const replayDetailsNode = document.getElementById("replay-details");
      const replayCanvas = document.getElementById("replay-chart");
      const refreshMetaNode = document.getElementById("refresh-meta");
      const autoRefreshNode = document.getElementById("auto-refresh");
      const runtimeHealthValueNode = document.getElementById("runtime-health-value");
      const runtimeHealthDetailNode = document.getElementById("runtime-health-detail");
      const computeValueNode = document.getElementById("compute-value");
      const computeDetailNode = document.getElementById("compute-detail");
      const qualityValueNode = document.getElementById("quality-value");
      const qualityDetailNode = document.getElementById("quality-detail");
      const settingsValueNode = document.getElementById("settings-value");
      const settingsDetailNode = document.getElementById("settings-detail");
      const positionsMetaNode = document.getElementById("positions-meta");
      const positionsTableNode = document.getElementById("positions-table");

      let activeSymbol = null;
      let activeReplayTrade = null;
      let activeMarketFilter = "ALL";
      let activeInterval = null;
      let availableIntervals = [];
      let executionMarkets = [];
      let symbolMarketMap = {{}};
      let latestPortfolio = {{ positions: {{}} }};
      let latestActiveReport = null;
      let dashboardLoading = false;
      let autoRefreshEnabled = true;
      let autoRefreshTimer = null;
      let lastDashboardRefreshAt = null;

      const currency = new Intl.NumberFormat("en-IN", {{
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2
      }});

      function formatNumber(value, decimals = 2) {{
        if (value == null || Number.isNaN(value)) {{
          return "n/a";
        }}
        return Number(value).toFixed(decimals);
      }}

      function formatPercent(value, decimals = 1) {{
        if (value == null || Number.isNaN(value)) {{
          return "n/a";
        }}
        return `${{Number(value).toFixed(decimals)}}%`;
      }}

      function toneClass(value) {{
        if (value == null || Number.isNaN(value) || Number(value) === 0) {{
          return "";
        }}
        return Number(value) > 0 ? "positive" : "negative";
      }}

      function formatPrice(value, symbol = "") {{
        if (value == null || Number.isNaN(value)) {{
          return "n/a";
        }}
        if ((symbol || "").endsWith(".NS")) {{
          return currency.format(value);
        }}
        return `${{Number(value).toFixed(2)}}`;
      }}

      function formatSignal(action) {{
        if (action === "BUY") return `<span class="signal-buy">BUY</span>`;
        if (action === "SELL") return `<span class="signal-sell">SELL</span>`;
        return `<span class="signal-hold">HOLD</span>`;
      }}

      function renderChip(label, value, className = "") {{
        return `<span class="chip ${{className}}">${{label}}: ${{value}}</span>`;
      }}

      function renderMarketChip(market, isActive) {{
        return `<span class="chip ${{isActive ? "active" : ""}}" data-market="${{market}}">${{market}}</span>`;
      }}

      function escapeHtml(value) {{
        return String(value ?? "").replace(/[&<>'"]/g, (character) => ({{
          "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
        }}[character]));
      }}

      function drawCanvasPlaceholder(canvas, message) {{
        const container = canvas.parentElement || canvas;
        const width = container.clientWidth || 960;
        const height = Math.max(320, container.clientHeight || 520);
        const ratio = window.devicePixelRatio || 1;
        canvas.width = width * ratio;
        canvas.height = height * ratio;
        const ctx = canvas.getContext("2d");
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = "rgba(15, 23, 42, 0.96)";
        ctx.fillRect(0, 0, width, height);
        ctx.strokeStyle = "rgba(148, 163, 184, 0.18)";
        ctx.strokeRect(1, 1, width - 2, height - 2);
        ctx.fillStyle = "rgba(148, 163, 184, 0.92)";
        ctx.font = '16px Consolas, "SFMono-Regular", "Segoe UI", sans-serif';
        ctx.textAlign = "center";
        ctx.fillText(message, width / 2, height / 2);
      }}

      function renderRefreshMeta() {{
        if (!refreshMetaNode || !autoRefreshNode) {{
          return;
        }}
        const syncText = lastDashboardRefreshAt
          ? `Last sync ${{lastDashboardRefreshAt.toLocaleTimeString()}}`
          : "Waiting for first sync";
        const autoText = autoRefreshEnabled ? "Auto 30s" : "Auto off";
        const intervalText = activeInterval ? `View ${{activeInterval}}` : "View n/a";
        refreshMetaNode.innerHTML =
          `<span class="sync-dot ${{autoRefreshEnabled ? "active" : ""}}"></span> ${{syncText}} | ${{autoText}} | ${{intervalText}}`;
        autoRefreshNode.textContent = `Auto Refresh: ${{autoRefreshEnabled ? "On" : "Off"}}`;
      }}

      function scheduleAutoRefresh() {{
        if (autoRefreshTimer) {{
          clearTimeout(autoRefreshTimer);
        }}
        if (!autoRefreshEnabled) {{
          return;
        }}
        autoRefreshTimer = setTimeout(() => {{
          loadDashboard();
        }}, 30000);
      }}

      function buildIntervalOptions(health, activeReport) {{
        return [...new Set([
          activeReport && activeReport.interval,
          health.trading_interval,
          health.interval,
          ...(health.confirmation_intervals || [])
        ].filter(Boolean))];
      }}

      function renderTicker(events) {{
        if (!events || !events.length) {{
          signalTickerNode.innerHTML = `<div class="ticker-item">Waiting for live events...</div>`;
          return;
        }}
        const recent = [...events].slice(-12).reverse();
        signalTickerNode.innerHTML = recent
          .map((event) => {{
            const action = event.order_action || event.signal_action || "HOLD";
            const market = getMarketForSymbol(event.symbol);
            const note = event.order_note || event.signal_reason || event.meta_reason || "No note";
            return `<div class="ticker-item">${{new Date(event.timestamp).toLocaleTimeString()}} | ${{event.symbol}} | ${{market}} | ${{action}} | ${{note}}</div>`;
          }})
          .join("");
      }}

      function renderOverview(portfolio, analytics, health) {{
        const lastRun = analytics.last_run ? new Date(analytics.last_run).toLocaleTimeString() : "n/a";
        const ready = portfolio.state === "ready";
        const openPositions = ready ? portfolio.open_positions : "n/a";
        const engineState = health.runtime && health.runtime.trading_worker
          ? health.runtime.trading_worker.state
          : "not reported";
        overviewKpisNode.innerHTML = [
          `<article class="hero-kpi"><div class="label">Portfolio Equity</div><div class="value">${{ready ? currency.format(portfolio.equity) : "n/a"}}</div><div class="sub">${{ready ? `Cash ${{currency.format(portfolio.cash)}}` : escapeHtml(portfolio.message || "No paper portfolio yet.")}}</div></article>`,
          `<article class="hero-kpi"><div class="label">Total PnL</div><div class="value ${{toneClass(portfolio.total_pnl)}}">${{ready ? currency.format(portfolio.total_pnl) : "n/a"}}</div><div class="sub">Realized ${{ready ? currency.format(portfolio.realized_pnl) : "n/a"}}</div></article>`,
          `<article class="hero-kpi"><div class="label">Open Positions</div><div class="value">${{openPositions}}</div><div class="sub">Exposure ${{ready ? currency.format(portfolio.gross_exposure) : "n/a"}}</div></article>`,
          `<article class="hero-kpi"><div class="label">Engine State</div><div class="value">${{engineState}}</div><div class="sub">Last cycle ${{lastRun}}</div></article>`
        ].join("");
      }}

      function renderRuntimeBoard(health, dataQuality, compute, config) {{
        const runtime = health.runtime || {{}};
        const research = runtime.research_worker || {{ state: "not reported" }};
        const trading = runtime.trading_worker || {{ state: "not reported" }};
        const workerDetail = (label, worker) => {{
          const heartbeat = worker.heartbeat_at ? new Date(worker.heartbeat_at).toLocaleTimeString() : "none";
          const success = worker.last_success_at ? new Date(worker.last_success_at).toLocaleTimeString() : "none";
          const error = worker.last_error ? ` | error: ${{worker.last_error}}` : "";
          return `${{label}} ${{worker.state || "unknown"}} | heartbeat ${{heartbeat}} | last success ${{success}}${{error}}`;
        }};
        runtimeHealthValueNode.textContent = `API ${{health.status || "unknown"}} · storage ${{runtime.storage?.state || "unknown"}}`;
        runtimeHealthDetailNode.textContent = `${{workerDetail("Research", research)}}\n${{workerDetail("Trading", trading)}}`;
        computeValueNode.textContent = compute.local_backend?.status === "available" ? "Local backend available" : "Compute unavailable";
        computeDetailNode.textContent = compute.remote_backend?.status === "not_configured"
          ? "Remote compute is not configured; no remote job data is invented."
          : (compute.note || "No compute detail reported.");
        const availableRecords = (dataQuality.records || []).filter((record) => record.status === "available").length;
        qualityValueNode.textContent = `${{dataQuality.status || "unknown"}} · ${{availableRecords}}/${{(dataQuality.records || []).length}} symbols`;
        qualityDetailNode.textContent = dataQuality.note || "No stored-data quality report is available.";
        settingsValueNode.textContent = `${{config.execution_mode || "unknown"}} · ${{config.storage_backend || "unknown"}} storage`;
        settingsDetailNode.textContent = `Data: ${{config.market_data_provider || "unknown"}} | loops: research=${{config.research_loop_enabled ? "on" : "off"}}, trading=${{config.trading_loop_enabled ? "on" : "off"}} | no secrets displayed`;
      }}

      function renderPositions(portfolio) {{
        const positions = portfolio.positions || [];
        if (portfolio.state !== "ready") {{
          positionsMetaNode.textContent = portfolio.message || "No paper portfolio has been created yet.";
          positionsTableNode.innerHTML = `<div class="empty-state">Run a paper trading cycle after configuration to populate positions.</div>`;
          return;
        }}
        positionsMetaNode.textContent = `${{positions.length}} open positions | as of ${{portfolio.as_of ? new Date(portfolio.as_of).toLocaleString() : "n/a"}} | reconciliation delta ${{currency.format(portfolio.pnl_reconciliation_delta)}}`;
        if (!positions.length) {{
          positionsTableNode.innerHTML = `<div class="empty-state">No open positions. This is a flat paper portfolio, not a zero-filled placeholder.</div>`;
          return;
        }}
        positionsTableNode.innerHTML = `<table class="data-table"><thead><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>Last</th><th>Market Value</th><th>Unrealized</th><th>Return</th><th>Weight</th></tr></thead><tbody>${{positions.map((position) => `<tr><td>${{escapeHtml(position.symbol)}}</td><td>${{position.quantity}}</td><td>${{formatPrice(position.average_entry_price, position.symbol)}}</td><td>${{formatPrice(position.last_price, position.symbol)}}</td><td>${{currency.format(position.market_value)}}</td><td class="${{toneClass(position.unrealized_pnl)}}">${{currency.format(position.unrealized_pnl)}}</td><td class="${{toneClass(position.return_pct)}}">${{formatPercent(position.return_pct, 2)}}</td><td>${{formatPercent(position.weight_pct, 2)}}</td></tr>`).join("")}}</tbody></table>`;
      }}

      function ensureSymbols(symbols) {{
        if (!chartSymbolNode) {{
          return;
        }}
        if (!symbols || !symbols.length) {{
          return;
        }}
        chartSymbolNode.innerHTML = symbols
          .map((symbol) => `<option value="${{symbol}}">${{symbol}}</option>`)
          .join("");
        if (!activeSymbol || !symbols.includes(activeSymbol)) {{
          activeSymbol = symbols[0];
        }}
        chartSymbolNode.value = activeSymbol;
      }}

      function ensureIntervals(intervals) {{
        if (!chartIntervalNode) {{
          return;
        }}
        availableIntervals = intervals && intervals.length ? intervals : ["15m"];
        if (!activeInterval || !availableIntervals.includes(activeInterval)) {{
          activeInterval = availableIntervals[0];
        }}
        chartIntervalNode.innerHTML = availableIntervals
          .map((interval) => `<option value="${{interval}}">${{interval}}</option>`)
          .join("");
        chartIntervalNode.value = activeInterval;
        renderRefreshMeta();
      }}

      function getMarketForSymbol(symbol) {{
        if (symbolMarketMap[symbol]) return symbolMarketMap[symbol];
        if (symbol.endsWith(".NS")) return "NSE";
        if (symbol.endsWith("-USD")) return "CRYPTO";
        if (symbol.endsWith("=X")) return "FOREX";
        return "US";
      }}

      function isExecutionEligible(market) {{
        if (!executionMarkets.length) {{
          return true;
        }}
        if (executionMarkets.includes(market)) {{
          return true;
        }}
        if ((market === "NASDAQ" || market === "NYSE") && executionMarkets.includes("US")) {{
          return true;
        }}
        if (market === "US" && (executionMarkets.includes("NASDAQ") || executionMarkets.includes("NYSE"))) {{
          return true;
        }}
        return false;
      }}

      function setBanner(message, tone = "info") {{
        if (!message) {{
          statusBannerNode.className = "status-banner";
          statusBannerNode.textContent = "";
          return;
        }}
        statusBannerNode.className = `status-banner show ${{tone}}`;
        statusBannerNode.textContent = message;
      }}

      async function fetchWithTimeout(url, options = {{}}, timeoutMs = 12000) {{
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), timeoutMs);
        try {{
          return await fetch(url, {{ ...options, signal: controller.signal }});
        }} catch (error) {{
          if (controller.signal.aborted) {{
            throw new Error(`${{url}} timed out after ${{Math.round(timeoutMs / 1000)}} seconds`);
          }}
          throw error;
        }} finally {{
          window.clearTimeout(timer);
        }}
      }}

      async function postJson(url, body = {{}}) {{
        const tokenInput = document.getElementById("operational-token");
        const token = tokenInput ? tokenInput.value.trim() : "";
        const headers = {{ "Content-Type": "application/json" }};
        if (token) {{
          headers.Authorization = `Bearer ${{token}}`;
        }}
        const response = await fetchWithTimeout(url, {{
          method: "POST",
          headers,
          body: JSON.stringify(body)
        }}, 90000);
        const text = await response.text();
        let payload = null;
        if (text) {{
          try {{
            payload = JSON.parse(text);
          }} catch (error) {{
            payload = null;
          }}
        }}
        if (!response.ok) {{
          const detail =
            payload && typeof payload === "object"
              ? (payload.detail || payload.message || null)
              : null;
          throw new Error(detail || text || `Request failed (${{response.status}})`);
        }}
        return payload || {{}};
      }}

      async function fetchJsonSafe(url, fallback = null, required = false) {{
        let response;
        try {{
          response = await fetchWithTimeout(url);
        }} catch (error) {{
          if (!required) {{
            return fallback;
          }}
          throw error;
        }}
        const text = await response.text();
        if (!response.ok) {{
          if (!required) {{
            return fallback;
          }}
          throw new Error(`${{url}} -> ${{text || `HTTP ${{response.status}}`}}`);
        }}
        if (!text) {{
          return fallback;
        }}
        try {{
          return JSON.parse(text);
        }} catch (error) {{
          if (!required) {{
            return fallback;
          }}
          throw new Error(`${{url}} returned invalid JSON`);
        }}
      }}

      function buildMarketFilters(symbols) {{
        const used = new Set(["ALL"]);
        (symbols || []).forEach((symbol) => used.add(getMarketForSymbol(symbol)));
        return Array.from(used);
      }}

      async function loadDashboard() {{
        if (dashboardLoading) {{
          return;
        }}
        dashboardLoading = true;
        try {{
          const [health, analytics, learning, tradeMemory, portfolio, portfolioSummary, dataQuality, compute, config, researchReport, tradingReport, events, universe] = await Promise.all([
            fetchJsonSafe("/health", null, true),
            fetchJsonSafe("/api/analytics/summary", {{
              status: "no-data",
              top_strategies: [],
              recent_orders: [],
              allocation_plan: {{}},
            }}),
            fetchJsonSafe("/api/analytics/learning", {{
              symbols_tracked: 0,
              scoreboard: [],
            }}),
            fetchJsonSafe("/api/analytics/trade-memory", {{
              records: 0,
              open_records: 0,
              closed_records: 0,
              win_rate: null,
              avg_pnl: 0,
              avg_return_pct: 0,
              best_pattern: null,
              worst_pattern: null,
              best_sentiment_pattern: null,
              worst_sentiment_pattern: null,
            }}),
            fetchJsonSafe("/api/portfolio", {{
              starting_capital: 0,
              total_equity: 0,
              open_exposure: 0,
              daily_pnl: 0,
              realized_pnl: 0,
              positions: {{}},
            }}),
            fetchJsonSafe("/api/portfolio/summary", {{
              state: "unavailable",
              message: "Portfolio summary is unavailable.",
              positions: [],
            }}),
            fetchJsonSafe("/api/data-quality", {{ status: "unavailable", records: [] }}),
            fetchJsonSafe("/api/research/compute-status", {{}}),
            fetchJsonSafe("/api/config", {{}}),
            fetchJsonSafe("/api/research/latest", null),
            fetchJsonSafe("/api/trading/latest", null),
            fetchJsonSafe("/api/events?limit=30", []),
            fetchJsonSafe("/api/universe", {{ resolved: [], symbol_markets: {{}} }}),
          ]); 
          const activeReport = tradingReport || researchReport;
          latestActiveReport = activeReport;
          latestPortfolio = portfolio;
          symbolMarketMap = universe.symbol_markets || {{}};
          executionMarkets = health.execution_markets || [];
          ensureIntervals(buildIntervalOptions(health, activeReport));

          const markets = buildMarketFilters(universe.resolved || health.research_symbols || []);
          if (!markets.includes(activeMarketFilter)) {{
            activeMarketFilter = "ALL";
          }}
          statusRow.innerHTML = [
            ...markets.map((market) => renderMarketChip(market, market === activeMarketFilter)),
            renderChip("API", health.status || "unknown", health.status === "ok" ? "active" : "error"),
            renderChip("Storage", health.runtime?.storage?.state || "unknown", health.runtime?.storage?.state === "connected" ? "active" : "error"),
            renderChip("Data", health.runtime?.market_data?.state || "unknown", health.runtime?.market_data?.state === "fresh" ? "active" : ""),
            renderChip("Research", health.runtime?.research_worker?.state || "not reported", health.runtime?.research_worker?.state === "running" ? "active" : ""),
            renderChip("Trading", health.runtime?.trading_worker?.state || "not reported", health.runtime?.trading_worker?.state === "running" ? "active" : ""),
            renderChip("Legacy", health.legacy_worker_running ? "running" : "stopped", health.legacy_worker_running ? "active" : ""),
            renderChip("Mode", health.execution_mode || "paper"),
            renderChip("Launch", health.worker_launch_mode || "unknown", health.worker_launch_mode === "embedded" ? "active" : ""),
            renderChip("Exec Markets", executionMarkets.join(", ") || "none"),
            renderChip("API", health.status || "unknown"),
            renderChip("Research Int", health.interval || "n/a"),
            renderChip("Trade Int", health.trading_interval || "n/a"),
            ...(health.worker_last_error ? [renderChip("Worker Error", "present", "error")] : []),
            renderChip("Time", new Date().toLocaleTimeString())
          ].join("");

          const workerIssue = health.runtime?.research_worker?.last_error || health.runtime?.trading_worker?.last_error || health.worker_last_error;
          if (workerIssue) {{
            setBanner(`Worker warning: ${{workerIssue}}`, "error");
          }} else if (health.runtime?.research_worker?.state === "stale" || health.runtime?.trading_worker?.state === "stale") {{
            setBanner("A worker heartbeat is stale. No automatic restart or order resubmission was performed.", "error");
          }} else if (health.runtime?.research_worker?.state === "not_reported" && health.runtime?.trading_worker?.state === "not_reported") {{
            setBanner("Workers have not reported a heartbeat yet. The dashboard remains usable; start the local stack to run scheduled cycles.", "info");
          }} else {{
            const launchNote = health.launch_hint ? ` | ${{health.launch_hint}}` : "";
            setBanner(`Dashboard synced | interval ${{activeInterval}} | execution markets: ${{executionMarkets.join(", ") || "none"}}${{launchNote}}`, "info");
          }}

          statusRow.querySelectorAll("[data-market]").forEach((chip) => {{
            chip.addEventListener("click", () => {{
              activeMarketFilter = chip.getAttribute("data-market") || "ALL";
              loadDashboard();
            }});
          }});

          ensureSymbols((activeReport && activeReport.symbols) || health.research_symbols || []);

          renderOverview(portfolioSummary, analytics, health);
          renderRuntimeBoard(health, dataQuality, compute, config);
          renderPositions(portfolioSummary);
          renderTicker(events);
          renderScanner(activeReport);
          renderTimeline(events);
          renderStrategyLab(analytics);
          renderRisk(portfolioSummary);
          renderLearning(learning, tradeMemory);

          if (activeSymbol) {{
            await loadSymbolPanels(activeSymbol);
          }}
          await loadReplayTrades();
          lastDashboardRefreshAt = new Date();
          renderRefreshMeta();
        }} catch (error) {{
          setBanner(`Dashboard load failed: ${{error.message}}`, "error");
          if (scannerMetaNode) {{
            scannerMetaNode.textContent = "Dashboard load failed.";
          }}
          if (scannerNode) {{
            scannerNode.innerHTML = `<li class="empty-state">The dashboard could not load its latest data. Refresh the page after the API is healthy again.</li>`;
          }}
          if (scannerSummaryNode) {{
            scannerSummaryNode.innerHTML = "";
          }}
          if (chartSnapshotNode) {{
            chartSnapshotNode.innerHTML = "";
          }}
          if (timelineMetaNode) {{
            timelineMetaNode.textContent = "Timeline unavailable while the dashboard is recovering.";
          }}
          renderRefreshMeta();
        }} finally {{
          dashboardLoading = false;
          scheduleAutoRefresh();
        }}
      }}

      function renderScanner(report) {{
        if (!scannerNode || !scannerMetaNode) {{
          return;
        }}
        if (!report || !report.results) {{
          scannerMetaNode.textContent = "Run a research or trading cycle to see signals.";
          if (scannerSummaryNode) {{
            scannerSummaryNode.innerHTML = "";
          }}
          scannerNode.innerHTML = `<li class="item">No results yet.</li>`;
          return;
        }}
        const results = report.results
          .map((item) => {{
            const signal = item.evolution.latest_signal;
            const family = (item.evolution.meta_selected || item.evolution.champion).genome.family;
            return {{
              symbol: item.symbol,
              action: signal.action,
              confidence: signal.confidence,
              regime: item.evolution.market_regime || "n/a",
              family: family
            }};
          }})
          .filter((item) => {{
            if (activeMarketFilter === "ALL") return true;
            return getMarketForSymbol(item.symbol) === activeMarketFilter;
          }})
          .sort((left, right) => {{
            const actionWeight = (action) => action === "BUY" ? 2 : (action === "SELL" ? 1 : 0);
            const actionDelta = actionWeight(right.action) - actionWeight(left.action);
            if (actionDelta !== 0) {{
              return actionDelta;
            }}
            return (right.confidence || 0) - (left.confidence || 0);
          }});

        const buyCount = results.filter((item) => item.action === "BUY").length;
        const sellCount = results.filter((item) => item.action === "SELL").length;
        const holdCount = results.filter((item) => item.action === "HOLD").length;
        const tradableCount = results.filter((item) => isExecutionEligible(getMarketForSymbol(item.symbol))).length;
        if (scannerSummaryNode) {{
          scannerSummaryNode.innerHTML = [
            `<div class="scanner-stat"><div class="label">Buy Setups</div><div class="value signal-buy">${{buyCount}}</div></div>`,
            `<div class="scanner-stat"><div class="label">Sell Setups</div><div class="value signal-sell">${{sellCount}}</div></div>`,
            `<div class="scanner-stat"><div class="label">Watching</div><div class="value signal-hold">${{holdCount}}</div></div>`,
            `<div class="scanner-stat"><div class="label">Tradable</div><div class="value">${{tradableCount}}</div></div>`
          ].join("");
        }}
        scannerMetaNode.textContent = `Scanning ${{results.length}} symbols | filter=${{activeMarketFilter}}`;
        if (!results.length) {{
          scannerNode.innerHTML = `<li class="empty-state">No symbols match the current market filter.</li>`;
          return;
        }}
        scannerNode.innerHTML = results
          .map((item) => {{
            const active = item.symbol === activeSymbol ? "active" : "";
            const regimeLabel = item.regime || "n/a";
            const regimeClass = (regimeLabel || "na").replace("/", "_");
            const market = getMarketForSymbol(item.symbol);
            const executable = isExecutionEligible(market);
            return `
              <li class="item selectable scanner-card ${{active}}" data-symbol="${{item.symbol}}">
                <div class="item-header">
                  <span class="item-title">${{item.symbol}}</span>
                  <span class="muted scanner-family">${{item.family}}</span>
                </div>
                <div class="signal-meta">
                  <span>${{formatSignal(item.action)}}</span>
                  <span class="muted">conf=${{formatNumber(item.confidence, 2)}}</span>
                </div>
                <div class="signal-meta">
                  <span class="muted">market=${{market}}</span>
                  <span class="badge ${{regimeClass}}">${{regimeLabel}}</span>
                </div>
                <div class="muted">${{executable ? "paper tradable" : "research only"}}</div>
              </li>
            `;
          }})
          .join("");

        scannerNode.querySelectorAll("[data-symbol]").forEach((item) => {{
          item.addEventListener("click", async () => {{
            activeSymbol = item.getAttribute("data-symbol");
            await loadSymbolPanels(activeSymbol);
            renderScanner(report);
          }});
        }});
      }}

      function renderTimeline(events) {{
        if (!timelineNode || !timelineMetaNode) {{
          return;
        }}
        if (!events || !events.length) {{
          timelineMetaNode.textContent = "No live events yet.";
          timelineNode.innerHTML = `<li class="item">No events yet.</li>`;
          return;
        }}
        const lastEvent = events[events.length - 1];
        timelineMetaNode.textContent = `Showing ${{events.length}} latest events | last update ${{new Date(lastEvent.timestamp).toLocaleTimeString()}}`;
        timelineNode.innerHTML = events.map((event) => {{
          const action = event.order_action || event.signal_action || "HOLD";
          const note = event.order_note || event.signal_reason || event.meta_reason || "";
          const family = event.strategy_family ? ` (${{event.strategy_family}})` : "";
          const actionClass = action === "BUY" ? "buy" : (action === "SELL" ? "sell" : "hold");
          const market = getMarketForSymbol(event.symbol);
          return `
            <li class="item">
              <div class="item-header">
                <div><span class="timeline-chip ${{actionClass}}">${{action}}</span> <strong>${{event.symbol}}</strong><span class="muted">${{family}}</span></div>
                <span class="muted">${{new Date(event.timestamp).toLocaleTimeString()}}</span>
              </div>
              <div class="signal-meta">
                <span class="muted">${{market}}</span>
                <span class="muted">conf=${{formatNumber(event.signal_confidence, 2)}}</span>
              </div>
              <div class="muted">${{note}}</div>
            </li>
          `;
        }}).join("");
      }}

      function renderStrategyLab(analytics) {{
        if (!analytics.top_strategies || analytics.top_strategies.length === 0) {{
          strategyLabNode.innerHTML = `<li class="item">No strategies ranked yet.</li>`;
          return;
        }}
        strategyLabNode.innerHTML = analytics.top_strategies.map((item) => {{
          return `
            <li class="item">
              <div class="item-header">
                <span class="item-title">${{item.symbol}}</span>
                <span class="muted">${{item.family}}</span>
              </div>
              <div class="signal-meta">
                <span class="muted">Sharpe=${{formatNumber(item.sharpe_ratio, 2)}}</span>
                <span class="muted">Val=${{formatNumber(item.validation_sharpe_ratio, 2)}}</span>
                <span class="muted">Trades=${{item.trades}}</span>
              </div>
              <div class="signal-meta">
                <span class="muted">Score=${{formatNumber(item.score, 2)}}</span>
                <span class="muted">PF=${{formatNumber(item.profit_factor, 2)}}</span>
                <span class="muted">Robust=${{formatNumber(item.robustness_score, 2)}}</span>
              </div>
              <div class="muted">Latest signal: ${{item.signal}}</div>
            </li>
          `;
        }}).join("");
      }}

      function renderRisk(portfolio) {{
        if (portfolio.state !== "ready") {{
          riskKpisNode.innerHTML = `<div class="empty-state">${{escapeHtml(portfolio.message || "No paper portfolio metrics are available yet.")}}</div>`;
          return;
        }}
        riskKpisNode.innerHTML = [
          `<div class="kpi"><div class="label">Capital</div><div class="value">${{currency.format(portfolio.starting_capital || 0)}}</div></div>`,
          `<div class="kpi"><div class="label">Equity</div><div class="value">${{currency.format(portfolio.equity)}}</div></div>`,
          `<div class="kpi"><div class="label">Exposure</div><div class="value">${{currency.format(portfolio.gross_exposure)}}</div></div>`,
          `<div class="kpi"><div class="label">Daily PnL</div><div class="value ${{toneClass(portfolio.daily_pnl)}}">${{portfolio.daily_pnl_available ? currency.format(portfolio.daily_pnl) : "n/a"}}</div></div>`,
          `<div class="kpi"><div class="label">Open Positions</div><div class="value">${{portfolio.open_positions}}</div></div>`,
          `<div class="kpi"><div class="label">Realized PnL</div><div class="value ${{toneClass(portfolio.realized_pnl)}}">${{currency.format(portfolio.realized_pnl || 0)}}</div></div>`
        ].join("");
      }}

      function renderLearning(learning, tradeMemory) {{
        const scoreboard = learning.scoreboard || [];
        let tradesLearned = 0;
        const familyScores = {{}};
        scoreboard.forEach((item) => {{
          tradesLearned += (item.paper_entries || 0) + (item.paper_exits || 0);
          if (item.family && item.score != null) {{
            if (!familyScores[item.family]) {{
              familyScores[item.family] = [];
            }}
            familyScores[item.family].push(item.score);
          }}
        }});

        const families = Object.keys(familyScores).map((family) => {{
          const scores = familyScores[family];
          const avg = scores.reduce((acc, value) => acc + value, 0) / scores.length;
          return {{ family, avg }};
        }});

        families.sort((a, b) => b.avg - a.avg);
        const topFamily = families[0];
        const weakFamily = families.length > 1 ? families[families.length - 1] : null;

        learningKpisNode.innerHTML = [
          `<div class="kpi"><div class="label">Symbols</div><div class="value">${{learning.symbols_tracked ?? 0}}</div></div>`,
          `<div class="kpi"><div class="label">Trades Learned</div><div class="value">${{tradesLearned}}</div></div>`,
          `<div class="kpi"><div class="label">Closed Memory</div><div class="value">${{tradeMemory.closed_records ?? 0}}</div></div>`,
          `<div class="kpi"><div class="label">Win Rate</div><div class="value">${{formatPercent((tradeMemory.win_rate ?? 0) * 100, 1)}}</div></div>`,
          `<div class="kpi"><div class="label">Top Family</div><div class="value">${{topFamily ? topFamily.family : "n/a"}}</div></div>`,
          `<div class="kpi"><div class="label">Weak Family</div><div class="value">${{weakFamily ? weakFamily.family : "n/a"}}</div></div>`
        ].join("");

        const bestPattern = tradeMemory.best_pattern;
        const worstPattern = tradeMemory.worst_pattern;
        const bestSentimentPattern = tradeMemory.best_sentiment_pattern;
        const bestText = bestPattern
          ? `${{bestPattern.family}} + ${{bestPattern.regime}} (${{bestPattern.trades}} trades, ${{formatPercent(bestPattern.win_rate * 100, 1)}})`
          : "n/a";
        const worstText = worstPattern
          ? `${{worstPattern.family}} + ${{worstPattern.regime}} (${{worstPattern.trades}} trades, ${{formatPercent(worstPattern.win_rate * 100, 1)}})`
          : "n/a";
        const bestSentimentText = bestSentimentPattern
          ? `${{bestSentimentPattern.family}} + ${{bestSentimentPattern.sentiment_bucket}} sentiment (${{bestSentimentPattern.trades}} trades, ${{formatPercent(bestSentimentPattern.win_rate * 100, 1)}})`
          : "n/a";
        learningNoteNode.textContent =
          `Memory records: ${{tradeMemory.records ?? 0}} | Closed trades: ${{tradeMemory.closed_records ?? 0}} | Avg return: ${{formatPercent(tradeMemory.avg_return_pct, 2)}} | Best pattern: ${{bestText}} | Best sentiment: ${{bestSentimentText}} | Weak pattern: ${{worstText}}`;

        if (!scoreboard.length) {{
          learningNode.innerHTML = `<li class="item">No strategy registry data yet.</li>`;
          return;
        }}
        learningNode.innerHTML = scoreboard.map((item) => {{
          const statusClass = item.status === "active" ? "trending" : (item.status === "retired" ? "high_vol" : "sideways");
          return `
            <li class="item">
              <div class="item-header">
                <span class="item-title">${{item.symbol}}</span>
                <span class="badge ${{statusClass}}">${{item.status || "n/a"}}</span>
              </div>
              <div class="muted">${{item.family || "n/a"}}</div>
              <div class="muted">score=${{formatNumber(item.score, 2)}} selected=${{item.times_selected}}</div>
              <div class="muted">wins=${{item.wins}} losses=${{item.losses}} pnl=${{formatNumber(item.realized_pnl, 2)}}</div>
            </li>
          `;
        }}).join("");
      }}

      function renderChartSnapshot(symbol, candles, features, report) {{
        if (!chartSnapshotNode) {{
          return;
        }}
        const slice = candles.slice(-140);
        const latestFeature = features.length ? features[features.length - 1] : {{}};
        const result = report && report.results ? report.results.find((item) => item.symbol === symbol) : null;
        const latestSignal = result && result.evolution ? result.evolution.latest_signal : null;
        const regime = result && result.evolution ? (result.evolution.market_regime || "n/a") : "n/a";
        const position = latestPortfolio.positions ? latestPortfolio.positions[symbol] : null;
        const firstClose = slice.length ? slice[0].close : null;
        const lastClose = slice.length ? slice[slice.length - 1].close : null;
        const visibleMove = firstClose && lastClose ? ((lastClose - firstClose) / firstClose) * 100 : null;
        const market = getMarketForSymbol(symbol);
        const confidence = latestSignal ? latestSignal.confidence : null;
        const positionSub = position ? `Avg ${{formatPrice(position.average_price, symbol)}}` : "Flat";

        chartSnapshotNode.innerHTML = [
          `<div class="snapshot-card"><div class="label">Market</div><div class="value">${{market}}</div><div class="sub">${{isExecutionEligible(market) ? "paper tradable" : "research only"}}</div></div>`,
          `<div class="snapshot-card"><div class="label">Last Price</div><div class="value">${{formatPrice(lastClose, symbol)}}</div><div class="sub">Visible move ${{formatPercent(visibleMove, 2)}}</div></div>`,
          `<div class="snapshot-card"><div class="label">Signal</div><div class="value">${{latestSignal ? latestSignal.action : "n/a"}}</div><div class="sub">Confidence ${{formatNumber(confidence, 2)}}</div></div>`,
          `<div class="snapshot-card"><div class="label">Regime</div><div class="value">${{regime}}</div><div class="sub">RSI ${{formatNumber(latestFeature.rsi_14, 2)}}</div></div>`,
          `<div class="snapshot-card"><div class="label">Momentum</div><div class="value">${{formatNumber(latestFeature.momentum_5, 4)}}</div><div class="sub">Vol ${{formatNumber(latestFeature.volatility_10, 4)}}</div></div>`,
          `<div class="snapshot-card"><div class="label">Sentiment</div><div class="value">${{formatNumber(latestFeature.sentiment_score, 2)}}</div><div class="sub">News ${{formatNumber(latestFeature.news_intensity, 2)}}</div></div>`,
          `<div class="snapshot-card"><div class="label">Position</div><div class="value">${{position ? position.quantity : 0}}</div><div class="sub">${{positionSub}}</div></div>`,
          `<div class="snapshot-card"><div class="label">Bars In View</div><div class="value">${{slice.length ? slice.length : 0}}</div><div class="sub">Visible chart depth</div></div>`
        ].join("");
      }}

      async function loadSymbolPanels(symbol) {{
        if (!symbol) {{
          return;
        }}
        try {{
          const report = await fetchJsonSafe("/api/trading/latest", null) || await fetchJsonSafe("/api/research/latest", null);
          const intervalQuery = activeInterval ? `?interval=${{encodeURIComponent(activeInterval)}}` : "";
          const [candles, features, trades, events] = await Promise.all([
            fetchJsonSafe(`/api/market/${{symbol}}${{intervalQuery}}`, [], true),
            fetchJsonSafe(`/api/features/${{symbol}}${{intervalQuery}}`, [], true),
            fetchJsonSafe("/api/trades?limit=200", []),
            fetchJsonSafe("/api/events?limit=200", []),
          ]);

          const symbolTrades = trades.filter((trade) => trade.symbol === symbol);
          renderChart(chartCanvas, chartMetaNode, symbol, candles, features, symbolTrades);
          renderBrain(symbol, report, features, events);
          renderChartSnapshot(symbol, candles, features, report);
        }} catch (error) {{
          chartMetaNode.textContent = `Chart data unavailable: ${{error.message}}`;
          drawCanvasPlaceholder(chartCanvas, "Stored chart data is unavailable.");
          brainNoteNode.textContent = "Symbol details could not be refreshed.";
        }}
      }}

      function renderChart(canvas, metaNode, symbol, candles, features, trades) {{
        const slice = candles.slice(-140);
        const featureSlice = features.slice(-slice.length);
        if (slice.length === 0) {{
          metaNode.textContent = `No candles for ${{symbol}} yet.`;
          drawCanvasPlaceholder(canvas, `No candles for ${{symbol}} yet.`);
          return;
        }}

        const container = canvas.parentElement || canvas;
        const width = container.clientWidth || 960;
        const height = Math.max(320, container.clientHeight || 520);
        const ratio = window.devicePixelRatio || 1;
        canvas.width = width * ratio;
        canvas.height = height * ratio;
        const ctx = canvas.getContext("2d");
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, width, height);

        const highs = slice.map((c) => c.high);
        const lows = slice.map((c) => c.low);
        const minPrice = Math.min(...lows);
        const maxPrice = Math.max(...highs);
        const range = maxPrice - minPrice || 1;
        const padding = 18;
        const chartHeight = height - padding * 2;
        const chartWidth = width - padding * 2;
        const xStep = chartWidth / slice.length;
        const candleWidth = Math.max(2, xStep * 0.6);

        const priceY = (price) =>
          height - padding - ((price - minPrice) / range) * chartHeight;

        ctx.strokeStyle = "rgba(148, 163, 184, 0.12)";
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i += 1) {{
          const y = padding + (chartHeight / 4) * i;
          ctx.beginPath();
          ctx.moveTo(padding, y);
          ctx.lineTo(width - padding, y);
          ctx.stroke();
        }}

        slice.forEach((candle, index) => {{
          const x = padding + xStep * index + xStep / 2;
          const openY = priceY(candle.open);
          const closeY = priceY(candle.close);
          const highY = priceY(candle.high);
          const lowY = priceY(candle.low);
          const rising = candle.close >= candle.open;
          ctx.strokeStyle = rising ? "#22c55e" : "#ef4444";
          ctx.fillStyle = rising ? "rgba(34, 197, 94, 0.65)" : "rgba(239, 68, 68, 0.65)";

          ctx.beginPath();
          ctx.moveTo(x, highY);
          ctx.lineTo(x, lowY);
          ctx.stroke();

          const bodyTop = Math.min(openY, closeY);
          const bodyHeight = Math.max(1, Math.abs(openY - closeY));
          ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
        }});

        const drawIndicator = (key, color) => {{
          ctx.strokeStyle = color;
          ctx.lineWidth = 1.6;
          ctx.beginPath();
          let started = false;
          featureSlice.forEach((row, index) => {{
            const value = row[key];
            if (value == null) {{
              return;
            }}
            const x = padding + xStep * index + xStep / 2;
            const y = priceY(value);
            if (!started) {{
              ctx.moveTo(x, y);
              started = true;
            }} else {{
              ctx.lineTo(x, y);
            }}
          }});
          ctx.stroke();
        }};

        drawIndicator("sma_20", "rgba(56, 189, 248, 0.9)");
        drawIndicator("ema_12", "rgba(251, 191, 36, 0.9)");

        trades.forEach((trade) => {{
          const tradeTime = new Date(trade.timestamp).getTime();
          let closestIndex = 0;
          let closestDelta = Number.POSITIVE_INFINITY;
          slice.forEach((candle, index) => {{
            const delta = Math.abs(new Date(candle.timestamp).getTime() - tradeTime);
            if (delta < closestDelta) {{
              closestDelta = delta;
              closestIndex = index;
            }}
          }});
          const candle = slice[closestIndex];
          if (!candle) {{
            return;
          }}
          const x = padding + xStep * closestIndex + xStep / 2;
          const y = trade.action === "BUY" ? priceY(candle.low) - 8 : priceY(candle.high) + 8;
          ctx.fillStyle = trade.action === "BUY" ? "#22c55e" : "#ef4444";
          ctx.beginPath();
          if (trade.action === "BUY") {{
            ctx.moveTo(x, y);
            ctx.lineTo(x - 6, y + 10);
            ctx.lineTo(x + 6, y + 10);
          }} else {{
            ctx.moveTo(x, y);
            ctx.lineTo(x - 6, y - 10);
            ctx.lineTo(x + 6, y - 10);
          }}
          ctx.closePath();
          ctx.fill();
        }});

        const lastCandle = slice[slice.length - 1];
        metaNode.textContent = `${{symbol}} | interval=${{activeInterval || "n/a"}} | candles=${{slice.length}} | last=${{formatPrice(lastCandle.close, symbol)}}`;
      }}

      function renderBrain(symbol, report, features, events = []) {{
        if (!report || !report.results) {{
          brainNode.innerHTML = `<li class="item">Run a research or trading cycle to see details.</li>`;
          brainNoteNode.textContent = "No symbol intelligence loaded yet.";
          return;
        }}
        const result = report.results.find((item) => item.symbol === symbol);
        if (!result) {{
          brainNode.innerHTML = `<li class="item">No data for ${{symbol}}.</li>`;
          brainNoteNode.textContent = "This symbol is not in the latest cycle.";
          return;
        }}
        const latestSignal = result.evolution.latest_signal;
        const metaGenome = result.evolution.meta_selected ? result.evolution.meta_selected.genome : null;
        const genome = metaGenome || result.evolution.champion.genome;
        const latestFeature = features.length ? features[features.length - 1] : {{}};
        const regime = result.evolution.market_regime ?? "n/a";
        const metaReason = result.evolution.meta_reason || "n/a";
        const latestEvent = (events || []).filter((item) => item.symbol === symbol).slice(-1)[0] || null;
        const market = getMarketForSymbol(symbol);
        const executable = isExecutionEligible(market);

        brainNode.innerHTML = [
          `<li class="item"><strong>Signal</strong><div class="muted">${{formatSignal(latestSignal.action)}} conf=${{formatNumber(latestSignal.confidence, 3)}}</div></li>`,
          `<li class="item"><strong>Strategy</strong><div class="muted">family=${{genome.family}} id=${{genome.strategy_id}}</div></li>`,
          `<li class="item"><strong>Regime</strong><div class="muted">${{regime}}</div></li>`,
          `<li class="item"><strong>Meta</strong><div class="muted">${{metaReason}}</div></li>`,
          `<li class="item"><strong>Reason</strong><div class="muted">${{latestSignal.reason}}</div></li>`,
          `<li class="item"><strong>Indicators</strong><div class="muted">RSI=${{formatNumber(latestFeature.rsi_14)}} Momentum=${{formatNumber(latestFeature.momentum_5, 4)}} Vol=${{formatNumber(latestFeature.volatility_10, 4)}}</div></li>`,
          `<li class="item"><strong>Sentiment</strong><div class="muted">score=${{formatNumber(latestFeature.sentiment_score, 2)}} news=${{formatNumber(latestFeature.news_intensity, 2)}}</div></li>`
        ].join("");

        brainNoteNode.textContent = latestEvent
          ? `Interval ${{activeInterval || "n/a"}} | ${{market}} | ${{executable ? "eligible for paper execution" : "research only in current execution settings"}} | ${{latestEvent.order_note || latestEvent.signal_reason || "No note"}}`
          : `Interval ${{activeInterval || "n/a"}} | ${{market}} | ${{executable ? "eligible for paper execution" : "research only in current execution settings"}}`;
      }}

      async function runCycle() {{
        const button = document.getElementById("run-cycle");
        button.disabled = true;
        button.textContent = "Running...";
        try {{
          const result = await postJson("/api/research/run");
          await loadDashboard();
          setBanner(`Research cycle finished for ${{(result.symbols || []).length}} symbols.`, "success");
        }} catch (error) {{
          setBanner(`Research cycle failed: ${{error.message}}`, "error");
        }} finally {{
          button.disabled = false;
          button.textContent = "Run Research Cycle";
        }}
      }}

      async function runTradeCycle() {{
        const button = document.getElementById("run-trade");
        button.disabled = true;
        button.textContent = "Trading...";
        try {{
          const result = await postJson("/api/trading/run");
          const trades = (result.results || []).filter((item) => item.latest_order && item.latest_order.status === "FILLED").length;
          await loadDashboard();
          setBanner(`Trading cycle finished. Filled orders: ${{trades}}.`, "success");
        }} catch (error) {{
          setBanner(`Trading cycle failed: ${{error.message}}`, "error");
        }} finally {{
          button.disabled = false;
          button.textContent = "Run Trading Cycle";
        }}
      }}

      const runCycleButton = document.getElementById("run-cycle");
      const runTradeButton = document.getElementById("run-trade");
      const refreshButton = document.getElementById("refresh");
      if (runCycleButton) {{
        runCycleButton.addEventListener("click", runCycle);
      }}
      if (runTradeButton) {{
        runTradeButton.addEventListener("click", runTradeCycle);
      }}
      if (refreshButton) {{
        refreshButton.addEventListener("click", loadDashboard);
      }}
      if (chartSymbolNode) {{
        chartSymbolNode.addEventListener("change", async (event) => {{
          activeSymbol = event.target.value;
          await loadSymbolPanels(activeSymbol);
        }});
      }}
      if (chartIntervalNode) {{
        chartIntervalNode.addEventListener("change", async (event) => {{
          activeInterval = event.target.value;
          renderRefreshMeta();
          if (activeSymbol) {{
            await loadSymbolPanels(activeSymbol);
          }}
          if (activeReplayTrade) {{
            await loadReplayDetail(activeReplayTrade);
          }}
        }});
      }}
      if (autoRefreshNode) {{
        autoRefreshNode.addEventListener("click", () => {{
          autoRefreshEnabled = !autoRefreshEnabled;
          renderRefreshMeta();
          scheduleAutoRefresh();
        }});
      }}
      if (replayTradeNode) {{
        replayTradeNode.addEventListener("change", async (event) => {{
          activeReplayTrade = event.target.value;
          if (activeReplayTrade) {{
            await loadReplayDetail(activeReplayTrade);
          }}
        }});
      }}
      document.querySelectorAll(".workspace-nav [data-jump]").forEach((button) => {{
        button.addEventListener("click", () => {{
          const target = document.getElementById(button.dataset.jump);
          if (!target) {{
            return;
          }}
          document.querySelectorAll(".workspace-nav [data-jump]").forEach((item) => item.classList.remove("active"));
          button.classList.add("active");
          target.scrollIntoView({{ behavior: "smooth", block: "start" }});
        }});
      }});

      renderRefreshMeta();
      loadDashboard();
      let resizeTimer = null;
      window.addEventListener("resize", () => {{
        if (resizeTimer) {{
          clearTimeout(resizeTimer);
        }}
        resizeTimer = setTimeout(async () => {{
          if (activeSymbol) {{
            await loadSymbolPanels(activeSymbol);
          }}
          if (activeReplayTrade) {{
            await loadReplayDetail(activeReplayTrade);
          }}
        }}, 150);
      }});

      async function loadReplayTrades() {{
        const trades = await fetchJsonSafe("/api/trades?limit=200", []);
        if (!trades.length) {{
          replayTradeNode.innerHTML = `<option value="">No trades yet</option>`;
          replayMetaNode.textContent = "No trades available.";
          drawCanvasPlaceholder(replayCanvas, "Trade replay will appear after the first fills.");
          replayDetailsNode.textContent = "Trade details will appear here.";
          return;
        }}
        replayTradeNode.innerHTML = trades
          .map((trade) => `<option value="${{trade.trade_id}}">${{trade.symbol}} ${{trade.action}} @ ${{new Date(trade.timestamp).toLocaleTimeString()}}</option>`)
          .join("");
        if (!activeReplayTrade || !trades.some((trade) => trade.trade_id === activeReplayTrade)) {{
          activeReplayTrade = trades[0].trade_id;
        }}
        replayTradeNode.value = activeReplayTrade;
        await loadReplayDetail(activeReplayTrade);
      }}

      async function loadReplayDetail(tradeId) {{
        const intervalQuery = activeInterval ? `?interval=${{encodeURIComponent(activeInterval)}}` : "";
        const replay = await fetchJsonSafe(`/api/trades/replay/${{tradeId}}${{intervalQuery}}`, null);
        if (!replay) {{
          replayMetaNode.textContent = "Trade replay unavailable.";
          return;
        }}
        renderReplay(replay.symbol, replay.candles, replay.features, replay.trade, replay.paired_trade);
      }}

      function renderReplay(symbol, candles, features, trade, pairedTrade) {{
        const replayTrades = [];
        if (trade) {{
          replayTrades.push(trade);
        }}
        if (pairedTrade) {{
          replayTrades.push(pairedTrade);
        }}
        renderChart(replayCanvas, replayMetaNode, symbol, candles, features, replayTrades);
        if (!trade) {{
          replayMetaNode.textContent = "Select a trade to replay.";
          replayDetailsNode.textContent = "Trade details will appear here.";
          return;
        }}

        replayMetaNode.textContent = `${{symbol}} | ${{trade.action}} ${{trade.quantity}} @ ${{formatPrice(trade.fill_price, symbol)}}`;
        const entry = trade.action === "BUY" ? trade : (pairedTrade && pairedTrade.action === "BUY" ? pairedTrade : null);
        const exit = trade.action === "SELL" ? trade : (pairedTrade && pairedTrade.action === "SELL" ? pairedTrade : null);
        if (entry && exit) {{
          const pnl = (exit.fill_price - entry.fill_price) * entry.quantity;
          const pct = entry.fill_price ? (pnl / (entry.fill_price * entry.quantity)) * 100 : 0;
          replayDetailsNode.textContent =
            `Entry ${{formatPrice(entry.fill_price, symbol)}} -> Exit ${{formatPrice(exit.fill_price, symbol)}} | PnL ${{formatPrice(pnl, symbol)}} (${{pct.toFixed(2)}}%)`;
        }} else {{
          replayDetailsNode.textContent = `Open trade | Avg ${{formatPrice(trade.fill_price, symbol)}} | Qty ${{trade.quantity}}`;
        }}
      }}
    </script>
  </body>
</html>
"""
