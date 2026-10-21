# Research Risk Register

| ID | Severity | Risk and evidence | Consequence | Mitigation / gate | Validation evidence required |
| --- | --- | --- | --- | --- | --- |
| R-01 | Critical | Public `/api/trading/run` with no auth behind public Nginx | Unauthorized paper orders and state changes | Authenticated admin control or remove remote execution route | Authorization and idempotency integration tests |
| R-02 | Critical | `live` configuration remains accepted | Future adapter could accidentally create a live path | Fail configuration closed to paper-only | Startup rejects `live` in every environment |
| R-03 | Critical | Deployment enables mock fallback | Synthetic data may drive research/paper decisions | No mock fallback beyond explicit tests | Provider failure prevents new entries |
| R-04 | Critical | Latest sentiment is attached to historical features | Look-ahead bias and invalid evidence | Timestamped as-of event joins only | Future events cannot alter past features/backtests |
| R-05 | Critical | Evaluation lacks untouched holdout and explicit training artifacts | Overfitting presented as validation | Versioned time splits, purging where needed, frozen holdout | Chronological split integrity tests |
| R-06 | High | Current-bar fills and same-bar stop/target ambiguity | Inflated backtest performance | Conservative documented fill policy | Gap and intrabar collision tests |
| R-07 | High | Sharpe always annualized by 252 | Invalid metrics for intraday intervals | Interval-aware policy | Metric-frequency tests |
| R-08 | High | Soft promotion permits weak candidates | Unproven strategies can receive paper allocation | Strict gate and explicit registry states | Weak-candidate cannot-buy regression |
| R-09 | High | Optimizer ignores covariance/liquidity/uncertainty and is disconnected from execution | Misleading allocation outputs | Keep analytics-only; build constrained allocator later | Invalid/correlation/zero-exposure tests |
| R-10 | High | Portfolio/order/event/memory writes are separate | Restart can leave unreconciled or duplicate state | Atomic command/event ledger and recovery | Failure-injection restart tests |
| R-11 | High | Multiple execution owners without durable lease | Duplicate cycles and orders | One owner plus storage-backed lease | Multi-process duplicate-start test |
| R-12 | High | Invalid settings silently revert to defaults | Unsafe configuration is masked | Strict schema + cross-field checks | Invalid configuration fails at startup |
| R-13 | Medium | Runtime DDL and JSONB full scans lack migrations/indexes | Upgrade and performance hazards | Migration/versioning and indexed queries | Migration + Postgres integration tests |
| R-14 | Medium | Trade memory excludes decisions/rejections | Biased future learning data | Decision-to-outcome event model | Rejected decision reconciliation test |
| R-15 | Medium | Yahoo assumptions use US trading minutes for intraday history | Inaccurate NSE data coverage | Market-calendar-specific data policy | NSE calendar/data-quality tests |
| R-16 | Medium | Health reports `ok` without storage/provider readiness | Operational failures hidden | Separate liveness/readiness checks | Outage health integration tests |
| R-17 | Medium | Docs reference absent `.env.example`, conflicting repository URL, and HTTP-first deployment | Misconfiguration and unsafe deployments | Correct, tested docs and safe example env | Documentation smoke test |
| R-18 | Medium | No approval/access evidence for Cosmos | Unapproved use or infeasible design | Do not implement Cosmos adapter before written access/scheduler verification | Access checklist completed and adapter contract test |

## Risk acceptance

### Mitigation update — 2026-10-21

R-01 through R-05 have been materially reduced by bearer-protected operational routes, paper-only validation, explicit mock provenance, point-in-time local sentiment, and a candidate-validation holdout. They are not eliminated: bearer tokens require secure deployment and rotation, and the final holdout is not yet persisted as an experiment artifact. R-10, R-11, R-13, R-14, R-16, and R-18 remain open.

No critical risk is accepted for Phase One. The current application may remain a local development prototype only. It must not be described as production-ready, profitable, autonomous in an unrestricted sense, or suitable for live trading.
