"""
Register the TogoLM Telegram bot's webhook and commands (run once, then after
changing the token or the secret).

    TELEGRAM_BOT_TOKEN=... TELEGRAM_WEBHOOK_SECRET=... python scripts/bots/telegram_setup.py

Same two values as in the API's environment (Coolify). The secret is any
random string (letters, digits, _ and -), e.g. `python -c "import secrets;
print(secrets.token_urlsafe(32))"`.
"""

import os
import sys

import httpx

WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "https://api.togolm.com/v1/bots/telegram/webhook")
COMMANDS = [
    ("aide", "Comment utiliser TogoLM"),
    ("fr", "Réponses en français"),
    ("ee", "Réponses en éwé (expérimental)"),
    ("kbp", "Réponses en kabiyè (expérimental)"),
    ("en", "Answers in English"),
    ("nouveau", "Nouvelle conversation"),
]
DESCRIPTION = (
    "Assistant sur le Togo : démarches, lois, santé, éducation, économie et actualité, "
    "à partir de sources officielles. Question écrite ou message vocal, en français, "
    "éwé ou kabiyè."
)


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not token or not secret:
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET are required", file=sys.stderr)
        return 1
    api = f"https://api.telegram.org/bot{token}"
    calls = [
        (
            "setWebhook",
            {
                "url": WEBHOOK_URL,
                "secret_token": secret,
                "allowed_updates": ["message"],
                "drop_pending_updates": True,
            },
        ),
        ("setMyCommands", {"commands": [{"command": c, "description": d} for c, d in COMMANDS]}),
        ("setMyDescription", {"description": DESCRIPTION}),
        ("setMyShortDescription", {"short_description": "Vos questions sur le Togo, sourcées."}),
    ]
    for method, payload in calls:
        result = httpx.post(f"{api}/{method}", json=payload, timeout=30).json()
        print(method, "ok" if result.get("ok") else result)
    info = httpx.get(f"{api}/getWebhookInfo", timeout=30).json().get("result", {})
    print("webhook:", info.get("url"), "| pending:", info.get("pending_update_count"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
