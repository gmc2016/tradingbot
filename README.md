# Trading Bot

Automated crypto trading bot — React dashboard, Python backend, Docker.

## First-time setup

### 1. Clone and configure on your NAS

```bash
ssh your-nas-ip
cd /volume1/docker
git clone https://github.com/gmc2016/tradingbot.git
cd tradingbot
cp .env.example .env
nano .env   # fill in your API keys
```

### 2. Deploy via Portainer

- Portainer → Stacks → Add stack
- Choose **Git Repository**
- Repository URL: `https://github.com/gmc2016/tradingbot`
- Compose path: `docker-compose.yml`
- Enable **Automatic updates** (optional — pulls on redeploy)
- Add environment variables from your `.env` file
- Deploy

Access at: `http://your-nas-ip:3200`

---

## Updating the bot

When code changes are pushed to GitHub:

```
Portainer → Stacks → tradingbot → Pull and redeploy
```

That's it. Database and settings survive in the Docker volume.

---

## API Keys

**Binance:** binance.com → API Management → Create key → enable Spot Trading only

**NewsAPI (free):** newsapi.org → register → copy key

---

## File structure

```
tradingbot/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py              ← Flask + SocketIO server
│   ├── bot/
│   │   ├── engine.py       ← Bot orchestrator + cache
│   │   ├── strategy.py     ← RSI/MACD/BB/ADX signals
│   │   └── exchange.py     ← Binance via ccxt
│   ├── ai/
│   │   └── sentiment.py    ← News fetch + VADER sentiment
│   └── db/
│       └── database.py     ← SQLite helpers
├── frontend/
│   ├── Dockerfile
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/     ← Topbar, Sidebar, Chart, etc.
│   │   └── hooks/
│   └── package.json
└── nginx/
    └── nginx.conf
```
