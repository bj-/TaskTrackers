const entities = require('@jetbrains/youtrack-scripting-api/entities');
const roles = require('./roles');

exports.rule = entities.Issue.onChange({
  title: 'Заполнить Разработчика / Тестировщика при назначении исполнителя, если поле пустое',
  guard: function (ctx) {
    const issue = ctx.issue;
    if (!issue.fields.Assignee || roles.bothFilled(issue)) return false;
    // Назначение на уже существующей задаче или задача создаётся сразу с исполнителем.
    return issue.becomesReported ||
      (issue.isReported && issue.fields.isChanged(ctx.Assignee));
  },
  action: function (ctx) {
    const issue = ctx.issue;
    const assignee = issue.fields.Assignee;
    // Берём новое значение State — состояние могло поменяться в той же транзакции.
    roles.matchingRoles(assignee, issue.fields.State, null, issue.project).forEach(function (role) {
      roles.applyRole(issue, role, assignee);
    });
  },
  requirements: require('./requirements').requirements
});
