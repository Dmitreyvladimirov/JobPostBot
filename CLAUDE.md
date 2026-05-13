# JobPostBot → WorkSearch Bot

Unified Telegram bot for job search automation. Three modes: vacancy tracking, interview training, LinkedIn idea capture.

## Stack
- Pure Python stdlib (no pip packages)
- ScrapingBee — JS-rendered scraping
- OpenAI gpt-4o-mini — job data extraction
- OpenAI gpt-5.5-2026-04-23 — interview training sessions
- OpenAI Whisper — voice transcription
- Notion API — vacancy cards + training log
- Telegram Bot API — long polling

## Files
- `bot.py` — entire bot logic (~500 lines)
- `content/` — training content (cheatsheet, frameworks, english errors/vocab)
- `run.sh` — loads `.env` and runs `bot.py`
- `.env` — all secrets and config

## .env variables
```
TELEGRAM_TOKEN
OPENAI_API_KEY
NOTION_TOKEN
SCRAPINGBEE_API_KEY
NOTION_DATABASE_ID     # vacancies DB (hardcoded: f71f92e0-c976-4cf2-bb56-8063b5cea681)
NOTION_TRAINING_PAGE_ID  # training log page: 35f7a85b-5b20-814c-9c92-f68000dac72f
LINKEDIN_STRATEGY_PATH   # local path to strategy.md (not needed in cloud)
INTERVIEW_LOG_PATH       # local path to interview-log.md (not needed in cloud)
```

## Notion IDs
- Vacancies DB: `f71f92e0-c976-4cf2-bb56-8063b5cea681`
- Training Log page: `35f7a85b-5b20-814c-9c92-f68000dac72f`
- Product sense parent: `3507a85b-5b20-8013-ba49-e52004ea0748`

## Bot commands
- Job URL (+ optional pasted text) → Notion card + prep checklist
- `#post text` or `/idea text` → LinkedIn strategy.md backlog
- Voice note → Whisper transcription → LinkedIn backlog (or training answer if in session)
- `/train ps` — Product Sense interview session
- `/train vacancy` — Recruiter simulation from recent Notion vacancies
- `/train english` — PM English exercises
- `/stop` — End session, generate summary, save to Notion Training Log

## Notion vacancy card fields
Позиция (title), Ссылка на вакансию (url), сайт компании (url), Status2 (select), Статус (select), Date Applied (date), Подался сам (checkbox)
Extended (add manually to DB): Key Skills (multi-select), Domain (select), Interview Focus (select)

## Content sync
`content/` files are copies from `product-cases/`. After training sessions here in Claude Code:
1. Update source files in product-cases/notes/
2. Copy to content/ in this repo
3. Commit and push → Railway auto-redeploys

## Process management (local)
Bot runs via launchd: `~/Library/LaunchAgents/com.jobpostbot.plist`
To restart: `launchctl kickstart -k gui/$(id -u)/com.jobpostbot`
Do NOT start manually via `run.sh` — creates duplicate process.

## Known issues
- LinkedIn URLs blocked by ScrapingBee → paste job description text alongside URL
- Webhook conflict (409): `curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"` then restart
- Extended Notion props (Key Skills/Domain/Interview Focus) must be added manually to DB first
