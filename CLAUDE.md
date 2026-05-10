# JobPostBot

Telegram bot for tracking job applications. Send a job posting URL → bot scrapes the page, extracts data via OpenAI, creates a Notion card with status "Applied".

## Stack
- Pure Python stdlib (no pip packages)
- ScrapingBee — JS-rendered scraping
- OpenAI gpt-4o-mini — job data extraction
- Notion API — card creation
- Telegram Bot API — long polling

## Files
- `bot.py` — entire bot logic (~300 lines)
- `run.sh` — loads `.env` and runs `bot.py`
- `.env` — TELEGRAM_TOKEN, OPENAI_API_KEY, NOTION_TOKEN, SCRAPINGBEE_API_KEY

## Notion database
ID: `f71f92e0-c976-4cf2-bb56-8063b5cea681`
Fields: Позиция (title), Ссылка на вакансию (url), сайт компании (url), Status2 (select → "Applied"), Статус (select → "Активно"), Date Applied (date), Подался сам (checkbox)

## How it works
1. User sends a URL (optionally with description text)
2. Bot buffers 3s for Telegram split messages
3. If no body text → fetches page via ScrapingBee, strips HTML
4. Sends content to OpenAI to extract: position, company_name, company_website, description
5. Creates Notion card, replies with link

## Process management
Bot runs via launchd: `~/Library/LaunchAgents/com.jobpostbot.plist` (KeepAlive=true, starts on login).
To restart: `launchctl kickstart -k gui/$(id -u)/com.jobpostbot`
Do NOT start manually via `run.sh` — launchd will create a second conflicting process.

## Known issues / gotchas
- **Webhook conflict (409)**: run `curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"` then restart via launchctl
- Description is split into 2000-char Notion blocks
- Fallback: if OpenAI can't parse the job, uses domain as company name
