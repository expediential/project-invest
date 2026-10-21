# Phased Roadmap

## Phase Zero — Forensics and evidence baseline (completed)

Artifacts: implementation audit, dependency map, research risk register, this roadmap, and implementation log. Source changed only by adding documentation. Test execution is blocked until project dependencies are installed in an isolated environment; compilation passed.

Acceptance criteria: observed architecture and gaps are documented without claiming unverified behavior.

## Phase One — Stabilize paper-only operation

**In progress (2026-10-21):** paper-only startup validation, separate worker roles, protected cycle-triggering API routes, no mock fallback, point-in-time local sentiment, a candidate-validation holdout, and strict paper-promotion blocking are implemented. Durable leases, atomic recovery, migrations, and full readiness checks remain acceptance blockers.

1. Enforce strict paper-only startup validation and remove production mock fallback.
2. Choose one worker topology; add durable cycle ownership and idempotency.
3. Add durable event/command transitions, reconciliation, and restart recovery.
4. Fix backtest execution semantics, metrics frequency, and strict split contracts before any strategy promotion.
5. Lock down remote control; introduce health/readiness, structured logs, and failure visibility.
6. Add a secret-free `.env.example`, correct deployment docs, migration baseline, and local/Postgres integration tests.

Acceptance criteria: no route/configuration can create live orders; provider/storage/staleness failures block entries; only one worker owns a cycle; a restart cannot duplicate/reconcile incorrectly; Phase One regression suite passes in an isolated environment.

## Phase Two — Reproducible experiments

Implement a laptop-first experiment definition/run/result/artifact registry with immutable snapshots, code revision, redacted configuration, dataset/feature identities, deterministic seed, bounded queue, cancellation, deduplication, and status lifecycle. Do not add Cosmos dependency.

Acceptance criteria: equivalent submission deduplicates; a saved specification reproduces a completed local run; failed/cancelled/rejected runs are durable and explainable.

## Phase Three — Opportunity discovery

Start with verified NSE-only eligibility. Build explainable ranking components and a documented normalized/rule-based ranking procedure that can return zero candidates. Separate research from paper-execution eligibility.

Acceptance criteria: rankings expose components, timestamps, freshness, uncertainty, eligibility and rejection reasons; sensitivity tests and no-candidate tests pass.

## Phase Four — Controlled strategy research

Define a bounded strategy-family interface, registry lifecycle, parameter-search accounting, and baseline comparisons. Keep family choice, parameters, assets, and allocation separate.

Acceptance criteria: strategies cannot inspect final holdout data; registry states and promotion/demotion reasons are durable; evidence minimums prevent tiny-sample promotion.

## Phase Five — Realistic validation

Add frozen holdout, purged/embargoed time splits where justified, cost scenarios, robustness analysis, and documented annualization. Track the total search count.

Acceptance criteria: deterministic leakage tests, benchmark comparisons, and validation reports include costs, sample adequacy, uncertainty, and rejection reasons.

## Phase Six — Constrained allocation

Add allocator input contracts, hard risk limits independent of strategies/models, and baseline comparisons. Permit zero exposure for incomplete or uncertain inputs.

Acceptance criteria: concentration, covariance, liquidity, turnover, cost, and uncertainty constraints are enforced in integration tests.

## Phase Seven — Trade memory analytics and learning

First normalize decision/order/fill/position/exit/outcome records. Add descriptive analytics, then candidate Logistic Regression/tree baselines only when evidence thresholds are met. Use candidate → validation → shadow → paper promotion with rollback.

Acceptance criteria: no outcome field appears in decision inputs; unseen chronological evaluation and calibration reports exist; no automatic deployment from training.

## Phase Eight — Events and sentiment

Implement approved modular sources only, each with publication/observation/ingestion time, source health, licensing status, and as-of backtest behavior.

Acceptance criteria: availability-time tests prevent look-ahead; provider failure/freshness is visible and non-executable.

## Phase Nine — Optional Cosmos backend

Prerequisite: documented approved access, scheduler/runtime/storage/network/data policy verification. Then add generic queued backend followed by a thin Cosmos submission adapter; never let it affect trading availability or promote directly.

Acceptance criteria: local backend remains functional when Cosmos is unavailable; jobs have bounded resources, cancellation, logs, checksum, seed, and status.

## Phase Ten — Dashboard and observability

Incrementally expose experiments, rankings, allocation, health, memory, replay, and data quality with safe empty/error/stale states. Preserve API compatibility or version changes.

Acceptance criteria: dashboards distinguish simulated from realized results, expose decision explanations and data/model versions, and retain chart usability.

## Phase Eleven — Proven cleanup

Remove only components shown redundant by references, tests, and equivalent behavior. No architectural expansion without measured need.

Acceptance criteria: every deletion has a rationale, migration/rollback note, and passing regression coverage.
