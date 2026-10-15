#!/usr/bin/env python3
"""Вспомогательные операции с архивом archive.json.

    python3 archive.py norm <url>          нормализованный адрес и sha1
    python3 archive.py seen <url>          exit 0 если уже в архиве, 1 если новый
    python3 archive.py add '<json>'        добавить запись (объект или список), дубли пропускаются
    python3 archive.py last-empty          время последнего "Ничего не нашлось" (или пусто)
    python3 archive.py mark-empty          запомнить время отправки "Ничего не нашлось"
    python3 archive.py page-sync <ids.json> <dir>
                                           записи архива, которых нет на странице (ids.json — список id
                                           со страницы): кладёт по файлу на запись в <dir> и печатает
                                           JSON для ArtifactData batch (по 50 записей на пакет)
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, "archive.json")
STATE = os.path.join(HERE, "state.json")
FIELDS = ("title", "url", "source", "published", "found", "topic", "summary")


def normalize(url):
    p = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                       if not k.lower().startswith("utm_")])
    path = p.path.rstrip("/")
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, query, ""))


def sha1(url):
    return hashlib.sha1(normalize(url).encode()).hexdigest()


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def main():
    cmd, *args = sys.argv[1:] or ["help"]
    if cmd == "norm":
        print(normalize(args[0]), sha1(args[0]))
    elif cmd == "seen":
        ids = {e.get("id") for e in load(ARCHIVE, [])}
        sys.exit(0 if sha1(args[0]) in ids else 1)
    elif cmd == "add":
        items = json.loads(args[0])
        items = items if isinstance(items, list) else [items]
        archive = load(ARCHIVE, [])
        ids = {e.get("id") for e in archive}
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        added = 0
        for it in items:
            entry = {k: it.get(k, "") for k in FIELDS}
            entry["found"] = entry["found"] or now
            entry["id"] = sha1(entry["url"])
            if entry["id"] in ids:
                continue
            archive.append(entry)
            ids.add(entry["id"])
            added += 1
        save(ARCHIVE, archive)
        print(f"Добавлено: {added}")
    elif cmd == "last-empty":
        print(load(STATE, {}).get("last_empty", ""))
    elif cmd == "mark-empty":
        state = load(STATE, {})
        state["last_empty"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save(STATE, state)
    elif cmd == "page-sync":
        with open(args[0], encoding="utf-8") as f:
            have = set(json.load(f))
        out_dir = args[1]
        os.makedirs(out_dir, exist_ok=True)
        writes = []
        for e in load(ARCHIVE, []):
            if e["id"] in have:
                continue
            path = os.path.join(out_dir, e["id"] + ".json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({k: e.get(k, "") for k in FIELDS}, f, ensure_ascii=False)
            writes.append({"op": "set", "collection": "links", "doc_id": e["id"], "file_path": os.path.abspath(path)})
        print(json.dumps([writes[i:i + 50] for i in range(0, len(writes), 50)], ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
