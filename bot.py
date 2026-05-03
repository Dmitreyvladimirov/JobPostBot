import os
import re
import json
import time
import logging
import urllib.request
import urllib.parse
from datetime import date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
SCRAPINGBEE_API_KEY = os.environ["SCRAPINGBEE_API_KEY"]
NOTION_DATABASE_ID = "f71f92e0-c976-4cf2-bb56-8063b5cea681"

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
}

# Buffer for split messages: chat_id -> {"url": str, "text": str, "ts": float}
pending_jobs: dict = {}
FLUSH_AFTER = 3  # seconds to wait for a continuation message


def http_post(url: str, payload: dict, headers: dict = None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")[:15000]


def get_updates(offset: int, timeout: int = 30) -> list:
    params = urllib.parse.urlencode({"timeout": timeout, "offset": offset})
    req = urllib.request.Request(f"{TELEGRAM_API}/getUpdates?{params}")
    try:
        with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("result", [])
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        logger.error(f"Telegram getUpdates error {e.code}: {body}")
        raise


def send_message(chat_id: int, text: str) -> dict:
    return http_post(f"{TELEGRAM_API}/sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })


def edit_message(chat_id: int, message_id: int, text: str) -> dict:
    return http_post(f"{TELEGRAM_API}/editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })


def extract_url(text: str) -> str | None:
    match = re.search(r'https?://[^\s]+', text)
    return match.group(0) if match else None


def extract_body_text(text: str, url: str) -> str:
    """Return everything in the message except the URL itself."""
    return text.replace(url, "").strip()


def strip_html(html: str) -> str:
    text = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def fetch_page_content(url: str) -> str:
    params = urllib.parse.urlencode({
        "api_key": SCRAPINGBEE_API_KEY,
        "url": url,
        "render_js": "true",
    })
    return http_get(f"https://app.scrapingbee.com/api/v1/?{params}")


def extract_job_data(content: str) -> dict:
    if len(content.strip()) < 200:
        raise ValueError("Page content too short — ScrapingBee likely failed to load the page")

    prompt = f"""You are extracting job posting data. Analyze the following job posting content and return ONLY a valid JSON object with these exact fields:
- "position": job title/position name (string, or null if not found)
- "company_name": company name (string, or null if not found)
- "company_website": company's main website URL, NOT the job posting URL (string or null if not found)
- "description": clean plain-text job description (responsibilities, requirements, about the role). Strip all HTML, navigation, footers, ads. Return null if not found.

If the content does not look like a job posting, return: {{"position": null, "company_name": null, "company_website": null, "description": null}}
Return ONLY the JSON object, no explanation, no markdown, no backticks.

Job posting content:
{content}"""

    response = http_post(
        "https://api.openai.com/v1/chat/completions",
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0,
        },
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
    )
    raw = response["choices"][0]["message"]["content"].strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)


def make_text_blocks(text: str) -> list:
    """Split text into Notion paragraph blocks (max 2000 chars each)."""
    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
    return [
        {"object": "block", "type": "paragraph",
         "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}}
        for chunk in chunks
    ]


def create_notion_card(position: str, company_name: str, job_url: str,
                       company_website: str | None, description: str | None) -> str:
    today = date.today().isoformat()
    title = f"{position} ({company_name})" if company_name else position
    properties = {
        "Позиция": {"title": [{"text": {"content": title}}]},
        "Ссылка на вакансию": {"url": job_url},
        "Status2": {"select": {"name": "Applied"}},
        "Статус": {"select": {"name": "Активно"}},
        "Date Applied": {"date": {"start": today}},
        "Подался сам": {"checkbox": True},
    }
    if company_website:
        properties["сайт компании"] = {"url": company_website}

    payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties}
    if description:
        payload["children"] = make_text_blocks(description)

    response = http_post("https://api.notion.com/v1/pages", payload, headers=NOTION_HEADERS)
    return response["url"]


def _execute_job(chat_id: int, job: dict) -> None:
    """Process a buffered job (URL + accumulated text)."""
    url = job["url"]
    body_text = job["text"]

    status_msg = send_message(chat_id, "⏳ Processing...")
    message_id = status_msg["result"]["message_id"]

    step = "init"
    try:
        if body_text:
            # User provided the job description — skip ScrapingBee
            content = body_text
            description = body_text
        else:
            step = "ScrapingBee"
            edit_message(chat_id, message_id, "⏳ Fetching job posting (ScrapingBee)...")
            content = strip_html(fetch_page_content(url))
            description = content

        step = "OpenAI"
        edit_message(chat_id, message_id, "🤖 Extracting job data (OpenAI)...")
        job_data = extract_job_data(content)

        position = job_data.get("position")
        company_name = job_data.get("company_name")
        company_website = job_data.get("company_website")
        if not body_text:
            description = job_data.get("description") or description

        # Fallback: extract what we can from the URL if OpenAI couldn't find it
        if not position or not company_name:
            domain = re.search(r'https?://(?:www\.)?([^/]+)', url)
            domain_name = domain.group(1) if domain else url
            if not company_name:
                company_name = domain_name
            if not position:
                position = f"Job at {company_name}"
            description = body_text or description  # always save what the user sent
            logger.warning(f"Could not extract job data from content, using fallback: {position} / {company_name}")

        step = "Notion"
        edit_message(chat_id, message_id, "📝 Creating Notion card...")
        notion_url = create_notion_card(position, company_name, url, company_website, description)

        warning = "\n⚠️ _Couldn't auto-detect position/company — check the card_" if not job_data.get("position") or not job_data.get("company_name") else ""
        edit_message(chat_id, message_id,
            f"✅ Card created!\n\n"
            f"💼 *{position}*\n"
            f"🏢 {company_name}\n"
            f"📊 Status: Applied\n\n"
            f"[Open in Notion]({notion_url}){warning}"
        )
    except Exception as e:
        logger.error(f"Error at step [{step}]: {e}", exc_info=True)
        edit_message(chat_id, message_id, f"❌ Error at {step}: {str(e)}")


def process_message(message: dict) -> None:
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    url = extract_url(text)

    if url:
        # If a different job was pending for this chat, flush it immediately
        if chat_id in pending_jobs:
            _execute_job(chat_id, pending_jobs.pop(chat_id))

        body_text = extract_body_text(text, url)
        # Buffer this job — wait for a possible continuation (Telegram split message)
        pending_jobs[chat_id] = {"url": url, "text": body_text, "ts": time.time()}
        logger.info(f"Buffered job for chat {chat_id}, waiting {FLUSH_AFTER}s for continuation")
        return

    if chat_id in pending_jobs:
        # No URL → treat as continuation of the previous split message
        existing = pending_jobs[chat_id]["text"]
        pending_jobs[chat_id]["text"] = (existing + "\n" + text).strip()
        pending_jobs[chat_id]["ts"] = time.time()
        logger.info(f"Appended continuation for chat {chat_id}")
        return

    send_message(chat_id, "🔗 Send me a job posting URL and I'll create a card in Notion.")


def run_polling():
    logger.info("Bot started (polling mode) — send a job URL to your bot in Telegram")
    offset = 0
    while True:
        try:
            # Use short poll timeout when jobs are pending so we flush them quickly
            poll_timeout = FLUSH_AFTER if pending_jobs else 30
            updates = get_updates(offset, timeout=poll_timeout)
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if message:
                    process_message(message)

            # Flush pending jobs that haven't received a continuation within FLUSH_AFTER seconds
            now = time.time()
            to_flush = [
                cid for cid, job in list(pending_jobs.items())
                if now - job["ts"] >= FLUSH_AFTER
            ]
            for cid in to_flush:
                job = pending_jobs.pop(cid)
                logger.info(f"Flushing pending job for chat {cid}")
                _execute_job(cid, job)

        except Exception as e:
            logger.error(f"Polling error: {e}", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    # Wait for network to be available (important after reboot)
    for attempt in range(30):
        try:
            urllib.request.urlopen("https://api.telegram.org", timeout=5)
            break
        except Exception:
            logger.info(f"Waiting for network... ({attempt + 1}/30)")
            time.sleep(5)
    run_polling()
