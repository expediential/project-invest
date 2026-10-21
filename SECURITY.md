# Security Policy

## Supported versions

Security fixes are applied to the current `main` branch while the project remains pre-1.0.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private security-advisory reporting flow for this repository. Include a minimal reproduction, impact, and affected revision; do not include credentials or private market data.

Operational endpoints fail closed without `PROJECT_INVEST_API_AUTH_TOKEN`. Treat that token as a secret, rotate it if exposed, and do not expose the control API on a public network without HTTPS and appropriate network access controls.
