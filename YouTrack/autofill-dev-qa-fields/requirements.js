const entities = require('@jetbrains/youtrack-scripting-api/entities');
const config = require('./config');

// Общие требования к проекту для всех правил пакета.
exports.requirements = {
  Assignee: {
    type: entities.User.fieldType
  },
  State: {
    type: entities.State.fieldType,
    name: config.STATE_FIELD
  },
  Developer: {
    type: entities.User.fieldType,
    name: config.DEVELOPER_FIELD
  },
  Tester: {
    type: entities.User.fieldType,
    name: config.TESTER_FIELD
  }
};
