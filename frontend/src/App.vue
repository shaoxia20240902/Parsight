<template>
  <el-config-provider :locale="zhCn">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
</script>

<style>
:root {
  /* 色彩 */
  --color-primary: #007AFF;
  --color-primary-hover: #3395FF;
  --color-primary-active: #0062CC;
  --color-success: #34C759;
  --color-warning: #FF9500;
  --color-danger: #FF3B30;
  --color-info: #5AC8FA;

  --color-text-primary: #1D1D1F;
  --color-text-secondary: #6E6E73;
  --color-text-tertiary: #AEAEB2;
  --color-separator: #E5E5EA;
  --color-bg: #F5F5F7;
  --color-white: #FFFFFF;

  /* 毛玻璃 */
  --glass-bg: rgba(255, 255, 255, 0.72);
  --glass-border: rgba(255, 255, 255, 0.3);
  --glass-blur: blur(20px) saturate(180%);

  /* 间距 */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 12px;
  --spacing-base: 16px;
  --spacing-lg: 20px;
  --spacing-xl: 24px;
  --spacing-2xl: 32px;
  --spacing-3xl: 48px;

  /* 圆角 */
  --radius-sm: 4px;
  --radius-base: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-full: 9999px;

  /* 阴影 */
  --shadow-card: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.06);
  --shadow-card-hover: 0 2px 6px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.08);
  --shadow-modal: 0 4px 12px rgba(0,0,0,0.08), 0 16px 48px rgba(0,0,0,0.12);
  --shadow-xs: 0 1px 2px rgba(0,0,0,0.04);

  /* 字体 */
  --font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display',
                 'Helvetica Neue', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-mono: 'SF Mono', 'Menlo', 'Consolas', monospace;

  /* 字号 */
  --text-xs: 11px;
  --text-sm: 12px;
  --text-base: 14px;
  --text-lg: 16px;
  --text-xl: 18px;
  --text-2xl: 24px;
  --text-3xl: 32px;

  /* 动画 */
  --ease-out: cubic-bezier(0.25, 0.1, 0.25, 1);
  --ease-in-out: cubic-bezier(0.42, 0, 0.58, 1);
  --transition-fast: 0.15s var(--ease-out);
  --transition-normal: 0.25s var(--ease-out);

  /* Element Plus 颜色覆盖 */
  --el-color-primary: #007AFF;
  --el-color-primary-light-3: #3395FF;
  --el-color-primary-light-5: #66B0FF;
  --el-color-primary-light-7: #99CCFF;
  --el-color-primary-light-9: #CCE5FF;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-family);
  background-color: var(--color-bg);
  color: var(--color-text-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>
