# yt.py — работа Claude с YouTrack

Скрипт для типовых операций через REST API YouTrack: поиск, чтение, комментарии, дополнение описания, заведение
задач и связей. Только стандартная библиотека Python 3.

Правила (что можно без согласования, префиксы `**AI:**` / `## AI`, тег `AI`) — `AI-Memory/memory/youtrack-access.md`.

## Токен

- env `TRACKER_TOKEN`, иначе файл `C:/Git/Youtrack_token.md` (путь меняется env `YOUTRACK_TOKEN_FILE`);
- адрес — env `YOUTRACK_URL`, иначе первая ссылка `https://...` из файла токена.

Токен в репозиторий не класть; у каждого на своей машине свой.

## Команды

Изменяющие команды без `--apply` только печатают черновик — его показываем на согласование.

| Команда | Что делает |
|---|---|
| `python yt.py me` | Проверить доступ |
| `python yt.py search "project: BA Type: Bug авторизация" [--top 20]` | Поиск (язык запросов YouTrack) |
| `python yt.py show BA-12 [--json]` | Поля, связи, описание, комментарии |
| `python yt.py comment BA-12 --file c.md [--apply]` | Комментарий; префикс `**AI:**` добавляется сам |
| `python yt.py append BA-12 --file d.md [--inline] [--apply]` | Дописать в описание раздел `## AI` (или строку с `**AI:**`); старый текст не меняется |
| `python yt.py create --project BA --summary "..." --file bug.md --command "Type Bug" --link "relates to BA-12" [--apply]` | Новая задача с тегом `AI` (`--no-tag` — без) |
| `python yt.py link BA-40 "relates to" BA-12 [--apply]` | Связь: `relates to`, `depends on`, `is required for`, `duplicates`, `subtask of`, `parent for` |
| `python yt.py command "Priority Major" BA-40 [--apply]` | Произвольная команда YouTrack |

Текст — через `--text` или `--file` (UTF-8, удобнее для Markdown).
