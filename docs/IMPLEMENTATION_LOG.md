# Implementation Log

## 2026-10-13 — Phase Zero: repository forensics

1. **Phase completed:** Phase Zero only. No implementation phase was started.
2. **Files inspected:** repository structure; `README.md`, `ARCHITECTURE.md`, `pyproject.toml`, ignore/Docker/Compose/deployment files; runtime/config/container; API/dashboard/schemas; domain models; providers; services; execution; storage; and all listed tests.
3. **Files created:** `docs/IMPLEMENTATION_AUDIT.md`, `docs/DEPENDENCY_MAP.md`, `docs/RESEARCH_RISK_REGISTER.md`, `docs/ROADMAP.md`, and this log. **Modified/deleted:** none.
4. **Design decisions:** documentation is evidence-based; paper execution is treated as a sensitive control; Cosmos is explicitly deferred pending approved access and technical verification.
5. **Bugs discovered:** critical safety/research-validity findings F-01 through F-05 and the remaining findings listed in the implementation audit. No runtime bugs were fixed in Phase Zero by design.
6. **Tests executed:** `python -m compileall -q src` passed. `git diff --check` passed before documentation creation.
7. **Tests not executed:** `python -m pytest -q` could not start because the active Python interpreter lacks `pytest`; no repository `.venv` is present. No test pass/fail result is claimed.
8. **Known limitations:** experiment system, strict OOS validation, constrained allocation, durable reconciliation, authenticated controls, migrations, and Cosmos adapter are absent; tests require an isolated dependency install.
9. **Migration/configuration changes:** none. No database/storage mutation occurred.
10. **Rollback:** remove only these five documentation files or revert the Phase Zero documentation commit once created. No data rollback is required.
11. **Local verification commands:**

   ```powershell
   python -m compileall -q src
   python -m pytest -q
   git diff --check
   ```

12. **Next phase:** Phase One stabilization. Acceptance requires strict paper-only configuration, no production mock fallback, a single durable worker owner, atomic/recoverable state, correct time-aware validation basics, secured control routes, and passing relevant tests.

## 2026-10-21 — Phase One: security and research integrity (in progress)

1. **Changes completed:** strict paper-only settings; protected operational API routes; no runtime mock fallback; mock provenance and paper-trading rejection; point-in-time local sentiment; candidate-validation holdout; strict promotion block; and separate API/research/trading worker roles.
2. **Verification:** targeted security, API, runtime, sentiment, feature, backtest, promotion, and lab tests passed during development. The complete suite and documentation/CI checks remain to be run before Phase One can be claimed complete.
3. **Residual limitations:** worker coordination is not yet durable across processes; storage writes are not transactional; migrations, robust readiness checks, and persistent experiment/holdout records are not implemented.

## 2026-10-21 — Portfolio reliability and monitoring terminal

1. **Changes completed:** fee-aware paper fills and closes; immutable local/Postgres portfolio-history snapshots; duplicate trade-id protection; pure portfolio reads; a single portfolio-summary service; base-currency display configuration; stored-data quality and explicit remote-compute status APIs; and a responsive paper-only monitoring terminal.
2. **Integrity decisions:** daily P&amp;L is unavailable without a same-day stored baseline; performance charts show only persisted snapshots; positions expose their actual last-mark timestamp; data-quality refresh does not contact a provider; rejected/skipped decisions stay distinct from fills; and Cosmos is reported as `not_configured` until a verified integration exists.
3. **Verification:** portfolio-accounting/local-storage focused suite passed (9 tests); subsequent dashboard/config/accounting/storage focused suite passed (17 tests); dashboard/accounting/storage focused suite passed after the UI split (10 tests); `compileall` and `git diff --check` passed. The base Python runtime available to automation stalls in Starlette's `TestClient`, so the new browser-style monitoring-route test is committed but was not completed there. The user previously reported a full virtual-environment run with 58 passing tests.
4. **Residual limitations:** portfolio latest-state and history writes are still not atomic; old snapshots cannot retroactively gain entry-fee data; Postgres migrations/readiness probes, durable leases, experiment artifacts, provider freshness policy, and a real remote compute adapter remain incomplete.
