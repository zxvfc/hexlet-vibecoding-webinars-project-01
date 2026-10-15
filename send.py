#!/usr/bin/env python3
"""Отправка сообщения в Telegram (только стандартная библиотека).

Использование:
    python3 send.py "текст"
    echo "текст" | python3 send.py

Токен и chat id берутся из TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
или из файла .env рядом со скриптом. Токен никогда не печатается.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

LIMIT = 4096
HERE = os.path.dirname(os.path.abspath(__file__))


def load_env():
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def split_text(text, limit=LIMIT):
    """Делит текст на части не длиннее limit, по возможности по строкам."""
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        parts.append(text)
    return parts


def send(text):
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit("Ошибка: не заданы TELEGRAM_BOT_TOKEN и/или TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for part in split_text(text):
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": part,
            "disable_web_page_preview": "true",
        }).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
                body = json.load(r)
        except urllib.error.HTTPError as e:
            try:
                desc = json.load(e).get("description", "")
            except Exception:
                desc = ""
            raise SystemExit(f"Ошибка Telegram: HTTP {e.code} {desc}".strip())
        except urllib.error.URLError as e:
            raise SystemExit(f"Ошибка сети: {e.reason}")
        if not body.get("ok"):
            raise SystemExit(f"Ошибка Telegram: {body.get('description', 'неизвестно')}")
    print(f"Отправлено частей: {len(split_text(text))}")


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    if not msg.strip():
        raise SystemExit("Пустое сообщение")
    send(msg)
