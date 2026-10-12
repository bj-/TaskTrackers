const entities = require('@jetbrains/youtrack-scripting-api/entities');
const config = require('./config');
const roles = require('./roles');

exports.rule = entities.Issue.onChange({
  title: 'Заполнить Разработчика / Тестировщика при назначении исполнителя',
  guard: function (ctx) {
    const issue = ctx.issue;
    if (!issue.fields.Assignee) return false;
    // Назначение на уже существующей задаче или задача создаётся сразу с исполнителем.
    return issue.becomesReported ||
      (issue.isReported && issue.fields.isChanged(ctx.Assignee));
  },
  action: function (ctx) {
    const issue = ctx.issue;
    const assignee = issue.fields.Assignee;
    // Берём новое значение State — состояние могло поменяться в той же транзакции.
    const role = roles.detectRole(assignee, issue.fields.State, null);
    roles.applyRole(issue, role, assignee, config.OVERWRITE_ON_ASSIGN);
  },
  requirements: require('./requirements').requirements
});
