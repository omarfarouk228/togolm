"""
Messaging bots (Telegram, WhatsApp): the channel-agnostic part.

In Togo people ask questions in messaging apps, not on websites. Each channel
module (telegram.py, whatsapp.py) turns its webhook payload into a call to
handle_text / handle_voice and sends back the replies, already formatted for
the channel. Answers come from the same pipeline as POST /v1/query.

Per user, in Redis: the answer language (/fr /ee /kbp /en), the last turns of
the conversation (follow-up questions keep their context) and a daily quota.
Everything is best-effort: Redis down means no history and no quota, never no
answer.
"""

import datetime
import html
import json
import logging
import os
import re
import time
from dataclasses import dataclass

import redis

from api.app.features.query.querylog import log_query
from api.app.features.query.schemas import HistoryMessage, QueryRequest

logger = logging.getLogger("togolm.bots")

DAILY_LIMIT = int(os.getenv("BOT_DAILY_LIMIT", "30"))
HISTORY_TURNS = 6  # messages kept (3 questions + 3 answers)
HISTORY_TTL_S = 24 * 3600
MAX_MESSAGE_CHARS = 3800  # Telegram and WhatsApp both cap a message at 4096
LANGUAGES = {"fr": "français", "ee": "éwé", "kbp": "kabiyè", "en": "english"}

WELCOME = (
    "Bonjour ! Je suis TogoLM, l'assistant qui répond à vos questions sur le Togo "
    "(démarches, lois, santé, éducation, économie, actualité) à partir de sources "
    "officielles.\n\n"
    "Posez votre question par écrit ou en message vocal.\n"
    "Langue des réponses : /fr français, /ee éwé, /kbp kabiyè, /en english.\n"
    "Nouvelle conversation : /nouveau. Aide : /aide."
)
LANGUAGE_SET = {
    "fr": "C'est noté, je réponds en français.",
    "ee": "C'est noté, je réponds en éwé (expérimental : signalez les erreurs sur togolm.com/contribute).",
    "kbp": "C'est noté, je réponds en kabiyè (expérimental : signalez les erreurs sur togolm.com/contribute).",
    "en": "Noted, I will answer in English.",
}
RESET = "Nouvelle conversation : je ne tiens plus compte des messages précédents."
QUOTA_REACHED = (
    "Vous avez atteint la limite de {n} questions pour aujourd'hui. Revenez demain, "
    "ou utilisez togolm.com."
)
FAILURE = "Désolé, je n'ai pas pu répondre pour le moment. Réessayez dans quelques minutes."
VOICE_FAILED = "Je n'ai pas compris ce message vocal. Pouvez-vous l'écrire ou le réenregistrer ?"
TOO_SHORT = "Pouvez-vous préciser votre question ?"

_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        _client = redis.from_url(url, decode_responses=True, socket_timeout=2)
    return _client


def _key(channel: str, user_id: str, name: str) -> str:
    return f"togolm:bot:{channel}:{user_id}:{name}"


def first_delivery(channel: str, message_id: str) -> bool:
    """False when this webhook delivery was already handled (channels retry)."""
    try:
        return bool(_redis().set(f"togolm:bot:{channel}:seen:{message_id}", 1, nx=True, ex=86400))
    except Exception:
        return True


def get_language(channel: str, user_id: str) -> str:
    try:
        return _redis().get(_key(channel, user_id, "lang")) or "fr"
    except Exception:
        return "fr"


def _set_language(channel: str, user_id: str, language: str) -> None:
    try:
        _redis().set(_key(channel, user_id, "lang"), language)
    except Exception:
        pass


def _history(channel: str, user_id: str) -> list[HistoryMessage]:
    try:
        raw = _redis().lrange(_key(channel, user_id, "history"), 0, -1)
        return [HistoryMessage(**json.loads(item)) for item in raw]
    except Exception:
        return []


def _remember(channel: str, user_id: str, question: str, answer: str) -> None:
    key = _key(channel, user_id, "history")
    try:
        pipe = _redis().pipeline()
        pipe.rpush(key, json.dumps({"role": "user", "content": question[:1000]}))
        pipe.rpush(key, json.dumps({"role": "assistant", "content": answer[:2000]}))
        pipe.ltrim(key, -HISTORY_TURNS, -1)
        pipe.expire(key, HISTORY_TTL_S)
        pipe.execute()
    except Exception:
        pass


def _reset(channel: str, user_id: str) -> None:
    try:
        _redis().delete(_key(channel, user_id, "history"))
    except Exception:
        pass


def _within_quota(channel: str, user_id: str) -> bool:
    key = _key(channel, user_id, f"day:{datetime.date.today().isoformat()}")
    try:
        pipe = _redis().pipeline()
        pipe.incr(key)
        pipe.expire(key, 2 * 86400)
        count = pipe.execute()[0]
    except Exception:
        return True
    return int(count) <= DAILY_LIMIT


# ── Formatting ───────────────────────────────────────────────────────────────


@dataclass
class Answer:
    text: str
    sources: list[dict]
    procedure: dict | None = None


def _procedure_block(card: dict, style: str) -> str:
    """Exact documents, cost and time of a procedure (rag.procedures)."""
    bold = (lambda t: f"<b>{t}</b>") if style == "html" else (lambda t: f"*{t}*")
    esc = html.escape if style == "html" else (lambda t: t)
    lines = [bold(f"📋 Fiche : {esc(card['title'])}")]
    if card.get("documents"):
        lines.append(bold("Pièces à fournir"))
        lines += [f"☐ {esc(d)[:300]}" for d in card["documents"][:10]]
    if card.get("cost"):
        lines.append(f"💰 {bold('Coût')} : {esc(card['cost'])[:300]}")
    if card.get("duration"):
        lines.append(f"⏱ {bold('Délai')} : {esc(card['duration'])[:300]}")
    if card.get("office"):
        lines.append(f"📍 {esc(card['office'])[:300]}")
    return "\n".join(lines)


