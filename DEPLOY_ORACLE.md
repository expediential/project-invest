# Oracle VM Deployment

This guide deploys Project Invest on a single Oracle Cloud VM using Docker Compose.

## Recommended production shape

- `nginx`
  - public entrypoint on port 80
- `api`
  - FastAPI dashboard and API
- `research_worker`
  - continuous strategy discovery and validation loop
- `trading_worker`
  - continuous paper-trading execution loop
- `postgres`
  - durable state for candles, features, trades, portfolio, and reports
- `redis`
  - optional cache layer

## 1. Create the VM

Recommended baseline:

- Ubuntu 22.04 or 24.04
- open ports `22`, `80`, and optionally `443`
- install Docker and Docker Compose plugin

Example package setup:

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin git
sudo usermod -aG docker $USER
```

Log out and back in once after adding yourself to the `docker` group.

## 2. Clone the repo

```bash
git clone <your-repo-url> project-invest
cd project-invest
```

## 3. Create the environment file

```bash
cp .env.example .env
```

Recommended production values:

```env
PROJECT_INVEST_EXECUTION_MODE=paper
PROJECT_INVEST_MARKET_DATA_PROVIDER=yahoo
PROJECT_INVEST_ALLOW_MOCK_DATA=false
PROJECT_INVEST_ALLOW_MOCK_FALLBACK=false
PROJECT_INVEST_STORAGE_BACKEND=postgres
PROJECT_INVEST_STORAGE_CACHE_ENABLED=true
PROJECT_INVEST_POSTGRES_DSN=postgresql://project_invest:project_invest@postgres:5432/project_invest
PROJECT_INVEST_POSTGRES_SCHEMA=project_invest
PROJECT_INVEST_REDIS_URL=redis://redis:6379/0
PROJECT_INVEST_USE_MARKET_UNIVERSES=true
PROJECT_INVEST_MARKET_UNIVERSES=NSE
PROJECT_INVEST_EXECUTION_MARKETS=NSE
PROJECT_INVEST_RESEARCH_SYMBOLS=RELIANCE.NS,TCS.NS,INFY.NS
PROJECT_INVEST_RESEARCH_INTERVAL=15m
PROJECT_INVEST_TRADING_INTERVAL=5m
PROJECT_INVEST_RESEARCH_LOOP_ENABLED=false
PROJECT_INVEST_RESEARCH_LOOP_SECONDS=21600
PROJECT_INVEST_TRADING_LOOP_ENABLED=false
PROJECT_INVEST_TRADING_LOOP_SECONDS=900
PROJECT_INVEST_LIVE_LOOP_ENABLED=false
```

Notes:

- keep all `*_LOOP_ENABLED` flags set to `false`
  - the dedicated worker containers own the long-running loops in production
- Provider failures must block new paper entries; mock fallback is intentionally disabled.
- start with `NSE` only
  - then add more universes after the box is stable

## 4. Start the stack

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Check status:

```bash
docker compose -f docker-compose.prod.yml ps
```

Check logs:

```bash
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f research_worker
docker compose -f docker-compose.prod.yml logs -f trading_worker
```

## 5. Open the dashboard

Visit:

```text
http://YOUR_VM_PUBLIC_IP/
```

Useful endpoints:

- `/`
- `/health`
- `/api/config`
- `/api/research/run`
- `/api/portfolio`
- `/api/trades`
- `/api/analytics/summary`

## 6. Manual research run

From the VM:

```bash
docker compose -f docker-compose.prod.yml exec api python -m project_invest run-once
```

## 7. Updating the deployment

```bash
git pull
docker compose -f docker-compose.prod.yml up --build -d
```

## 8. Required deployment hardening

- put Cloudflare or another proxy in front
- add HTTPS with Caddy, Traefik, or Nginx + Certbot
- set a strong `PROJECT_INVEST_API_AUTH_TOKEN` and do not expose it in logs
- use HTTPS and network access controls before exposing the dashboard
- change the default Postgres password
- add VM-level firewall restrictions
- add backups for the Postgres volume

## 9. Troubleshooting

If `/health` loads but no research happens:

- inspect the worker logs
- confirm `research_worker` and `trading_worker` are running in `docker compose ps`
- confirm the `.env` values point to `postgres` and `redis`, not `localhost`

If the app fails on startup:

- check `docker compose logs api`
- check `docker compose logs research_worker`
- check `docker compose logs trading_worker`
- verify the `PROJECT_INVEST_POSTGRES_DSN` uses host `postgres`
- verify the `PROJECT_INVEST_REDIS_URL` uses host `redis`

If you want to stop the whole stack:

```bash
docker compose -f docker-compose.prod.yml down
```

To stop it and remove named volumes too:

```bash
docker compose -f docker-compose.prod.yml down -v
```
