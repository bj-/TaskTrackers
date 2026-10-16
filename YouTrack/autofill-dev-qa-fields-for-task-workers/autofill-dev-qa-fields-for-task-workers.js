
const entities = require('@jetbrains/youtrack-scripting-api/entities');

exports.rule = entities.Issue.onChange({
  title: 'Track developers and testers',

  guard: function(ctx) {
    var issue = ctx.issue;

    // Добавлен комментарий или work item.
    if (issue.comments.added.isNotEmpty() ||
        issue.workItems.added.isNotEmpty()) {
      return true;
    }

    // Только выбранные изменения задачи.
    return issue.isChanged('summary') ||
      issue.isChanged('description') ||
      issue.isChanged('Assignee') ||
      issue.isChanged('State');
  },

  action: function(ctx) {
    var issue = ctx.issue;
    var user = ctx.currentUser;

    if (!user) {
      return;
    }

    // Разработчик: добавить инициатора, если он состоит в группе.
    if (user.isInGroup('Developers')) {
      issue.fields.DevelopersField.add(user);
    }

    // Тестировщик: пользователь может принадлежать обеим группам.
    if (user.isInGroup('Testers')) {
      issue.fields.TestersField.add(user);
    }
  },

  requirements: {
    DevelopersField: {
      type: entities.User.fieldType,
      name: 'Разработчик',
      multi: true
    },
    TestersField: {
      type: entities.User.fieldType,
      name: 'Тестировщик',
      multi: true
    }
  }
});
