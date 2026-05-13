import os
import re
import json
import time
import logging
import threading
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
INTERVIEW_LOG_PATH = os.environ.get(
    "INTERVIEW_LOG_PATH",
    "/Users/DimaKu/Documents/Coding/product-cases/notes/interview-log.md"
)
NOTION_TRAINING_PAGE_ID = os.environ.get("NOTION_TRAINING_PAGE_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

OPENAI_MODEL_EXTRACT = "gpt-4o-mini"
OPENAI_MODEL_TRAINING = "gpt-5.5"

AVAILABLE_MODELS = [
    ("gpt-4o",                    "openai",    "OpenAI · fast"),
    ("gpt-5.5",                   "openai",    "OpenAI · flagship"),
    ("claude-haiku-4-5-20251001", "anthropic", "Anthropic · fast & cheap"),
    ("claude-sonnet-4-6",         "anthropic", "Anthropic · balanced"),
    ("claude-opus-4-7",           "anthropic", "Anthropic · most capable"),
]

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
}

# Buffer for split messages: chat_id -> {"url": str, "text": str, "ts": float}
pending_jobs: dict = {}
FLUSH_AFTER = 3

# Training session state: chat_id -> session dict
active_sessions: dict = {}
# Pending vacancy selection: chat_id -> list of vacancy dicts
pending_vacancy_picks: dict = {}
# Per-user model choice: chat_id -> (model_name, provider)
session_models: dict = {}
# Waiting for model number pick
pending_model_pick: set = set()

CASES_CONTEXT = (
    "Diagnose cases: Instagram, LinkedIn, Notion, Slack, Spotify, Uber\n"
    "Product deep dive: ChatGPT, Google Maps, Slack, Spotify, Uber, Wolt, YouTube\n"
    "Favorite product: Telegram\n"
    "Frameworks: diagnose, metrics, prioritization, question types"
)


# ── Utilities ────────────────────────────────────────────────────────────────

def http_post(url: str, payload: dict, headers: dict = None, method: str = "POST") -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code} from {url.split('/')[2]}: {body[:600]}") from e


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


