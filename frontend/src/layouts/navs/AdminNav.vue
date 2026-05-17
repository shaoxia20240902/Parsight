<template>
  <nav class="side-nav">
    <div class="nav-section">
      <div class="nav-label">系统管理</div>
      <router-link to="/admin" class="nav-item" :class="{ active: route.path === '/admin' }">
        <el-icon><User /></el-icon>
        <span>用户管理</span>
      </router-link>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { User } from '@element-plus/icons-vue'

const route = useRoute()
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
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  margin: 2px 0;
  border-radius: var(--radius-base);
  color: var(--color-text-secondary);
  font-size: var(--text-base);
  font-weight: 400;
  text-decoration: none;
  transition: all var(--transition-fast);
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

.nav-item .el-icon {
  font-size: 16px;
}
</style>
