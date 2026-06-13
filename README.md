# Stock AI Bot

Personal stock-tracking Telegram bot with Claude analysis. Tracks your holdings, summarizes news, answers buy/sell questions, and sends a morning brief every day at 8 AM Bangkok time.

## What it does

- **Holdings tracking** — `/add PTT.BK 1000`, `/holdings`, `/remove`
- **On-demand analysis** — `/analyze AAPL` returns bull case / bear case / technicals / what to watch
- **News headlines** — `/news DELTA.BK` pulls 5 latest items
- **Free-text chat** — "should I sell ADVANC?" or "PTTEP เป็นยังไงวันนี้" — auto-detects tickers, fetches data, replies with Claude
- **Morning brief** — daily summary of all holdings, sent automatically at 8 AM

Works with US (`AAPL`), Thai (`PTT.BK`), HK (`0700.HK`), and any other ticker yfinance supports.

## Setup (~10 minutes)

### 1. Get a Telegram bot token

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`, follow prompts (name + username ending in `bot`)
3. Save the token it gives you (looks like `123456:ABC-DEF...`)

### 2. Get an Anthropic API key

[console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key

### 3. Push this to GitHub

```bash
cd stock-bot
git init
git add .
git commit -m "init"
gh repo create stock-bot --private --source=. --push
# or push to a GitHub repo you created manually
```

### 4. Deploy on Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Pick your `stock-bot` repo
3. Once it's building, go to **Variables** and add:
   - `TELEGRAM_BOT_TOKEN` — from BotFather
   - `ANTHROPIC_API_KEY` — from Anthropic console
4. Add a **Volume** for persistent holdings:
   - Service → **Settings** → **Volumes** → **+ New Volume**
   - Mount path: `/data`
5. Wait for the deploy to go green

### 5. Get your chat ID and enable the morning brief

1. Open Telegram, message your bot: `/start`
2. Send `/whoami` — it'll reply with your chat ID
3. Back in Railway → **Variables**, add:
   - `OWNER_CHAT_ID` — the number from `/whoami`
4. Railway will redeploy. Now the 8 AM brief is on.

Done. Try `/add AAPL 10` then `/brief` to test end-to-end.

## Commands

```
/holdings           Show portfolio + live values
/add SYMBOL SHARES  Add a holding
/remove SYMBOL      Remove a holding
/analyze SYMBOL     Full analysis (bull/bear/technicals)
/news SYMBOL        Recent headlines
/brief              Run morning brief now
/whoami             Your chat ID
/help               Show help
```

Anything not a command → free chat with Claude (auto-pulls data for any tickers it detects).

## Local dev (optional)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in tokens
export $(cat .env | xargs)
export HOLDINGS_FILE=./holdings.json  # local file, not /data
python main.py
```

## Configuration

All via env vars (see `.env.example`):

| Var | Default | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | required |
| `ANTHROPIC_API_KEY` | — | required |
| `OWNER_CHAT_ID` | — | set this to enable daily brief |
| `BRIEF_HOUR` | `8` | 24h, in `BRIEF_TIMEZONE` |
| `BRIEF_MINUTE` | `0` | |
| `BRIEF_TIMEZONE` | `Asia/Bangkok` | any IANA tz |
| `HOLDINGS_FILE` | `/data/holdings.json` | needs the Railway volume mounted at `/data` |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | |

## Cost expectations

- **Railway**: free tier covers this easily — the bot is mostly idle, ~$0/mo unless you hit the trial credits
- **Anthropic**: each `/analyze` or chat message ~$0.01–0.03; morning brief ~$0.05. If you brief 10 holdings daily + chat occasionally, expect $2–5/mo

## Architecture

```
main.py          → bot startup
bot/handlers.py  → /commands + free-text dispatcher
bot/analyzer.py  → Claude calls (system prompt, ticker detection)
bot/stocks.py    → yfinance wrappers, holdings JSON, RSI/SMA
bot/news.py      → yfinance news normalizer
bot/scheduler.py → daily JobQueue brief builder
```

## Notes

- This is **analysis, not advice.** The bot is prompted not to give personalized buy/sell verdicts and to close every response with a disclaimer. If you want it to be more opinionated, edit `SYSTEM` in `bot/analyzer.py` — but think hard before doing that.
- yfinance is unofficial / can break — if `/holdings` starts erroring across many symbols at once, that's the cause. Pin to a known-good version or swap to a paid data provider.
- The free Railway tier limits build minutes but not runtime for projects this small. If you outgrow it, $5/mo gets you plenty.

## Want LINE instead of Telegram?

The bot logic in `bot/` is platform-agnostic. To switch to LINE:
1. Replace `main.py` and `bot/handlers.py` with a `linebot` SDK webhook server (`linebot==3.x`).
2. Railway gives each service a public URL — register that as your LINE webhook.
3. LINE needs HTTPS + a verified channel from LINE Developers Console (more setup than Telegram). Worth it if you already live on LINE; otherwise stick with Telegram.
