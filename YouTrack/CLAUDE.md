# YouTrack

Workflow-скрипты YouTrack. Каждый workflow — отдельная папка с `package.json` и `README.md`.

## dev-qa-fields

Автоматически заполняет поля «Разработчик» и «Тестировщик» при назначении исполнителя или списании времени.
Правила, установка и проверка — в `dev-qa-fields/README.md`.

- Все настройки — в `dev-qa-fields/config.js`; названия групп, состояний и типов работ сверять с конкретным YouTrack.
- Архив для импорта собирается из папки `YouTrack/` (архив в git не хранится):
  `Compress-Archive -Path .\dev-qa-fields\* -DestinationPath .\dev-qa-fields.zip -Force`
