const entities = require('@jetbrains/youtrack-scripting-api/entities');
const roles = require('./roles');

exports.rule = entities.Issue.onChange({
  title: 'Заполнить Разработчика / Тестировщика по списанному времени, если поле пустое',
  guard: function (ctx) {
    const issue = ctx.issue;
    return issue.isReported && issue.workItems.added.isNotEmpty();
  },
  action: function (ctx) {
    const issue = ctx.issue;
    issue.workItems.added.forEach(function (workItem) {
      const author = workItem.author;
      if (!author) return;
      const role = roles.detectRole(author, issue.fields.State, workItem.type, issue.project);
      // Только если поле ещё пустое — назначение имеет приоритет над списанием времени.
      roles.applyRole(issue, role, author, false);
    });
  },
  requirements: require('./requirements').requirements
});
