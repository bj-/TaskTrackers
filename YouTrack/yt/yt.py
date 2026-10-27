#!/usr/bin/env python3
"""Работа Claude с YouTrack через REST API: поиск, чтение, черновики изменений.

Изменяющие команды по умолчанию только печатают черновик; отправка - с ключом --apply.
Правила (что можно без согласования, префиксы AI) - AI-Memory/memory/youtrack-access.md.

Токен: env TRACKER_TOKEN, иначе файл из env YOUTRACK_TOKEN_FILE (по умолчанию C:/Git/Youtrack_token.md).
Адрес: env YOUTRACK_URL, иначе первая ссылка https://... из файла токена.
"""
import argparse
import datetime as dt
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


GROUP_PREFIX = "sg-"   # тег группы безопасности (ADR Test-Library 0011): сессия группы читает только свои задачи


def group_tags_exist(groups):
    """Теги групп, которые есть в трекере (запрос с несуществующим тегом YouTrack отклоняет)."""
    tags = api("GET", "/tags", {"fields": "name", "query": GROUP_PREFIX, "$top": 500}) or []
    return [g for g in groups if g in {t["name"] for t in tags}]


def cmd_search(args):
    query = args.query
    if args.group:
        groups = group_tags_exist(args.group)
        if not groups:
            print(f"Найдено: 0 - тегов {', '.join(args.group)} в трекере ещё нет")
            return
        query += " (" + " or ".join(f"tag: {{{g}}}" for g in groups) + ")"
    issues = api("GET", "/issues", {"query": query, "$top": args.top,
                                    "fields": "idReadable,summary,tags(name),customFields(name,value(name))"})
    skip = set(args.skip_group or [])
    issues = [i for i in issues if not skip & {t["name"] for t in i.get("tags") or []}]
    for i in issues:
        f = {c["name"]: field_value(c["value"]) for c in i["customFields"]}
        groups = [t["name"] for t in i.get("tags") or [] if t["name"].startswith(GROUP_PREFIX)]
        print(f'{i["idReadable"]:<10} [{f.get("State", "")}] {i["summary"]}' + (f'  {{{", ".join(groups)}}}' if groups else ""))
    print(f"Найдено: {len(issues)} (показано не больше {args.top})")


RESTRICTED_TAG = "ai-restricted"   # описание и комментарии задачи ассистенту не читать (ADR Test-Library 0008)


def cmd_show(args):
    i = api("GET", f"/issues/{args.id}", {"fields": ISSUE_FIELDS})
    tags = {t["name"] for t in i.get("tags") or []}
    if RESTRICTED_TAG in tags and not args.human:
        i["description"] = f"[скрыто: тег {RESTRICTED_TAG} - описание читает человек; показать: --human]"
        i["comments"] = []
    foreign = sorted(t for t in tags if t.startswith(GROUP_PREFIX) and t not in (args.group or []))
    if args.group and foreign and not args.human:      # задача другой группы безопасности - не в контекст сессии группы
        i["description"] = f"[скрыто: группа {', '.join(foreign)} - не группа сессии ({', '.join(args.group)})]"
        i["comments"] = []
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


DAY_START_HOUR = 8   # рабочие сутки - с 08:00 до 08:00: работа после полуночи идёт в предыдущий день


def day_bounds(date):
    """Границы рабочих суток date (местное время) в мс эпохи."""
    start = dt.datetime.combine(dt.date.fromisoformat(date), dt.time(DAY_START_HOUR))
    return int(start.timestamp() * 1000), int((start + dt.timedelta(days=1)).timestamp() * 1000)


def ms_local(ms):
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")


def cmd_team(args):
    p = api("GET", f"/admin/projects/{args.project}", {"fields": "team(users(login,name,banned))"})
    for u in p["team"]["users"]:
        if not u.get("banned"):
            print(f'{u["login"]:<20} {u["name"]}')


