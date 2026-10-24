"""
Alerts: a daily digest of the new documents matching a search.

A subscription is a few words (and optionally a category) plus where to send
the matches: an e-mail address, confirmed through a link first (double
opt-in), or a Telegram / WhatsApp chat. corpus.tasks.send_alert_digests runs
send_digests() every morning after the news crawl.
"""

import datetime
import html
import logging
import os
import secrets

from db import get_conn

logger = logging.getLogger("togolm.alerts")

MAX_PER_TARGET = 10
MAX_DOCS_PER_DIGEST = 10
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "https://api.togolm.com").rstrip("/")


class AlertError(ValueError):
    pass


def create(channel: str, target: str, query: str, category: str | None = None) -> dict:
    """New subscription; e-mail ones wait for confirmation."""
    query = " ".join(query.split())[:200]
    if len(query) < 3:
        raise AlertError("query too short")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM alert_subscriptions "
                "WHERE channel = %s AND target = %s AND active",
                (channel, target),
            )
            if cur.fetchone()[0] >= MAX_PER_TARGET:
                raise AlertError("too many alerts")
            token = secrets.token_urlsafe(24)
            cur.execute(
                """
                INSERT INTO alert_subscriptions (channel, target, query, category, token, confirmed)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id::text
                """,
                (channel, target, query, category, token, channel != "email"),
            )
            sub_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return {"id": sub_id, "token": token, "query": query, "confirmed": channel != "email"}


def _update(sql: str, token: str) -> bool:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (token,))
            found = cur.rowcount > 0
        conn.commit()
        return found
    finally:
        conn.close()


def confirm(token: str) -> bool:
    return _update(
        "UPDATE alert_subscriptions SET confirmed = TRUE WHERE token = %s AND active", token
    )


def unsubscribe(token: str) -> bool:
    return _update("UPDATE alert_subscriptions SET active = FALSE WHERE token = %s", token)


def list_for(channel: str, target: str) -> list[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT query, category FROM alert_subscriptions "
                "WHERE channel = %s AND target = %s AND active ORDER BY created_at",
                (channel, target),
            )
            return [{"query": q, "category": c} for q, c in cur.fetchall()]
    finally:
        conn.close()


def stop_all(channel: str, target: str) -> int:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alert_subscriptions SET active = FALSE "
                "WHERE channel = %s AND target = %s AND active",
                (channel, target),
            )
            count = cur.rowcount
        conn.commit()
        return count
    finally:
        conn.close()


def matches(cur, query: str, category: str | None, since: datetime.datetime) -> list[dict]:
    """New French documents matching all the words of `query` since `since`."""
    sql = """
        SELECT title, url, source, published_at
        FROM documents
        WHERE status = 'active' AND language = 'fr'
          AND collected_at > %s
          AND fts_vector @@ websearch_to_tsquery('french', %s)
    """
    params: list = [since, query]
    if category:
        sql += " AND %s IN (category, subcategory)"
        params.append(category)
    sql += " ORDER BY collected_at DESC LIMIT %s"
    params.append(MAX_DOCS_PER_DIGEST)
    cur.execute(sql, params)
    return [
        {"title": t or u, "url": u, "source": s, "published_at": p.isoformat() if p else None}
        for t, u, s, p in cur.fetchall()
    ]


def digest(sub: dict, docs: list[dict], style: str) -> str:
    """Digest message: 'text' (e-mail body), 'html' (Telegram) or 'whatsapp'."""
    count = (
        f"{len(docs)} nouveau{'x' if len(docs) > 1 else ''} document{'s' if len(docs) > 1 else ''}"
    )
    if style == "html":
        lines = [f"🔔 <b>Alerte « {html.escape(sub['query'])} »</b> : {count}"]
        lines += [
            f'• <a href="{html.escape(d["url"])}">{html.escape(d["title"][:120])}</a> ({d["source"]})'
            for d in docs
        ]
        lines.append("\nArrêter les alertes : /stopalertes")
    else:
        bold = "*" if style == "whatsapp" else ""
        lines = [f"🔔 {bold}Alerte « {sub['query']} »{bold} : {count}"]
        lines += [f"• {d['title'][:120]} ({d['source']})\n  {d['url']}" for d in docs]
        if style == "whatsapp":
            lines.append("\nArrêter les alertes : /stopalertes")
        else:
            lines.append(
                f"\nSe désabonner : {PUBLIC_API_URL}/v1/alerts/unsubscribe?token={sub['token']}"
            )
    return "\n".join(lines)


def _deliver(sub: dict, docs: list[dict]) -> None:
    if sub["channel"] == "telegram":
        from api.app.features.bots.telegram import send

        send(int(sub["target"]), [digest(sub, docs, "html")])
    elif sub["channel"] == "whatsapp":
        from api.app.features.bots.whatsapp import send

        send(sub["target"], [digest(sub, docs, "whatsapp")])
    else:
        from api.app.features.alerts.mail import send_email

        send_email(sub["target"], f"TogoLM : alerte « {sub['query']} »", digest(sub, docs, "text"))


def send_digests() -> dict:
    """Send every active, confirmed subscription its new matches since last time."""
    sent = failed = 0
    now = datetime.datetime.now()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, channel, target, query, category, token,
                       COALESCE(last_sent_at, created_at)
                FROM alert_subscriptions WHERE active AND confirmed
                """
            )
            subs = [
                dict(zip(("id", "channel", "target", "query", "category", "token", "since"), r))
                for r in cur.fetchall()
            ]
            for sub in subs:
                docs = matches(cur, sub["query"], sub["category"], sub["since"])
                if docs:
                    try:
                        _deliver(sub, docs)
                        sent += 1
                    except Exception:
                        failed += 1
                        logger.exception("Alert digest failed (%s)", sub["channel"])
                        continue
                cur.execute(
                    "UPDATE alert_subscriptions SET last_sent_at = %s WHERE id = %s",
                    (now, sub["id"]),
                )
        conn.commit()
    finally:
        conn.close()
    return {"subscriptions": len(subs), "digests_sent": sent, "failed": failed}
