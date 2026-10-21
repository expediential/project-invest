# Contributing

Project Invest accepts focused, evidence-backed contributions. It is a paper-trading and research project; live brokerage functionality is out of scope.

## Setup

Use Python 3.11 or later, create a virtual environment, and install development dependencies:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]
.venv\Scripts\python -m pytest -q --basetemp .tmp_pytest -p no:cacheprovider
```

On Linux/macOS, use `.venv/bin/python` in place of `.venv\Scripts\python`.

Copy `.env.example` to `.env`, keep paper mode, and never commit the generated API token. Use deterministic synthetic fixtures for tests; do not make CI depend on live market providers.

## Expectations

- Keep changes small and add regression tests for behavior changes.
- Preserve chronological data boundaries and independent risk controls.
- Use Conventional Commit-style messages where practical.
- Do not add secrets, personal data, market datasets without clear licensing, or live-order code.

Report defects with reproduction steps and expected versus actual behavior. For security-sensitive reports, follow [SECURITY.md](SECURITY.md).