# ── Job Processing ────────────────────────────────────────────────────────────

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

    prompt = f"""You are extracting job posting data. Return ONLY a valid JSON object with these fields:
- "position": job title (string or null)
- "company_name": company name (string or null)
- "company_website": company main website URL, NOT the job posting URL (string or null)
- "description": clean plain-text job description, strip HTML/navigation/ads (string or null)
- "key_skills": up to 8 key required skills or technologies (array of strings)
- "domain": one of: SaaS, FinTech, AI, EdTech, Marketplace, HealthTech, Other (string)
- "interview_focus": one of: product-sense, execution, strategy, mixed (string)

If not a job posting, return all fields as null or empty. No markdown, no backticks.

Content:
{content}"""

    response = http_post(
        "https://api.openai.com/v1/chat/completions",
        {
            "model": OPENAI_MODEL_EXTRACT,
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

    prompt = f"""You are an interview prep advisor for a Product Manager candidate.

Candidate's available cases:
{CASES_CONTEXT}

Job: {position} at {company} | Domain: {domain} | Focus: {interview_focus} | Skills: {key_skills}

Write a concise prep checklist using this structure exactly:

## Top 3 Cases to Review
1. [case name] — [one sentence: why relevant for this role]
2. [case name] — [one sentence why]
3. [case name] — [one sentence why]

## Company-Specific Practice Prompt
[One tailored practice question for this company/domain]

## Key Focus Areas
- [2-3 things to emphasize based on requirements]

## English Vocabulary to Prepare
- [3-5 PM terms specific to this domain]

Be specific. No generic advice."""

    response = http_post(
        "https://api.openai.com/v1/chat/completions",
        {
            "model": OPENAI_MODEL_EXTRACT,
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
        "object": "block", "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}
    }


def make_divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def create_notion_card(position: str, company_name: str, job_url: str,
                       company_website: str | None, description: str | None,
                       prep_checklist: str | None = None) -> tuple[str, str]:
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
        logger.warning(f"Extended props not updated (add Key Skills/Domain/Interview Focus to DB): {e}")


# ── Voice & Ideas ─────────────────────────────────────────────────────────────

def get_telegram_file_bytes(file_id: str) -> tuple[bytes, str]:
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
    req = urllib.request.Request("https://api.openai.com/v1/audio/transcriptions", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())["text"]


def append_post_idea(text: str, chat_id: int) -> None:
    entry = f"\n\n- [ ] **{datetime.now().strftime('%Y-%m-%d')}** — {text}"
    try:
        with open(LINKEDIN_STRATEGY_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        preview = text[:200] + ("..." if len(text) > 200 else "")
        send_message(chat_id, f"💡 Saved to LinkedIn backlog:\n\n_{preview}_")
    except Exception as e:
        logger.error(f"Failed to save post idea: {e}")
        send_message(chat_id, f"❌ Couldn't save idea: {str(e)}")


# ── Training Module ───────────────────────────────────────────────────────────

def _run_with_keepalive(chat_id: int, message_id: int, fn):
    """Run fn() in the current thread while a background thread updates the message every 20s."""
    stop = threading.Event()
    hints = ["💭 Still thinking...", "💭 Almost there...", "💭 Generating response..."]

    def _updater():
        i = 0
        while not stop.wait(20):
            try:
                edit_message(chat_id, message_id, hints[i % len(hints)])
                i += 1
            except Exception:
                pass

    t = threading.Thread(target=_updater, daemon=True)
    t.start()
    try:
        return fn()
    finally:
        stop.set()

def load_content(filename: str) -> str:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", filename)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Content file not found: {path}")
        return ""


def _openai_completion(messages: list, model: str) -> str:
    data = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 1200,
        "temperature": 0.7,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=data, method="POST"
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI {e.code}: {body[:500]}") from e


def _anthropic_completion(messages: list, model: str) -> str:
    system = ""
    filtered = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            filtered.append(m)

    payload = {"model": model, "max_tokens": 1200, "messages": filtered}
    if system:
        payload["system"] = system

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data, method="POST"
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", ANTHROPIC_API_KEY)
    req.add_header("anthropic-version", "2023-06-01")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Anthropic {e.code}: {body[:500]}") from e


def chat_completion(messages: list, chat_id: int = 0) -> str:
    model, provider = session_models.get(chat_id, (OPENAI_MODEL_TRAINING, "openai"))
    if provider == "anthropic":
        return _anthropic_completion(messages, model)
    return _openai_completion(messages, model)


def handle_model_command(chat_id: int) -> None:
    current_model, _ = session_models.get(chat_id, (OPENAI_MODEL_TRAINING, "openai"))
    lines = [f"🤖 *Current model:* `{current_model}`\n\n*Switch to:*\n"]
    for i, (model_id, _, label) in enumerate(AVAILABLE_MODELS, 1):
        marker = "✅ " if model_id == current_model else ""
        lines.append(f"{i}. {marker}`{model_id}` — {label}")
    lines.append("\nReply with a number to switch.")
    send_message(chat_id, "\n".join(lines))
    pending_model_pick.add(chat_id)


def build_ps_system_prompt() -> str:
    return f"""You are a senior PM interviewer at a top tech company conducting a product sense interview.

Each turn:
1. Ask ONE product sense question (rotate types: diagnose, improve retention/engagement, favorite product, 0→1, strategy)
2. After the candidate answers, give structured feedback
3. Then ask the next question

Feedback format:
✅ What worked: [specific, reference the framework]
❌ What was missing: [what a senior PM would add]
📊 Score: Structure X/5 | Depth X/5 | Product Thinking X/5 | Communication X/5

Use these as your evaluation standard:

{load_content("cheatsheet.md")}

---

{load_content("frameworks.md")}

---

Be a tough but fair interviewer. Push back on generic answers. Start with one question now."""


def build_english_system_prompt() -> str:
    return f"""You are an English coach for a Russian-speaking Product Manager preparing for interviews.

The candidate's known error patterns:
{load_content("english-errors.md")}

Key PM vocabulary to reinforce:
{load_content("english-vocab.md")}

Each turn, give ONE exercise (rotate types):
1. PM concept or sentence in Russian → candidate translates to English
2. Weak or incorrect PM phrase → candidate improves it
3. Scenario → candidate uses a specific target word correctly

Feedback format:
✅ Correct: [what they got right]
❌ Error: [what was wrong, reference error log if it matches a known pattern]
💡 Better: [the ideal version]

One exercise at a time. Start now."""


def handle_train_command(chat_id: int, args: str) -> None:
    if chat_id in active_sessions:
        send_message(chat_id, "⚠️ You're already in a session. Use /stop to end it first.")
        return

    args = args.strip().lower()

    if args in ("ps", "product-sense", "productsense"):
        start_ps_session(chat_id)
    elif args in ("english", "en"):
        start_english_session(chat_id)
    elif args in ("vacancy", "v", "vac"):
        fetch_and_show_vacancies(chat_id)
    else:
        send_message(chat_id, (
            "🎯 *Choose training type:*\n\n"
            "➤ /train ps — Product Sense interview\n"
            "➤ /train vacancy — Prep for a specific vacancy\n"
            "➤ /train english — English practice\n\n"
            "Use /stop to end any session."
        ))


def _start_session_with_prompt(chat_id: int, session_type: str, system_prompt: str,
                                opener: str, extra: dict = None) -> None:
    """Shared session start logic."""
    active_sessions[chat_id] = {
        "type": session_type,
        "system": system_prompt,
        "history": [],
        "start_time": time.time(),
        "question_count": 0,
        **(extra or {}),
    }
    status_msg = send_message(chat_id, "⏳ Loading session...")
    message_id = status_msg["result"]["message_id"]
    try:
        first_msg = _run_with_keepalive(chat_id, message_id, lambda: chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": opener},
        ], chat_id=chat_id))
        active_sessions[chat_id]["history"].append({"role": "assistant", "content": first_msg})
        active_sessions[chat_id]["question_count"] = 1
        edit_message(chat_id, message_id, first_msg)
    except Exception as e:
        logger.error(f"Failed to start {session_type} session: {e}")
        del active_sessions[chat_id]
        edit_message(chat_id, message_id, f"❌ Couldn't start session: {e}")


def start_ps_session(chat_id: int) -> None:
    _start_session_with_prompt(
        chat_id, "product-sense",
        build_ps_system_prompt(),
        "Start the interview. Ask me the first question."
    )


def start_english_session(chat_id: int) -> None:
    _start_session_with_prompt(
        chat_id, "english",
        build_english_system_prompt(),
        "Start the session. Give me the first exercise."
    )


def fetch_and_show_vacancies(chat_id: int) -> None:
    status_msg = send_message(chat_id, "📋 Fetching recent vacancies...")
    message_id = status_msg["result"]["message_id"]
    try:
        response = http_post(
            f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query",
            {"sorts": [{"property": "Date Applied", "direction": "descending"}], "page_size": 5},
            headers=NOTION_HEADERS
        )
        pages = response.get("results", [])
        if not pages:
            edit_message(chat_id, message_id, "No vacancies found. Send a job URL first!")
            return

        vacancies = []
        for page in pages:
            props = page.get("properties", {})
            title_parts = props.get("Позиция", {}).get("title", [])
            title = title_parts[0]["text"]["content"] if title_parts else "Unknown"
            date_prop = props.get("Date Applied", {}).get("date") or {}
            date_str = date_prop.get("start", "")[:10]
            domain_prop = props.get("Domain", {}).get("select") or {}
            domain = domain_prop.get("name", "")
            vacancies.append({"id": page["id"], "title": title, "date": date_str, "domain": domain})

        pending_vacancy_picks[chat_id] = vacancies
        lines = ["📋 *Recent vacancies:*\n"]
        for i, v in enumerate(vacancies, 1):
            meta = f" · {v['domain']}" if v["domain"] else ""
            lines.append(f"{i}. {v['title']}{meta} _{v['date']}_")
        lines.append("\nReply with a number (1–5) to start prep.")
        edit_message(chat_id, message_id, "\n".join(lines))
    except Exception as e:
        logger.error(f"Failed to fetch vacancies: {e}")
        edit_message(chat_id, message_id, f"❌ Couldn't fetch vacancies: {e}")


def start_vacancy_session(chat_id: int, vacancy: dict) -> None:
    system_prompt = f"""You are an experienced recruiter conducting a screening call.

Position: {vacancy['title']}{' (' + vacancy['domain'] + ')' if vacancy.get('domain') else ''}

Your job:
1. Simulate a realistic recruiter call — start with a natural opener ("Tell me about yourself" adapted to this role)
2. Ask follow-up questions based on the candidate's answers
3. After each answer, add a brief coach note: what landed well and what to sharpen

On /stop, give full coaching summary:
- What came across well
- What needs sharper framing
- 3 specific phrases to use or avoid in the real interview

Keep it conversational. Be encouraging but realistic."""

    _start_session_with_prompt(
        chat_id, "vacancy",
        system_prompt,
        "Start the interview.",
        extra={"vacancy": vacancy}
    )


def handle_training_message(chat_id: int, text: str) -> None:
    session = active_sessions[chat_id]
    session["history"].append({"role": "user", "content": text})
    session["question_count"] += 1

    status_msg = send_message(chat_id, "💭 Thinking...")
    message_id = status_msg["result"]["message_id"]
    try:
        messages = [{"role": "system", "content": session["system"]}] + session["history"]
        reply = _run_with_keepalive(chat_id, message_id, lambda: chat_completion(messages, chat_id=chat_id))
        session["history"].append({"role": "assistant", "content": reply})
        edit_message(chat_id, message_id, reply)
    except Exception as e:
        logger.error(f"Training message error: {e}")
        edit_message(chat_id, message_id, f"❌ Error: {e}")


def end_session(chat_id: int) -> None:
    session = active_sessions.pop(chat_id, None)
    if not session:
        send_message(chat_id, "No active session.")
        return

    status_msg = send_message(chat_id, "📊 Generating summary...")
    message_id = status_msg["result"]["message_id"]
    try:
        duration_min = max(1, int((time.time() - session["start_time"]) / 60))
        summary_request = (
            f"The session just ended ({duration_min} min, {session['question_count']} exchanges).\n\n"
            "Generate a session summary:\n\n"
            "## Session Summary\n\n"
            "### What went well\n[2-3 specific observations]\n\n"
            "### Main areas to improve\n[2-3 specific points with examples from this session]\n\n"
            "### Scores\n"
            "- Structure: X/5\n- Depth/Accuracy: X/5\n- Communication/English: X/5\n- Overall: X/5\n\n"
            "### Top 3 things to practice before next session\n1. \n2. \n3. \n\n"
            "Be specific. Reference actual exchanges."
        )
        messages = (
            [{"role": "system", "content": session["system"]}]
            + session["history"]
            + [{"role": "user", "content": summary_request}]
        )
        summary = _run_with_keepalive(chat_id, message_id, lambda: chat_completion(messages, chat_id=chat_id))

        _save_session_locally(session, summary, duration_min)
        notion_url = _save_session_to_notion(session, summary, duration_min)
        notion_link = f"\n\n[View in Notion]({notion_url})" if notion_url else ""

        edit_message(chat_id, message_id, summary + notion_link)
    except Exception as e:
        logger.error(f"Failed to end session: {e}")
        edit_message(chat_id, message_id, f"❌ Couldn't generate summary: {e}")


def _save_session_locally(session: dict, summary: str, duration_min: int) -> None:
    try:
        if not os.path.exists(INTERVIEW_LOG_PATH):
            return
        session_type = session["type"]
        vacancy_title = session.get("vacancy", {}).get("title", "")
        header = f"\n\n---\n\n## {datetime.now().strftime('%Y-%m-%d')} — {session_type.title()} ({duration_min} min)"
        if vacancy_title:
            header += f" — {vacancy_title}"
        with open(INTERVIEW_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(header + "\n\n" + summary)
    except Exception as e:
        logger.warning(f"Could not save session locally: {e}")


def _save_session_to_notion(session: dict, summary: str, duration_min: int) -> str | None:
    if not NOTION_TRAINING_PAGE_ID:
        return None
    try:
        session_type = session["type"]
        vacancy_title = session.get("vacancy", {}).get("title", "")
        title = f"{datetime.now().strftime('%Y-%m-%d')} — {session_type.title()} ({duration_min} min)"
        if vacancy_title:
            title += f" — {vacancy_title}"
        payload = {
            "parent": {"page_id": NOTION_TRAINING_PAGE_ID},
            "properties": {"title": {"title": [{"text": {"content": title}}]}},
            "children": make_text_blocks(summary),
        }
        response = http_post("https://api.notion.com/v1/pages", payload, headers=NOTION_HEADERS)
        return response.get("url")
    except Exception as e:
        logger.warning(f"Could not save session to Notion: {e}")
        return None


# ── Job Execution ─────────────────────────────────────────────────────────────

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
            company_name = company_name or domain_name
            position = position or f"Job at {company_name}"
            description = body_text or description
            logger.warning(f"Fallback: {position} / {company_name}")

        step = "PrepChecklist"
        edit_message(chat_id, message_id, "📚 Generating prep checklist...")
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


# ── Message Routing ───────────────────────────────────────────────────────────

def process_message(message: dict) -> None:
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    # Voice / audio
    voice = message.get("voice") or message.get("audio")
    if voice:
        status_msg = send_message(chat_id, "🎙️ Transcribing...")
        message_id = status_msg["result"]["message_id"]
        try:
            transcribed = transcribe_voice(voice["file_id"])
            if chat_id in active_sessions:
                edit_message(chat_id, message_id, f"🎙️ _{transcribed[:200]}_")
                handle_training_message(chat_id, transcribed)
            else:
                edit_message(chat_id, message_id, f"🎙️ _{transcribed[:300]}_\n\nSaving to LinkedIn backlog...")
                append_post_idea(transcribed, chat_id)
        except Exception as e:
            logger.error(f"Voice error: {e}", exc_info=True)
            edit_message(chat_id, message_id, f"❌ Transcription failed: {e}")
        return

    # /stop
    if text.strip() == "/stop":
        end_session(chat_id)
        return

    # /model
    if text.strip() == "/model":
        handle_model_command(chat_id)
        return

    # Model number pick
    if chat_id in pending_model_pick and text.strip().isdigit():
        idx = int(text.strip()) - 1
        if 0 <= idx < len(AVAILABLE_MODELS):
            model_id, provider, label = AVAILABLE_MODELS[idx]
            session_models[chat_id] = (model_id, provider)
            pending_model_pick.discard(chat_id)
            send_message(chat_id, f"✅ Model switched to `{model_id}` ({label})")
        else:
            send_message(chat_id, f"Pick a number between 1 and {len(AVAILABLE_MODELS)}.")
        return

    # /train
    if text.startswith("/train"):
        handle_train_command(chat_id, text[len("/train"):])
        return

    # Active training session — route all messages there
    if chat_id in active_sessions:
        handle_training_message(chat_id, text)
        return

    # Vacancy selection from numbered list
    if chat_id in pending_vacancy_picks and text.strip().isdigit():
        idx = int(text.strip()) - 1
        vacancies = pending_vacancy_picks.pop(chat_id)
        if 0 <= idx < len(vacancies):
            start_vacancy_session(chat_id, vacancies[idx])
        else:
            send_message(chat_id, f"Pick a number between 1 and {len(vacancies)}.")
        return

    # Post idea capture
    if text.startswith("#post") or text.startswith("/idea"):
        idea = re.sub(r'^(#post|/idea)\s*', '', text).strip()
        if idea:
            append_post_idea(idea, chat_id)
        else:
            send_message(chat_id, "💡 Send your idea after `#post` or `/idea`")
        return

    # Job URL
    url = extract_url(text)
    if url:
        if chat_id in pending_jobs:
            _execute_job(chat_id, pending_jobs.pop(chat_id))
        body_text = extract_body_text(text, url)
        pending_jobs[chat_id] = {"url": url, "text": body_text, "ts": time.time()}
        return

    if chat_id in pending_jobs:
        existing = pending_jobs[chat_id]["text"]
        pending_jobs[chat_id]["text"] = (existing + "\n" + text).strip()
        pending_jobs[chat_id]["ts"] = time.time()
        return

    send_message(chat_id, (
        "👋 *What I can do:*\n\n"
        "🔗 Job URL → Notion card + prep checklist\n"
        "💡 `#post idea` → LinkedIn backlog\n"
        "🎙️ Voice note → transcribe + save\n\n"
        "🎯 *Training:*\n"
        "/train ps — Product Sense interview\n"
        "/train vacancy — Prep for specific vacancy\n"
        "/train english — English practice\n"
        "/stop — End current session\n"
        "/model — Switch AI model"
    ))


# ── Polling ───────────────────────────────────────────────────────────────────

def register_commands() -> None:
    commands = [
        {"command": "train",   "description": "Start training: /train ps | vacancy | english"},
        {"command": "stop",    "description": "End current training session + get summary"},
        {"command": "model",   "description": "Switch AI model (OpenAI / Anthropic)"},
        {"command": "idea",    "description": "Save a LinkedIn post idea"},
    ]
    try:
        http_post(f"{TELEGRAM_API}/setMyCommands", {"commands": commands})
        logger.info("Bot commands registered")
    except Exception as e:
        logger.warning(f"Could not register commands: {e}")


def run_polling():
    register_commands()
    logger.info("Bot started")
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
            for cid in [c for c, j in list(pending_jobs.items()) if now - j["ts"] >= FLUSH_AFTER]:
                _execute_job(cid, pending_jobs.pop(cid))

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
