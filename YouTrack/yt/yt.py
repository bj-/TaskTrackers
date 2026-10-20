#!/usr/bin/env python3
"""Работа Claude с YouTrack через REST API: поиск, чтение, черновики изменений.

Изменяющие команды по умолчанию только печатают черновик; отправка - с ключом --apply.
Правила (что можно без согласования, префиксы AI) - AI-Memory/memory/youtrack-access.md.

Токен: env TRACKER_TOKEN, иначе файл из env YOUTRACK_TOKEN_FILE (по умолчанию C:/Git/Youtrack_token.md).
Адрес: env YOUTRACK_URL, иначе первая ссылка https://... из файла токена.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

AI_PREFIX = "**AI:** "
AI_SECTION = "## AI"
AI_TAG = "AI"
DEFAULT_TOKEN_FILE = "C:/Git/Youtrack_token.md"

ISSUE_FIELDS = ("idReadable,summary,description,created,updated,reporter(login),"
                "project(shortName),tags(name),customFields(name,value(name,login,presentation)),"
                "links(direction,linkType(name,sourceToTarget,targetToSource),issues(idReadable,summary)),"
                "comments(id,text,created,author(login))")


def load_config():
    path = os.environ.get("YOUTRACK_TOKEN_FILE", DEFAULT_TOKEN_FILE)
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    token = os.environ.get("TRACKER_TOKEN")
    if not token:
        m = re.search(r"perm[:-]\S+", text)
        token = m.group(0) if m else None
    url = os.environ.get("YOUTRACK_URL")
    if not url:
        m = re.search(r"https://\S+", text)
        url = m.group(0) if m else None
    if not token or not url:
        sys.exit(f"Нет токена или адреса: задайте TRACKER_TOKEN / YOUTRACK_URL или файл {path}")
    return url.rstrip("/") + "/api", token


BASE, TOKEN = None, None


def api(method, path, params=None, body=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + TOKEN, "Accept": "application/json",
        "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {method} {path}: {e.read().decode('utf-8', 'replace')[:500]}")


def field_value(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(field_value(x) for x in v)
    if isinstance(v, dict):
        return v.get("name") or v.get("login") or v.get("presentation") or ""
    return str(v)


def read_text(args):
    if getattr(args, "file", None):
        return open(args.file, encoding="utf-8").read().strip()
    if getattr(args, "text", None):
        return args.text.strip()
    sys.exit("Нужен --text или --file")


def draft(title, lines, apply):
    print(("ОТПРАВКА: " if apply else "ЧЕРНОВИК (без --apply ничего не отправлено): ") + title)
    for line in lines:
        print(line)
    print("-" * 60)


# --- чтение ---

def cmd_me(args):
    me = api("GET", "/users/me", {"fields": "login,name"})
    print(me["login"], "-", me["name"])


def cmd_search(args):
    issues = api("GET", "/issues", {"query": args.query, "$top": args.top,
                                    "fields": "idReadable,summary,customFields(name,value(name))"})
    for i in issues:
        f = {c["name"]: field_value(c["value"]) for c in i["customFields"]}
        print(f'{i["idReadable"]:<10} [{f.get("State", "")}] {i["summary"]}')
    print(f"Найдено: {len(issues)} (показано не больше {args.top})")


def cmd_show(args):
    i = api("GET", f"/issues/{args.id}", {"fields": ISSUE_FIELDS})
    if args.json:
        print(json.dumps(i, ensure_ascii=False, indent=2))
        return
    print(f'{i["idReadable"]}: {i["summary"]}')
    for c in i["customFields"]:
        if c["value"] not in (None, []):
            print(f'  {c["name"]}: {field_value(c["value"])}')
    if i.get("tags"):
        print("  Теги:", ", ".join(t["name"] for t in i["tags"]))
    for l in i.get("links", []):
        if l["issues"]:
            lt = l["linkType"]
            name = lt["targetToSource"] if l["direction"] == "INWARD" and lt["targetToSource"] else lt["sourceToTarget"]
            for t in l["issues"]:
                print(f'  {name}: {t["idReadable"]} {t["summary"]}')
    print("\n--- Описание ---\n" + (i.get("description") or ""))
    for c in i.get("comments", []):
        print(f'\n--- Комментарий {c["id"]} ({c["author"]["login"]}) ---\n{c["text"]}')


# --- изменения (черновик / --apply) ---

def run_command(issue_ids, query):
    api("POST", "/commands", {"fields": "id"},
        {"query": query, "issues": [{"idReadable": i} for i in issue_ids]})


def cmd_comment(args):
    text = read_text(args)
    if not text.startswith((AI_SECTION, AI_PREFIX.strip())):
        text = f"{AI_SECTION}\n\n{text}"
    draft(f"комментарий к {args.id}", [text], args.apply)
    if args.apply:
        c = api("POST", f"/issues/{args.id}/comments", {"fields": "id"}, {"text": text})
        print("Добавлен комментарий", c["id"])


def cmd_comment_insert(args):
    text = read_text(args)
    c = api("GET", f"/issues/{args.id}/comments/{args.comment_id}", {"fields": "text"})
    lines = c["text"].split("\n")
    pos = next((n for n, l in enumerate(lines) if args.after in l), None)
    if pos is None:
        sys.exit(f"В комментарии {args.comment_id} нет строки с «{args.after}»")
    # строка списка - вставляем тем же маркером, чтобы не разорвать список
    marker = re.match(r"\s*(?:[*+-]|\d+[.)])\s+", lines[pos])
    line = (marker.group(0) if marker else "") + (text if text.startswith(AI_PREFIX.strip()) else AI_PREFIX + text)
    new = lines[:pos + 1] + [line] + lines[pos + 1:]
    draft(f"вставка строки в комментарий {args.comment_id} задачи {args.id}",
          [("+ " if n == pos + 1 else "  ") + l for n, l in enumerate(new)], args.apply)
    if args.apply:
        api("POST", f"/issues/{args.id}/comments/{args.comment_id}", {"fields": "id"}, {"text": "\n".join(new)})
        print("Комментарий изменён")


def cmd_append(args):
    text = read_text(args)
    i = api("GET", f"/issues/{args.id}", {"fields": "description"})
    old = (i.get("description") or "").rstrip()
    block = text if args.inline else f"{AI_SECTION}\n\n{text}"
    if args.inline and not block.startswith(AI_PREFIX.strip()):
        block = AI_PREFIX + block
    new = (old + "\n\n" + block).strip()
    draft(f"дополнение описания {args.id} (старый текст не меняется)", ["+ " + l for l in block.splitlines()], args.apply)
    if args.apply:
        api("POST", f"/issues/{args.id}", {"fields": "id"}, {"description": new})
        print("Описание дополнено")


def cmd_create(args):
    description = read_text(args)
    commands = list(args.command or [])
    if not args.no_tag:
        commands.append(f"tag {AI_TAG}")
    lines = [f"Проект: {args.project}", f"Тема: {args.summary}", "Команды полей: " + "; ".join(commands),
             "Связи: " + ("; ".join(args.link or []) or "-"), "--- Описание ---", description]
    draft("новая задача", lines, args.apply)
    if not args.apply:
        return
    p = api("GET", f"/admin/projects/{args.project}", {"fields": "id"})
    i = api("POST", "/issues", {"fields": "idReadable"},
            {"project": {"id": p["id"]}, "summary": args.summary, "description": description})
    iid = i["idReadable"]
    for c in commands:
        run_command([iid], c)
    for l in args.link or []:
        run_command([iid], l)
    print("Создана", iid, BASE[:-4] + "/issue/" + iid)


def cmd_link(args):
    query = f"{args.type} {args.target}"
    draft(f"связь {args.id}", [f"{args.id} {query}"], args.apply)
    if args.apply:
        run_command([args.id], query)
        print("Связь добавлена")


def cmd_command(args):
    draft(f"команда для {', '.join(args.ids)}", [args.query], args.apply)
    if args.apply:
        run_command(args.ids, args.query)
        print("Команда применена")


def main():
    global BASE, TOKEN
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("me", help="проверить доступ").set_defaults(fn=cmd_me)

    p = sub.add_parser("search", help="поиск задач (язык запросов YouTrack)")
    p.add_argument("query")
    p.add_argument("--top", type=int, default=20)
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("show", help="задача целиком: поля, связи, описание, комментарии")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_show)

    def with_text(p):
        p.add_argument("--text")
        p.add_argument("--file", help="текст из файла (UTF-8)")
        p.add_argument("--apply", action="store_true", help="отправить (без него - только черновик)")

    p = sub.add_parser("comment", help=f"комментарий с заголовком '{AI_SECTION}' первой строкой")
    p.add_argument("id")
    with_text(p)
    p.set_defaults(fn=cmd_comment)

    p = sub.add_parser("comment-insert", help=f"вставить строку с {AI_PREFIX.strip()} в существующий комментарий")
    p.add_argument("id")
    p.add_argument("comment_id", help="id комментария, напр. 7-58 (см. show)")
    p.add_argument("--after", required=True, help="подстрока строки, после которой вставить")
    with_text(p)
    p.set_defaults(fn=cmd_comment_insert)

    p = sub.add_parser("append",help=f"дописать в описание раздел '{AI_SECTION}' (или строку с --inline)")
    p.add_argument("id")
    p.add_argument("--inline", action="store_true", help=f"строка с префиксом {AI_PREFIX.strip()} вместо раздела")
    with_text(p)
    p.set_defaults(fn=cmd_append)

    p = sub.add_parser("create", help=f"новая задача (с тегом {AI_TAG})")
    p.add_argument("--project", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--command", action="append", help="команда YouTrack для полей, напр. 'Type Bug', 'Priority Major'")
    p.add_argument("--link", action="append", help="связь командой, напр. 'relates to BA-12', 'subtask of BA-3'")
    p.add_argument("--no-tag", action="store_true", help=f"не ставить тег {AI_TAG}")
    with_text(p)
    p.set_defaults(fn=cmd_create)

    p = sub.add_parser("link", help="связь между задачами")
    p.add_argument("id")
    p.add_argument("type", help="'relates to', 'depends on', 'is required for', 'duplicates', 'subtask of', 'parent for'")
    p.add_argument("target")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_link)

    p = sub.add_parser("command", help="произвольная команда YouTrack (поля, теги)")
    p.add_argument("query")
    p.add_argument("ids", nargs="+")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_command)

    args = ap.parse_args()
    BASE, TOKEN = load_config()
    args.fn(args)


if __name__ == "__main__":
    main()
