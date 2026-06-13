<template>
  <aside class="table-sidebar">
    <div class="sidebar-label">数据表</div>
    <div v-if="loading" class="sidebar-loading">
      <div v-for="i in 3" :key="i" class="skeleton-line"></div>
    </div>
    <div v-else-if="tables.length === 0" class="sidebar-empty">
      <p>暂无数据表</p>
      <p class="sidebar-empty-desc">上传 XLSX 文件开始</p>
    </div>
    <template v-else>
      <div class="table-list-scroll">
        <div class="table-list">
          <div
            v-for="t in tables"
            :key="t.table_name"
            :class="{ active: !relationsActive && activeTable === t.table_name }"
            class="table-list-item"
            @click="$emit('select', t)"
          >
            <div class="table-item-name">{{ t.sheet_name }}</div>
            <div class="table-item-meta">{{ t.row_count }} 行 · {{ (t.columns || []).length }} 列</div>
          </div>
        </div>
      </div>
      <button
        type="button"
        class="relations-summary-btn"
        :class="{ active: relationsActive }"
        @click="$emit('relations')"
      >
        <el-icon class="relations-summary-icon"><Connection /></el-icon>
        关联总结
      </button>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { Connection } from '@element-plus/icons-vue'

defineProps<{
  tables: any[]
  loading: boolean
  activeTable: string
  relationsActive: boolean
}>()

defineEmits<{
  select: [table: any]
  relations: []
}>()
</script>

<style scoped>
.table-sidebar {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--dv-surface);
  border: 1px solid var(--dv-border);
  border-radius: 12px;
  box-shadow: none;
  padding: 12px;
  min-height: 0;
  overflow: hidden;
}

.table-list-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin-bottom: var(--spacing-sm);
}

.relations-summary-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 36px;
  margin-top: auto;
  flex-shrink: 0;
  border: 1px solid rgba(217, 119, 87, 0.35);
  border-radius: 10px;
  background: var(--dv-accent-soft);
  color: var(--dv-accent);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
}

.relations-summary-btn:hover {
  background: rgba(217, 119, 87, 0.18);
  border-color: rgba(217, 119, 87, 0.5);
}

.relations-summary-btn.active {
  background: var(--dv-accent);
  border-color: var(--dv-accent);
  color: #fff;
}

.relations-summary-icon {
  font-size: 16px;
}

.sidebar-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--dv-faint);
  margin-bottom: 8px;
  padding: 0 4px;
}

.sidebar-loading,
.sidebar-empty {
  padding: var(--spacing-base) var(--spacing-xs);
}

.sidebar-empty-desc {
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
  margin-top: var(--spacing-xs);
}

.table-list {
  display: flex;
  flex-direction: column;
}

.table-list-item {
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s var(--ease-out);
}

.table-list-item:hover {
  background: var(--dv-hover);
}

.table-list-item.active {
  background: var(--dv-accent-soft);
}

.table-item-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--dv-text);
  line-height: 1.4;
}

.table-list-item.active .table-item-name {
  color: var(--dv-accent);
}

.table-item-meta {
  font-size: 11px;
  color: var(--dv-faint);
  margin-top: 2px;
}

.skeleton-line {
  height: var(--spacing-md);
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-sm);
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { opacity: 0.5; }
  50% { opacity: 1; }
  100% { opacity: 0.5; }
}
</style>
