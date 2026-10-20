/**
 * Учёт участников задачи: кто реально работал над задачей как разработчик или тестировщик.
 *
 * Когда пользователь оставляет комментарий, списывает время или меняет название / описание
 * задачи, он добавляется в поле своей роли:
 * - участник группы «Разработчики» (Developers) — в поле «Разработчик»;
 * - участник группы «Тестировщики» (Testers) — в поле «Тестировщик»;
 * - состоит в обеих группах — в оба поля.
 *
 * Поля многозначные: пользователь добавляется к уже указанным, никто не удаляется.
 * Пользователь вне групп ролей или вне набора значений поля — поле не меняется
 * (предупреждение в лог workflow), само действие пользователя не откатывается.
 */
const entities = require('@jetbrains/youtrack-scripting-api/entities');

// Поля и группы ролей. Группы — любые из списка (имена сверять с YouTrack).
const ROLES = [
  { field: 'Разработчик', groups: ['Developers', 'Разработчики'] },
  { field: 'Тестировщик', groups: ['Testers', 'Тестировщики'] }
];

function inAnyGroup(user, groups) {
  return groups.some(function (group) {
    return user.isInGroup(group);
  });
}

// Добавляет пользователя в поле роли. Поле может быть одно- или многозначным;
// однозначное заполняется только если пустое.
function addToField(issue, fieldName, user) {
  const projectField = issue.project.findFieldByName(fieldName);
  if (!projectField) {
    console.warn(issue.id + ': в проекте ' + issue.project.shortName + ' нет поля «' + fieldName + '»');
    return;
  }

  // Пользователь вне набора значений поля: запись бросит исключение и откатит всё изменение.
  if (typeof projectField.findValueByLogin === 'function' && !projectField.findValueByLogin(user.login)) {
    console.warn(issue.id + ': ' + user.login + ' не входит в набор значений поля «' + fieldName + '»');
    return;
  }

  try {
    const current = issue.fields[fieldName];
    if (current && typeof current.add === 'function') {
      if (!current.has(user)) current.add(user);
    } else if (!current) {
      issue.fields[fieldName] = user;
    }
  } catch (e) {
    console.warn(issue.id + ': не удалось записать ' + user.login + ' в поле «' + fieldName + '»: ' + e);
  }
}

exports.rule = entities.Issue.onChange({
  title: 'AutoFill track developers and testers',

  // Комментарий, списание времени, изменение названия или описания.
  guard: function (ctx) {
    const issue = ctx.issue;
    return issue.comments.added.isNotEmpty() ||
      issue.workItems.added.isNotEmpty() ||
      issue.isChanged('summary') ||
      issue.isChanged('description');
  },

  action: function (ctx) {
    const issue = ctx.issue;
    const user = ctx.currentUser;
    if (!user) return;

    ROLES.forEach(function (role) {
      if (inAnyGroup(user, role.groups)) addToField(issue, role.field, user);
    });
  },

  requirements: {}
});
