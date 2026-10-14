const config = require('./config');

const DEVELOPER = 'developer';
const TESTER = 'tester';
const ROLES = [DEVELOPER, TESTER];

function inAnyGroup(user, groups) {
  return groups.some(function (group) {
    return user.isInGroup(group);
  });
}

function byName(value, names) {
  return !!value && names.indexOf(value.name) !== -1;
}

function groupsFor(role) {
  return role === DEVELOPER ? config.DEVELOPER_GROUPS : config.TESTER_GROUPS;
}

function workTypesFor(role) {
  return role === DEVELOPER ? config.DEVELOPER_WORK_TYPES : config.TESTER_WORK_TYPES;
}

// Состояния, в которых роль заполняется в этом проекте (с учётом PROJECT_STATES).
function statesFor(role, project) {
  const overrides = config.PROJECT_STATES || {};
  const custom = project && (overrides[project.name] || overrides[project.shortName]);
  if (custom) return custom[role] || [];
  return role === DEVELOPER ? config.DEVELOPER_STATES : config.TESTER_STATES;
}

/**
 * Роли, поля которых можно заполнить этим пользователем. Должно выполняться всё сразу:
 * - пользователь в группе роли;
 * - роль используется в проекте (список состояний проекта не пустой);
 * - состояние задачи из списка роли; при списании времени вместо состояния
 *   подходит и тип работы роли (workType передаётся только для списания).
 */
exports.matchingRoles = function (user, state, workType, project) {
  return ROLES.filter(function (role) {
    if (!inAnyGroup(user, groupsFor(role))) return false;
    const states = statesFor(role, project);
    if (!states.length) return false;
    return byName(state, states) || byName(workType, workTypesFor(role));
  });
};

/**
 * Оба поля уже заполнены — workflow ничего не делает.
 */
exports.bothFilled = function (issue) {
  return !!issue.fields.Developer && !!issue.fields.Tester;
};

/**
 * Записывает пользователя в поле, соответствующее роли, только если поле ещё пустое.
 */
exports.applyRole = function (issue, role, user) {
  const field = role === DEVELOPER ? 'Developer' : role === TESTER ? 'Tester' : null;
  if (!field) return false;

  const current = issue.fields[field];
  if (current) return false;

  // Пользователь вне набора значений поля: запись бросит исключение и откатит всё изменение
  // (в т.ч. само назначение исполнителя). Пропускаем поле и пишем предупреждение в лог.
  const fieldName = role === DEVELOPER ? config.DEVELOPER_FIELD : config.TESTER_FIELD;
  const projectField = issue.project.findFieldByName(fieldName);
  if (projectField && typeof projectField.findValueByLogin === 'function' &&
      !projectField.findValueByLogin(user.login)) {
    console.warn(issue.id + ': пользователь ' + user.login + ' не входит в набор значений поля «' +
      fieldName + '» проекта ' + issue.project.shortName + ' — поле не заполнено');
    return false;
  }

  try {
    issue.fields[field] = user;
  } catch (e) {
    console.warn(issue.id + ': не удалось записать ' + user.login + ' в поле «' + fieldName + '»: ' + e);
    return false;
  }
  return true;
};

exports.DEVELOPER = DEVELOPER;
exports.TESTER = TESTER;
