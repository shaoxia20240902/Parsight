<template>
  <nav class="side-nav">
    <div class="nav-section">
      <div class="nav-label">数据管理</div>
      <router-link to="/data" class="nav-item" :class="{ active: isActiveExact('/data') }">
        <el-icon class="nav-icon"><Document /></el-icon>
        <span>XLSX 管理</span>
      </router-link>
      <router-link to="/data/relations" class="nav-item" :class="{ active: isActive('/data/relations') }">
        <el-icon class="nav-icon"><Connection /></el-icon>
        <span>XLSX 关联</span>
      </router-link>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { Document, Connection } from '@element-plus/icons-vue'

const route = useRoute()

function isActive(path: string) {
  return route.path.startsWith(path)
}

function isActiveExact(path: string) {
  return route.path === path
}
</script>

<style scoped>
.side-nav {
  padding: var(--spacing-base) 0;
}

.nav-section {
  padding: 0 var(--spacing-md);
}

.nav-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-tertiary);
  padding: var(--spacing-sm) var(--spacing-sm) var(--spacing-xs);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px var(--spacing-md);
  margin: 2px 0;
  border-radius: var(--radius-base);
  color: var(--color-text-secondary);
  font-size: var(--text-base);
  font-weight: 400;
  text-decoration: none;
  transition: all 0.15s var(--ease-out);
}

.nav-item:hover {
  background: rgba(0, 0, 0, 0.04);
  color: var(--color-text-primary);
}

.nav-item.active {
  background: rgba(0, 122, 255, 0.08);
  color: var(--color-primary);
  font-weight: 500;
}

.nav-icon {
  font-size: 18px;
}
</style>
