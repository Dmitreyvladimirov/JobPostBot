import os
import re
import json
import time
import logging
import urllib.request
import urllib.parse
from datetime import date, datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
SCRAPINGBEE_API_KEY = os.environ["SCRAPINGBEE_API_KEY"]
NOTION_DATABASE_ID = "f71f92e0-c976-4cf2-bb56-8063b5cea681"
LINKEDIN_STRATEGY_PATH = os.environ.get(
    "LINKEDIN_STRATEGY_PATH",
    "/Users/DimaKu/Documents/Coding/LinkedIn posting/linkedin/strategy.md"
)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
}

# Buffer for split messages: chat_id -> {"url": str, "text": str, "ts": float}
pending_jobs: dict = {}
FLUSH_AFTER = 3  # seconds to wait for a continuation message

CASES_CONTEXT = (
    "Diagnose cases: Instagram, LinkedIn, Notion, Slack, Spotify, Uber\n"
    "Product deep dive: ChatGPT, Google Maps, Slack, Spotify, Uber, Wolt, YouTube\n"
    "Favorite product: Telegram\n"
    "Frameworks: diagnose, metrics, prioritization, question types"
)


def http_post(url: str, payload: dict, headers: dict = None, method: str = "POST") -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
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
- "company_website": company's main website URL, NOT the job posting URL (string or null)
- "description": clean plain-text job description (responsibilities, requirements, about the role). Strip all HTML, navigation, footers, ads. Return null if not found.
- "key_skills": list of up to 8 key required skills or technologies (array of strings, or empty array)
- "domain": primary business domain — one of: SaaS, FinTech, AI, EdTech, Marketplace, HealthTech, Other (string)
- "interview_focus": likely interview focus — one of: product-sense, execution, strategy, mixed (string)

If the content does not look like a job posting, return all fields as null or empty.
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


def generate_prep_checklist(job_data: dict) -> str:
    position = job_data.get("position") or "PM role"
    company = job_data.get("company_name") or "this company"
    domain = job_data.get("domain") or "tech"
    interview_focus = job_data.get("interview_focus") or "mixed"
    key_skills = ", ".join(job_data.get("key_skills") or []) or "not specified"

    prompt = f"""You are an interview prep advisor for a Product Manager candidate actively job hunting.

The candidate has these interview cases and frameworks ready:
{CASES_CONTEXT}

Job details:
- Position: {position} at {company}
- Domain: {domain}
- Interview focus likely: {interview_focus}
- Key skills required: {key_skills}

Write a concise interview prep checklist. Use this exact structure:

## Top 3 Cases to Review
1. [case name] — [one sentence: why it's the most relevant for this role]
2. [case name] — [one sentence why]
3. [case name] — [one sentence why]

## Company-Specific Practice Prompt
[One tailored practice question for this specific company/domain, e.g. "How would you diagnose a 15% drop in [their key metric]?"]

## Key Focus Areas
- [2-3 specific things to emphasize based on the job requirements]

## English Vocabulary to Prepare
- [3-5 PM terms or phrases specific to this domain or role type]

Be specific. Avoid generic advice."""

    response = http_post(
        "https://api.openai.com/v1/chat/completions",
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800,
            "temperature": 0.3,
        },
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
    )
    return response["choices"][0]["message"]["content"].strip()


def make_text_blocks(text: str) -> list:
    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
    return [
        {"object": "block", "type": "paragraph",
         "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}}
        for chunk in chunks
    ]


def make_heading_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}
    }


def make_divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def create_notion_card(position: str, company_name: str, job_url: str,
                       company_website: str | None, description: str | None,
                       prep_checklist: str | None = None) -> tuple[str, str]:
    """Returns (page_url, page_id)."""
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

    children = []
    if description:
        children.append(make_heading_block("Job Description"))
        children.extend(make_text_blocks(description))
    if prep_checklist:
        children.append(make_divider_block())
        children.append(make_heading_block("Interview Prep Checklist"))
        children.extend(make_text_blocks(prep_checklist))

    payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties}
    if children:
        payload["children"] = children

    response = http_post("https://api.notion.com/v1/pages", payload, headers=NOTION_HEADERS)
    return response["url"], response["id"]


