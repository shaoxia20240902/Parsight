/* eslint-env node */
require('@rushstack/eslint-patch/modern-module-resolution')

module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: [
    'plugin:vue/vue3-recommended',
    'eslint:recommended',
    '@vue/eslint-config-typescript',
    'prettier',
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  rules: {
    'vue/multi-word-component-names': 'off',
    '@typescript-eslint/no-explicit-any': 'warn',
    // 以下规则先以 warning 引入，避免已有代码阻塞 lint；后续逐步收紧为 error
    'no-async-promise-executor': 'warn',
    'no-constant-condition': 'warn',
    'vue/no-ref-as-operand': 'warn',
  },
}