def cmd_day(args):
    """Что было у человека за рабочие сутки: назначенные задачи, его комментарии, списанное время."""
    login = args.author or api("GET", "/users/me", {"fields": "login"})["login"]
    start, end = day_bounds(args.date)
    print(f"=== {login}, {args.date} (сутки с {DAY_START_HOUR:02d}:00) ===")

    print("\n--- Назначенные открытые задачи ---")
    for i in api("GET", "/issues", {"query": f"Assignee: {login} #Unresolved", "$top": 100,
                                    "fields": "idReadable,summary,customFields(name,value(name))"}):
        f = {c["name"]: field_value(c["value"]) for c in i["customFields"]}
        print(f'{i["idReadable"]:<10} [{f.get("State", "")}] {i["summary"]}')

    print("\n--- Комментарии ---")
    day = dt.date.fromisoformat(args.date)
    query = f"commenter: {login} commented: {day} .. {day + dt.timedelta(days=1)}"
    for i in api("GET", "/issues", {"query": query, "$top": 100,
                                    "fields": "idReadable,summary,comments(created,text,author(login))"}):
        for c in i.get("comments") or []:
            if c["author"]["login"] == login and start <= c["created"] < end:
                text = " ".join((c["text"] or "").split())
                print(f'{i["idReadable"]:<10} {ms_local(c["created"])}  {text[:args.width]}')

    print("\n--- Списанное время ---")
    total = 0
    for w in api("GET", "/workItems", {"author": login, "startDate": args.date, "endDate": args.date, "$top": 500,
                                       "fields": "date,duration(minutes,presentation),text,issue(idReadable,summary)"}):
        total += w["duration"]["minutes"]
        text = " ".join((w.get("text") or "").split())
        print(f'{w["issue"]["idReadable"]:<10} {w["duration"]["presentation"]:>8}  {w["issue"]["summary"]}'
              + (f"  - {text[:args.width]}" if text else ""))
    print(f"Итого списано: {total // 60} ч {total % 60} мин")


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


def cmd_work(args):
    text = read_text(args) if (args.text or args.file) else ""
    date = dt.datetime.combine(dt.date.fromisoformat(args.date), dt.time(12))
    body = {"date": int(date.timestamp() * 1000), "duration": {"presentation": args.duration}, "text": text}
    if args.type:
        project = api("GET", f"/issues/{args.id}", {"fields": "project(id)"})["project"]["id"]
        types = api("GET", f"/admin/projects/{project}/timeTrackingSettings", {"fields": "workItemTypes(id,name)"})
        found = [t for t in types["workItemTypes"] if t["name"] == args.type]
        if not found:
            sys.exit(f"Нет типа работы «{args.type}»: " + ", ".join(t["name"] for t in types["workItemTypes"]))
        body["type"] = {"id": found[0]["id"]}
    draft(f"списание времени в {args.id}", [f"Дата: {args.date}", f"Время: {args.duration}",
                                             f"Тип: {args.type or '-'}", f"Что сделано: {text or '-'}"], args.apply)
    if args.apply:
        w = api("POST", f"/issues/{args.id}/timeTracking/workItems", {"fields": "id,duration(presentation)"}, body)
        print("Списано", w["duration"]["presentation"], "- запись", w["id"])


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
    p.add_argument("--group", action="append", help="только задачи с тегом группы безопасности (sg-..., можно несколько)")
    p.add_argument("--skip-group", action="append", help="без задач с тегом этой группы (например sg-restricted)")
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("show", help="задача целиком: поля, связи, описание, комментарии")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.add_argument("--human", action="store_true", help=f"показать описание задачи с тегом {RESTRICTED_TAG} (запускает человек)")
    p.add_argument("--group", action="append", help="группа сессии (sg-...): у задачи с тегом другой группы описание скрыто")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("team", help="участники проекта (состав отдела - TES)")
    p.add_argument("project", nargs="?", default="TES")
    p.set_defaults(fn=cmd_team)

    p = sub.add_parser("day", help="за рабочие сутки: назначенные задачи, комментарии, списанное время")
    p.add_argument("--date", default=dt.date.today().isoformat(), help="YYYY-MM-DD (по умолчанию сегодня)")
    p.add_argument("--author", help="логин (по умолчанию владелец токена)")
    p.add_argument("--width", type=int, default=160, help="обрезать текст комментария до N символов")
    p.set_defaults(fn=cmd_day)

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

    p = sub.add_parser("work", help="списать время в задачу (worklog)")
    p.add_argument("id")
    p.add_argument("duration", help="'1h 30m', '45m'")
    p.add_argument("--date", default=dt.date.today().isoformat(), help="YYYY-MM-DD - день работы")
    p.add_argument("--type", help="тип работы, напр. 'Исследование', 'Документирование'")
    with_text(p)
    p.set_defaults(fn=cmd_work)

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
