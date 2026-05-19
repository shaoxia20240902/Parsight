<template>
  <nav class="admin-nav">
    <div class="nav-header">
      <div class="nav-header__icon">
        <el-icon><Setting /></el-icon>
      </div>
      <span class="nav-header__title">管理后台</span>
    </div>

    <div class="nav-section">
      <div class="nav-section__label">系统管理</div>
      <div class="nav-items">
        <router-link
          to="/admin"
          class="nav-item"
          :class="{ active: route.path === '/admin' }"
        >
          <span class="nav-item__icon">
            <el-icon><User /></el-icon>
          </span>
          <span class="nav-item__text">用户管理</span>
        </router-link>

        <router-link
          to="/admin/spaces"
          class="nav-item"
          :class="{ active: route.path === '/admin/spaces' }"
        >
          <span class="nav-item__icon">
            <el-icon><OfficeBuilding /></el-icon>
          </span>
          <span class="nav-item__text">空间管理</span>
        </router-link>

        <router-link
          to="/admin/logs"
          class="nav-item"
          :class="{ active: route.path.startsWith('/admin/logs') }"
        >
          <span class="nav-item__icon">
            <el-icon><Tickets /></el-icon>
          </span>
          <span class="nav-item__text">日志中心</span>
        </router-link>

        <router-link
          to="/admin/llm-config"
          class="nav-item"
          :class="{ active: route.path === '/admin/llm-config' }"
        >
          <span class="nav-item__icon">
            <el-icon><Cpu /></el-icon>
          </span>
          <span class="nav-item__text">模型配置</span>
        </router-link>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { User, Tickets, Cpu, Setting, OfficeBuilding } from '@element-plus/icons-vue'

const route = useRoute()
</script>

<style scoped>
.admin-nav {
  --nav-accent: #C6613F;
  --nav-accent-soft: rgba(198, 97, 63, 0.1);
  --nav-accent-hover: rgba(198, 97, 63, 0.06);
  --nav-bg: #FAF8F5;
  --nav-text: #1C1917;
  --nav-muted: #736C64;
  --nav-faint: #A39E96;
  --nav-border: #E5E0D8;

  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 12px;
  height: 100%;
  box-sizing: border-box;
}

/* Header */
.nav-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px 16px;
  margin-bottom: 4px;
  border-bottom: 1px solid var(--nav-border);
}

.nav-header__icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: var(--nav-accent-soft);
  color: var(--nav-accent);
  font-size: 16px;
}

.nav-header__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--nav-text);
  letter-spacing: -0.01em;
}

/* Section */
.nav-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-section__label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--nav-faint);
  padding: 8px 10px 4px;
}

.nav-items {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* Nav Item */
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  margin: 0;
  border-radius: 10px;
  color: var(--nav-muted);
  font-size: 13px;
  font-weight: 450;
  text-decoration: none;
  transition: all 0.18s ease;
  cursor: pointer;
  border: 1.5px solid transparent;
}

.nav-item:hover {
  background: var(--nav-accent-hover);
  color: var(--nav-text);
}

.nav-item.active {
  background: var(--nav-accent-soft);
  border-color: rgba(198, 97, 63, 0.18);
  color: var(--nav-accent);
  font-weight: 600;
}

.nav-item__icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 15px;
  transition: all 0.18s ease;
}

.nav-item.active .nav-item__icon {
  background: rgba(198, 97, 63, 0.12);
}

.nav-item__text {
  line-height: 1.3;
}
</style>
