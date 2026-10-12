const config = require('./config');

const DEVELOPER = 'developer';
const TESTER = 'tester';

function inAnyGroup(user, groups) {
  return groups.some(function (group) {
    return user.isInGroup(group);
  });
}

function byName(value, names) {
  return !!value && names.indexOf(value.name) !== -1;
}

function roleByGroup(user) {
  const isDev = inAnyGroup(user, config.DEVELOPER_GROUPS);
  const isQa = inAnyGroup(user, config.TESTER_GROUPS);
  if (isDev && !isQa) return DEVELOPER;
  if (isQa && !isDev) return TESTER;
  return null; // ни в одной группе или в обеих — решаем по контексту
}

function roleByState(state) {
  if (byName(state, config.DEVELOPER_STATES)) return DEVELOPER;
  if (byName(state, config.TESTER_STATES)) return TESTER;
  return null;
}

function roleByWorkType(type) {
  if (byName(type, config.DEVELOPER_WORK_TYPES)) return DEVELOPER;
  if (byName(type, config.TESTER_WORK_TYPES)) return TESTER;
  return null;
}

/**
 * Определяет роль пользователя в задаче.
 * Порядок: группа пользователя -> тип работы (для списания времени) -> состояние задачи.
 */
exports.detectRole = function (user, state, workType) {
  return roleByGroup(user) || roleByWorkType(workType) || roleByState(state);
};

/**
 * Записывает пользователя в поле, соответствующее роли.
 * overwrite=false — только если поле пустое.
 */
exports.applyRole = function (issue, role, user, overwrite) {
  const field = role === DEVELOPER ? 'Developer' : role === TESTER ? 'Tester' : null;
  if (!field) return false;

  const current = issue.fields[field];
  if (current && (!overwrite || current.login === user.login)) return false;

  issue.fields[field] = user;
  return true;
};

exports.DEVELOPER = DEVELOPER;
exports.TESTER = TESTER;