def update_notion_extended_props(page_id: str, key_skills: list, domain: str, interview_focus: str) -> None:
    """Update card with extended properties. Fails gracefully if properties don't exist in DB yet."""
    properties = {}
    if key_skills:
        properties["Key Skills"] = {"multi_select": [{"name": s[:100]} for s in key_skills[:10]]}
    if domain:
        properties["Domain"] = {"select": {"name": domain}}
    if interview_focus:
        properties["Interview Focus"] = {"select": {"name": interview_focus}}

    if not properties:
        return

    try:
        http_post(
            f"https://api.notion.com/v1/pages/{page_id}",
            {"properties": properties},
            headers=NOTION_HEADERS,
            method="PATCH"
        )
    except Exception as e:
        logger.warning(f"Extended props not updated (add Key Skills/Domain/Interview Focus to Notion DB): {e}")


def get_telegram_file_bytes(file_id: str) -> tuple[bytes, str]:
    """Download a file from Telegram. Returns (bytes, filename)."""
    params = urllib.parse.urlencode({"file_id": file_id})
    req = urllib.request.Request(f"{TELEGRAM_API}/getFile?{params}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    file_path = data["result"]["file_path"]
    filename = file_path.split("/")[-1]

    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    req = urllib.request.Request(file_url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(), filename


def transcribe_voice(file_id: str) -> str:
    """Transcribe a Telegram voice/audio message via Whisper API."""
    audio_bytes, filename = get_telegram_file_bytes(file_id)

    boundary = f"----FormBoundary{int(time.time())}"
    crlf = b"\r\n"

    parts = [
        f"--{boundary}".encode() + crlf,
        b'Content-Disposition: form-data; name="model"' + crlf + crlf,
        b"whisper-1" + crlf,
        f"--{boundary}".encode() + crlf,
        f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode() + crlf,
        b"Content-Type: audio/ogg" + crlf + crlf,
        audio_bytes + crlf,
        f"--{boundary}--".encode() + crlf,
    ]

    body = b"".join(parts)
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        method="POST"
    )
    req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    return result["text"]


def append_post_idea(text: str, chat_id: int) -> None:
    """Append a LinkedIn post idea to strategy.md."""
    entry = f"\n\n- [ ] **{datetime.now().strftime('%Y-%m-%d')}** — {text}"
    try:
        with open(LINKEDIN_STRATEGY_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        preview = text[:200] + ("..." if len(text) > 200 else "")
        send_message(chat_id, f"💡 Saved to LinkedIn backlog:\n\n_{preview}_")
    except Exception as e:
        logger.error(f"Failed to save post idea: {e}")
        send_message(chat_id, f"❌ Couldn't save idea: {str(e)}")


def _execute_job(chat_id: int, job: dict) -> None:
    url = job["url"]
    body_text = job["text"]

    status_msg = send_message(chat_id, "⏳ Processing...")
    message_id = status_msg["result"]["message_id"]

    step = "init"
    try:
        if body_text:
            content = body_text
            description = body_text
        else:
            step = "ScrapingBee"
            edit_message(chat_id, message_id, "⏳ Fetching job posting...")
            content = strip_html(fetch_page_content(url))
            description = content

        step = "OpenAI"
        edit_message(chat_id, message_id, "🤖 Extracting job data...")
        job_data = extract_job_data(content)

        position = job_data.get("position")
        company_name = job_data.get("company_name")
        company_website = job_data.get("company_website")
        key_skills = job_data.get("key_skills") or []
        domain = job_data.get("domain") or ""
        interview_focus = job_data.get("interview_focus") or ""
        if not body_text:
            description = job_data.get("description") or description

        if not position or not company_name:
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            domain_name = domain_match.group(1) if domain_match else url
            if not company_name:
                company_name = domain_name
            if not position:
                position = f"Job at {company_name}"
            description = body_text or description
            logger.warning(f"Fallback extraction: {position} / {company_name}")

        step = "PrepChecklist"
        edit_message(chat_id, message_id, "📚 Generating interview prep checklist...")
        prep_checklist = generate_prep_checklist(job_data)

        step = "Notion"
        edit_message(chat_id, message_id, "📝 Creating Notion card...")
        notion_url, page_id = create_notion_card(
            position, company_name, url, company_website, description, prep_checklist
        )
        update_notion_extended_props(page_id, key_skills, domain, interview_focus)

        skills_line = f"\n🏷 _{', '.join(key_skills[:5])}_" if key_skills else ""
        warning = "\n⚠️ _Couldn't auto-detect position/company_" if not job_data.get("position") else ""
        edit_message(chat_id, message_id,
            f"✅ Card created!\n\n"
            f"💼 *{position}*\n"
            f"🏢 {company_name}{' · ' + domain if domain else ''}\n"
            f"🎯 Focus: {interview_focus or 'mixed'}{skills_line}\n\n"
            f"[Open in Notion]({notion_url}){warning}"
        )
    except Exception as e:
        logger.error(f"Error at step [{step}]: {e}", exc_info=True)
        edit_message(chat_id, message_id, f"❌ Error at {step}: {str(e)}")


def process_message(message: dict) -> None:
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    # Voice / audio → transcribe and save as post idea
    voice = message.get("voice") or message.get("audio")
    if voice:
        status_msg = send_message(chat_id, "🎙️ Transcribing...")
        message_id = status_msg["result"]["message_id"]
        try:
            transcribed = transcribe_voice(voice["file_id"])
            edit_message(chat_id, message_id, f"🎙️ _{transcribed[:300]}_\n\nSaving to LinkedIn backlog...")
            append_post_idea(transcribed, chat_id)
        except Exception as e:
            logger.error(f"Voice transcription error: {e}", exc_info=True)
            edit_message(chat_id, message_id, f"❌ Transcription failed: {str(e)}")
        return

    # Post idea capture
    if text.startswith("#post") or text.startswith("/idea"):
        idea = re.sub(r'^(#post|/idea)\s*', '', text).strip()
        if idea:
            append_post_idea(idea, chat_id)
        else:
            send_message(chat_id, "💡 Send your idea after `#post` or `/idea`\nExample: `#post Why AI won't replace PMs`")
        return

    url = extract_url(text)

    if url:
        if chat_id in pending_jobs:
            _execute_job(chat_id, pending_jobs.pop(chat_id))
        body_text = extract_body_text(text, url)
        pending_jobs[chat_id] = {"url": url, "text": body_text, "ts": time.time()}
        logger.info(f"Buffered job for chat {chat_id}")
        return

    if chat_id in pending_jobs:
        existing = pending_jobs[chat_id]["text"]
        pending_jobs[chat_id]["text"] = (existing + "\n" + text).strip()
        pending_jobs[chat_id]["ts"] = time.time()
        logger.info(f"Appended continuation for chat {chat_id}")
        return

    send_message(chat_id, (
        "👋 What I can do:\n\n"
        "🔗 *Job URL* → Notion card + interview prep checklist\n"
        "💡 `#post your idea` → LinkedIn backlog\n"
        "🎙️ *Voice note* → transcribe and save as post idea"
    ))


def run_polling():
    logger.info("Bot started — send a job URL, #post idea, or voice note")
    offset = 0
    while True:
        try:
            poll_timeout = FLUSH_AFTER if pending_jobs else 30
            updates = get_updates(offset, timeout=poll_timeout)
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if message:
                    process_message(message)

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
    for attempt in range(30):
        try:
            urllib.request.urlopen("https://api.telegram.org", timeout=5)
            break
        except Exception:
            logger.info(f"Waiting for network... ({attempt + 1}/30)")
            time.sleep(5)
    run_polling()
