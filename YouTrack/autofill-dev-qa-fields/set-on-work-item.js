const entities = require('@jetbrains/youtrack-scripting-api/entities');
const roles = require('./roles');

exports.rule = entities.Issue.onChange({
  title: 'Заполнить Разработчика / Тестировщика по списанному времени, если поле пустое',
  guard: function (ctx) {
    const issue = ctx.issue;
    return issue.isReported && issue.workItems.added.isNotEmpty() && !roles.bothFilled(issue);
  },
  action: function (ctx) {
    const issue = ctx.issue;
    issue.workItems.added.forEach(function (workItem) {
      const author = workItem.author;
      if (!author) return;
      roles.matchingRoles(author, issue.fields.State, workItem.type, issue.project).forEach(function (role) {
        roles.applyRole(issue, role, author);
      });
    });
  },
  requirements: require('./requirements').requirements
});
