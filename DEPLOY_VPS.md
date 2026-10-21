# VPS Deployment Checklist

This is the fastest clean path to run Project Invest 24/7 on a Linux VPS.

It is written for:

- Ubuntu 24.04 or 22.04
- your GitHub repo at `https://github.com/expediential/project-invest.git`
- a domain you will point later, such as `invest.yourdomain.com`

This guide uses the production stack already in this repo:

- [Dockerfile](/C:/Users/ADMIN/Documents/New%20project/hacks/project%20invest/Dockerfile)
- [docker-compose.prod.yml](/C:/Users/ADMIN/Documents/New%20project/hacks/project%20invest/docker-compose.prod.yml)
- [deploy/nginx/nginx.conf](/C:/Users/ADMIN/Documents/New%20project/hacks/project%20invest/deploy/nginx/nginx.conf)

## 1. Create the server

Use:

- Oracle Cloud Always Free if you can complete account verification
- otherwise a small Ubuntu VPS

Recommended minimum:

- 2 vCPU
- 4 GB RAM
- 40+ GB disk

Open these firewall ports:

- `22` for SSH
- `80` for HTTP
- `443` for HTTPS later

## 2. SSH into the server

Replace `YOUR_SERVER_IP` with the server IP:

```bash
ssh ubuntu@YOUR_SERVER_IP
```

If your provider uses `root` instead of `ubuntu`, use:

```bash
ssh root@YOUR_SERVER_IP
```

## 3. Install Docker and Git

Paste this whole block:

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

## 4. Clone your repo

```bash
git clone https://github.com/expediential/project-invest.git
cd project-invest
```

## 5. Create the production environment file

```bash
cp .env.example .env
```

Open it:

```bash
nano .env
```

Use these values as your baseline production config:

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
PROJECT_INVEST_LIVE_LOOP_SECONDS=60
PROJECT_INVEST_DATA_ROOT=runtime/data_lake
```

Important:

- keep all loop flags `false`
- the dedicated Docker worker containers will own the loops
- do not turn embedded API loops on in this deployment model

Save and exit `nano`:

- `Ctrl+O`
- `Enter`
- `Ctrl+X`

## 6. Start the stack

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

This starts:

- `nginx`
- `api`
- `research_worker`
- `trading_worker`
- `postgres`
- `redis`

## 7. Verify everything is running

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
```

In a second SSH session, check the workers:

```bash
docker compose -f docker-compose.prod.yml logs -f research_worker
docker compose -f docker-compose.prod.yml logs -f trading_worker
```

Health check:

```bash
curl http://127.0.0.1/health
```

If healthy, open in your browser:

```text
http://YOUR_SERVER_IP/
```

## 8. Point your domain

In your domain provider DNS panel:

- create an `A` record
- host: `@` or `invest`
- value: `YOUR_SERVER_IP`

Examples:

- `yourdomain.com -> YOUR_SERVER_IP`
- `invest.yourdomain.com -> YOUR_SERVER_IP`

Once DNS propagates, your site should load over HTTP.

## 9. Add HTTPS later

Fastest clean option:

- put Cloudflare in front of the server and enable proxy + SSL

Alternative:

- add Caddy or Certbot later on the VPS

For the first deploy, get plain HTTP working first.

## 10. Update the app later

Whenever you push new code:

```bash
cd ~/project-invest
git pull
docker compose -f docker-compose.prod.yml up --build -d
```

## 11. Restart the app if needed

Restart everything:

```bash
docker compose -f docker-compose.prod.yml restart
```

Restart just the API:

```bash
docker compose -f docker-compose.prod.yml restart api
```

Restart just the workers:

```bash
docker compose -f docker-compose.prod.yml restart research_worker trading_worker
```

## 12. Useful commands

See running containers:

```bash
docker compose -f docker-compose.prod.yml ps
```

See live logs:

```bash
docker compose -f docker-compose.prod.yml logs -f
```

Stop the stack:

```bash
docker compose -f docker-compose.prod.yml down
```

Stop and remove volumes too:

```bash
docker compose -f docker-compose.prod.yml down -v
```

## 13. Troubleshooting

If the site does not load:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.prod.yml logs -f api
```

If health works but trading/research is idle:

```bash
docker compose -f docker-compose.prod.yml logs -f research_worker
docker compose -f docker-compose.prod.yml logs -f trading_worker
```

If Postgres or Redis connection fails:

- make sure `.env` uses `postgres` and `redis`, not `localhost`

Correct:

```env
PROJECT_INVEST_POSTGRES_DSN=postgresql://project_invest:project_invest@postgres:5432/project_invest
PROJECT_INVEST_REDIS_URL=redis://redis:6379/0
```

If Yahoo rate limits you:

- keep `PROJECT_INVEST_ALLOW_MOCK_FALLBACK=false`; provider failures must block new entries
- start with `NSE` only
- expand universes after the server is stable

## 14. What to replace

Before you deploy, replace these placeholders:

- `YOUR_SERVER_IP`
- `yourdomain.com`
- `invest.yourdomain.com`

## 15. Recommended first live test

After deploy:

1. Open `/health`
2. Open `/`
3. Wait for the first research cycle
4. Wait for the first trading cycle
5. Check:

```bash
curl http://127.0.0.1/api/research/latest
curl http://127.0.0.1/api/trading/latest
curl http://127.0.0.1/api/trades?limit=5
```

That gives you a full end-to-end proof that:

- the site is up
- the workers are alive
- the database is working
- the bot is producing output continuously
