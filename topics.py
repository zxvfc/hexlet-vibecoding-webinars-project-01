#!/usr/bin/env python3
"""Темы дайджеста. Источник истины — topics.txt в репозитории.

    python3 topics.py list                  темы из topics.txt (JSON-список)
    python3 topics.py apply <requests.json> применить заявки со страницы

Заявка: {"id": "...", "op": "add"|"remove", "name": "...", "at": "ISO-время"}.
Заявки — действия, а не снимок списка, поэтому применяются поверх текущего
topics.txt. Конфликт («добавить X» против удаления X в репозитории или наоборот)
решается по времени: побеждает более позднее действие. Время действия в
репозитории — время коммита, в котором X появился или пропал в topics.txt.

Результат apply (stdout, JSON):
    {"topics": [...], "changed": bool, "changes": [...], "notes": [...], "processed": [ids]}
changes — строки для сообщения коммита, notes — что сообщить в Telegram.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TOPICS = os.path.join(HERE, "topics.txt")


def parse(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def read_topics():
    if not os.path.exists(TOPICS):
        return []
    with open(TOPICS, encoding="utf-8") as f:
        return parse(f.read())


def write_topics(topics):
    with open(TOPICS, "w", encoding="utf-8") as f:
        f.write("# Темы дайджеста, по одной на строку. Источник истины.\n")
        for t in topics:
            f.write(t + "\n")


def key(name):
    return " ".join(name.split()).casefold()


def ts(s):
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def git(*args):
    r = subprocess.run(["git", "-C", HERE, *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def history():
    """[(время коммита, множество ключей тем)] от новых к старым."""
    log = git("log", "--format=%H %cI", "--", "topics.txt")
    out = []
    for line in (log or "").splitlines():
        sha, when = line.split(" ", 1)
        content = git("show", f"{sha}:topics.txt")
        out.append((ts(when), {key(t) for t in parse(content or "")}))
    return out


def last_repo_change(k, hist, present_now):
    """Время коммита, с которого наличие темы k такое, как сейчас (None — так было всегда)."""
    when = None
    for t, keys in hist:  # от новых к старым
        if (k in keys) != present_now:
            return when
        when = t
    return None


def ever_existed(k, hist):
    return any(k in keys for _, keys in hist)


def apply(requests):
    topics = read_topics()
    hist = history()
    changes, notes, processed = [], [], []
    for r in sorted(requests, key=lambda r: r.get("at", "")):
        processed.append(r.get("id"))
        name = " ".join(str(r.get("name", "")).split())
        op = r.get("op")
        if not name or op not in ("add", "remove"):
            notes.append(f"Заявка пропущена: непонятное действие {op!r} для «{name}».")
            continue
        k = key(name)
        current = {key(t): t for t in topics}
        present = k in current
        try:
            req_at = ts(r["at"])
        except Exception:
            req_at = None
        repo_at = last_repo_change(k, hist, present)
        if op == "add":
            if present:
                continue
            if repo_at and req_at and repo_at > req_at:
                notes.append(f"Тема «{name}»: удалена в репозитории {repo_at:%Y-%m-%d %H:%M} UTC "
                             f"позже заявки на добавление ({req_at:%Y-%m-%d %H:%M} UTC). Оставил удалённой.")
                continue
            if repo_at and req_at:
                notes.append(f"Тема «{name}»: удалена в репозитории {repo_at:%Y-%m-%d %H:%M} UTC, "
                             f"добавлена на странице {req_at:%Y-%m-%d %H:%M} UTC. Оставил добавленной.")
            topics.append(name)
            changes.append(f"+ {name}")
        else:
            if not present:
                if not ever_existed(k, hist):
                    notes.append(f"Заявка на удаление: темы «{name}» нет в списке, ничего не удалено.")
                continue
            if repo_at and req_at and repo_at > req_at:
                notes.append(f"Тема «{name}»: добавлена в репозитории {repo_at:%Y-%m-%d %H:%M} UTC "
                             f"позже заявки на удаление ({req_at:%Y-%m-%d %H:%M} UTC). Оставил.")
                continue
            if repo_at and req_at:
                notes.append(f"Тема «{name}»: добавлена в репозитории {repo_at:%Y-%m-%d %H:%M} UTC, "
                             f"удалена на странице {req_at:%Y-%m-%d %H:%M} UTC. Удалил.")
            topics = [t for t in topics if key(t) != k]
            changes.append(f"- {current[k]}")
    # дубли без учёта регистра
    seen, unique = set(), []
    for t in topics:
        if key(t) not in seen:
            seen.add(key(t))
            unique.append(t)
    if changes or unique != read_topics():
        write_topics(unique)
    return {"topics": unique, "changed": bool(changes), "changes": changes,
            "notes": notes, "processed": processed}


def main():
    cmd, *args = sys.argv[1:] or ["help"]
    if cmd == "list":
        print(json.dumps(read_topics(), ensure_ascii=False))
    elif cmd == "apply":
        with open(args[0], encoding="utf-8") as f:
            reqs = json.load(f)
        print(json.dumps(apply(reqs), ensure_ascii=False, indent=2))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