def _split(text: str) -> list[str]:
    """Messages of at most MAX_MESSAGE_CHARS, cut between paragraphs."""
    parts, current = [], ""
    for paragraph in text.split("\n\n"):
        while len(paragraph) > MAX_MESSAGE_CHARS:
            parts.append(paragraph[:MAX_MESSAGE_CHARS])
            paragraph = paragraph[MAX_MESSAGE_CHARS:]
        if current and len(current) + len(paragraph) + 2 > MAX_MESSAGE_CHARS:
            parts.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        parts.append(current)
    return parts


def to_telegram_html(markdown: str) -> str:
    """The model's Markdown as the HTML subset Telegram renders."""
    text = html.escape(markdown, quote=False)
    text = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"^\s*[*-]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)
    return text


def to_whatsapp(markdown: str) -> str:
    """The model's Markdown as WhatsApp formatting (*bold*, _italic_)."""
    text = re.sub(r"^#{1,6}\s*(.+)$", r"*\1*", markdown, flags=re.MULTILINE)
    text = re.sub(r"^\s*[*-]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", text)
    return text


def render(answer: Answer, style: str) -> list[str]:
    """Messages to send for an answer: the text, then up to 3 sources."""
    body = to_telegram_html(answer.text) if style == "html" else to_whatsapp(answer.text)
    if answer.sources:
        lines = []
        for s in answer.sources[:3]:
            title = (s.get("title") or s.get("url") or "")[:90]
            if style == "html":
                lines.append(f'• <a href="{html.escape(s["url"])}">{html.escape(title)}</a>')
            else:
                lines.append(f"• {title}\n  {s['url']}")
        header = "<b>Sources</b>" if style == "html" else "*Sources*"
        body += f"\n\n{header}\n" + "\n".join(lines)
    if answer.procedure:
        body += "\n\n" + _procedure_block(answer.procedure, style)
    return _split(body)


# ── Handling ─────────────────────────────────────────────────────────────────


def _command(channel: str, user_id: str, text: str) -> str | None:
    word = text.strip().split()[0].lower().lstrip("/").split("@")[0] if text.strip() else ""
    if not text.strip().startswith("/"):
        return None
    if word in ("start", "aide", "help"):
        return WELCOME
    if word in LANGUAGES:
        _set_language(channel, user_id, word)
        return LANGUAGE_SET[word]
    if word in ("langue", "language"):
        parts = text.split()
        if len(parts) > 1 and parts[1].lower() in LANGUAGES:
            _set_language(channel, user_id, parts[1].lower())
            return LANGUAGE_SET[parts[1].lower()]
        return "Langues : /fr, /ee (éwé), /kbp (kabiyè), /en."
    if word in ("nouveau", "new", "reset"):
        _reset(channel, user_id)
        return RESET
    return WELCOME


def _ask(channel: str, user_id: str, question: str) -> Answer:
    from api.app.features.query.router import _display_sources, _procedure_for, _run_text_query

    language = get_language(channel, user_id)
    request = QueryRequest(question=question, language=language, history=_history(channel, user_id))
    t0 = time.monotonic()
    result = _run_text_query(request)
    log_query(
        question,
        language,
        result.search_category,
        result.is_off_topic,
        len(result.chunks),
        int((time.monotonic() - t0) * 1000),
        f"bot:{channel}",
    )
    _remember(channel, user_id, question, result.answer)
    sources = _display_sources(
        [{"title": c.title, "url": c.url, "score": round(c.score, 4)} for c in result.chunks]
    )
    return Answer(result.answer, [s for s in sources if s.get("url")], _procedure_for(sources))


def handle_text(channel: str, user_id: str, text: str, style: str) -> list[str]:
    """Replies (already formatted for the channel) to a text message."""
    reply = _command(channel, user_id, text)
    if reply is not None:
        return [to_telegram_html(reply) if style == "html" else to_whatsapp(reply)]
    if len(text.strip()) < 3:
        return [TOO_SHORT]
    if not _within_quota(channel, user_id):
        return [QUOTA_REACHED.format(n=DAILY_LIMIT)]
    try:
        return render(_ask(channel, user_id, text.strip()[:4000]), style)
    except Exception:
        logger.exception("Bot answer failed (%s)", channel)
        return [FAILURE]


def handle_voice(
    channel: str, user_id: str, mime_type: str, data_b64: str, style: str
) -> list[str]:
    """Transcribe a voice message (French, Éwé, Kabiyè), then answer it."""
    from rag.generation.audio import transcribe_audio

    language = get_language(channel, user_id)
    try:
        heard = transcribe_audio(mime_type, data_b64, language)
    except Exception:
        logger.exception("Bot voice transcription failed (%s)", channel)
        return [VOICE_FAILED]
    text = (heard.get("text") or "").strip()
    if len(text) < 3:
        return [VOICE_FAILED]
    quote = html.escape(text) if style == "html" else text
    echo = f"🎙️ <i>« {quote} »</i>" if style == "html" else f"🎙️ _« {quote} »_"
    return [echo, *handle_text(channel, user_id, text, style)]
