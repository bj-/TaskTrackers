# YouTrack

Workflow-скрипты YouTrack (каждый — отдельная папка с `package.json` и `README.md`) и `yt/` — скрипт работы Claude
с YouTrack через API (`yt/README.md`; правила доступа — `AI-Memory/memory/youtrack-access.md`).

## autofill-dev-qa-fields

Автоматически заполняет поля «Разработчик» и «Тестировщик» при назначении исполнителя или списании времени.
Правила, установка и проверка — в `autofill-dev-qa-fields/README.md`.

- Все настройки — в `autofill-dev-qa-fields/config.js`; названия групп, состояний и типов работ сверять с конкретным YouTrack.
- Архив для импорта собирается из папки `YouTrack/` (архив в git не хранится):
  `Compress-Archive -Path .\autofill-dev-qa-fields\* -DestinationPath .\autofill-dev-qa-fields.zip -Force`
