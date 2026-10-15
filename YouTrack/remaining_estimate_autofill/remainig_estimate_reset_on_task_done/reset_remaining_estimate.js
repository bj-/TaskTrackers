/**
 * This is a template for an on-change rule. This rule defines what
 * happens when a change is applied to an issue.
 *
 * For details, read the Quick Start Guide:
 * https://www.jetbrains.com/help/youtrack/devportal/Quick-Start-Guide-Workflows-JS.html
 */

const entities = require('@jetbrains/youtrack-scripting-api/entities');
const dateTime = require('@jetbrains/youtrack-scripting-api/date-time');

exports.rule = entities.Issue.onChange({
  title: 'Обнулять Remaining при переходе в Готово',
  
  // Условие срабатывания (Guard)
  guard: (ctx) => {
    // Проверяем, что статус задачи изменился именно на "Готово"
    //return ctx.issue.State.becomes(ctx.State.Done);
    const issue = ctx.issue;
    // Проверяем, что поле State (Статус) изменилось и задача перешла в состояние "Решена" (Resolved)
    //console.log("dd");
    return issue.fields.isChanged(ctx.State) && issue.isResolved;
  },
  
  // Действие (Action)
  action: (ctx) => {

    // Обнуляем поле Remaining
    ctx.issue.fields.Remaining = dateTime.toPeriod(0);
    
    // Опционально: можно добавить комментарий, что время сброшено
    // ctx.issue.comments.add('Автоматическое обнуление остатка времени при переходе в Готово');
  },
  
  // Требования (Тут мы описываем, какие поля и состояния нужны правилу)
  requirements: {
    ///*
    State: {
      type: entities.State.fieldType
    },
    //*/
    Remaining: {
      type: entities.Field.periodType,
      // ВАЖНО: Укажите точное название поля из настроек YouTrack!
      // Например: name: 'Осталось' или name: 'Оставшееся время'
      name: 'Remaining' 
    }
    
  }
});