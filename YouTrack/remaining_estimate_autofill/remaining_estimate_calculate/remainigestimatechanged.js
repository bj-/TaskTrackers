/**
 * This is a template for an on-change rule. This rule defines what
 * happens when a change is applied to an issue.
 *
 * For details, read the Quick Start Guide:
 * https://www.jetbrains.com/help/youtrack/devportal/Quick-Start-Guide-Workflows-JS.html
 */

const entities = require('@jetbrains/youtrack-scripting-api/entities');
const dateTime = require('@jetbrains/youtrack-scripting-api/date-time');

// Вспомогательная функция для конвертации объекта Period в минуты
function periodToMinutes(period) {
  if (!period) {
    return 0;
  }
  const WORKDAYS_PER_WEEK = 5;
  const HOURS_PER_DAY = 8;

  return period.getMinutes() +
      60 * (period.getHours() +
          HOURS_PER_DAY * (period.getDays() +
              WORKDAYS_PER_WEEK * period.getWeeks()));
}

exports.rule = entities.Issue.onChange({
  title: 'Calculate remaining time with delta logic',
  
  guard: (ctx) => {
    const issue = ctx.issue;
    return issue.fields.isChanged(ctx.Estimation) || issue.fields.isChanged(ctx.SpentTime);
  },
  
  action: (ctx) => {
    const issue = ctx.issue;
    const isSpentChanged = issue.fields.isChanged(ctx.SpentTime);
    const isEstimationChanged = issue.fields.isChanged(ctx.Estimation);

    // 1. ЛОГИКА ПРИ ТРЕКИНГЕ ВРЕМЕНИ (изменение SpentTime)
    if (isSpentChanged) {
      const oldSpentMin = periodToMinutes(issue.fields.oldValue(ctx.SpentTime));
      const newSpentMin = periodToMinutes(issue.fields.SpentTime);
      const deltaSpentMin = newSpentMin - oldSpentMin; // Положительное при добавлении, отрицательное при удалении

      if (deltaSpentMin !== 0) {
        let newRemainingMin;

        if (issue.fields.Remaining) {
          // Сценарий А: Remaining не пустое. Вычитаем дельту из уже имеющегося значения.
          // Это сохраняет ручные правки поля Remaining, сделанные пользователем ранее.
          const currentRemainingMin = periodToMinutes(issue.fields.Remaining);
          newRemainingMin = currentRemainingMin - deltaSpentMin;
        } else {
          // Сценарий Б: Remaining пустое. Вычисляем из Оценки минус текущее затраченное.
          const estimationMin = periodToMinutes(issue.fields.Estimation);
          newRemainingMin = estimationMin - newSpentMin;
        }

        // Не допускаем отрицательных значений
        if (newRemainingMin < 0) {
          newRemainingMin = 0;
        }

        // Записываем результат (null если 0)
        //issue.fields.Remaining = newRemainingMin === 0 ? 0 : dateTime.toPeriod(newRemainingMin * 60 * 1000);
        issue.fields.Remaining = dateTime.toPeriod(newRemainingMin * 60 * 1000);
      }
    } 
    // 2. ЛОГИКА ПРИ ИЗМЕНЕНИИ ОЦЕНКИ (чтобы поле не рассинхронизировалось)
    else if (isEstimationChanged) {
      const oldEstMin = periodToMinutes(issue.fields.oldValue(ctx.Estimation));
      const newEstMin = periodToMinutes(issue.fields.Estimation);
      const deltaEstMin = newEstMin - oldEstMin;

      if (deltaEstMin !== 0) {
        let newRemainingMin;
        
        if (issue.fields.Remaining) {
          // Корректируем существующее Remaining на величину изменения оценки
          const currentRemainingMin = periodToMinutes(issue.fields.Remaining);
          newRemainingMin = currentRemainingMin + deltaEstMin;
        } else {
          // Если Remaining было пустым, инициализируем его на основе новой оценки
          const spentMin = periodToMinutes(issue.fields.SpentTime);
          newRemainingMin = newEstMin - spentMin;
        }

        // Если результат <= 0, устанавливаем в 0
        if (newRemainingMin <= 0) {
          newRemainingMin = 0;
        }

        //issue.fields.Remaining = newRemainingMin === 0 ? null : dateTime.toPeriod(newRemainingMin * 60 * 1000);
        // Всегда записываем значение (включая 0)
        issue.fields.Remaining = dateTime.toPeriod(newRemainingMin * 60 * 1000);        
      }
    }
  },
  
  requirements: {
    Estimation: {
      type: entities.Field.periodType,
      name: 'Оценка' // Точное имя поля в вашем YouTrack
    },
    SpentTime: {
      type: entities.Field.periodType,
      name: 'Затраченное время' // Точное имя поля в вашем YouTrack
    },
    Remaining: {
      type: entities.Field.periodType,
      // ВАЖНО: Укажите точное название поля из настроек YouTrack!
      // Например: name: 'Осталось' или name: 'Оставшееся время'
      name: 'Remaining' 
    }
  }
});