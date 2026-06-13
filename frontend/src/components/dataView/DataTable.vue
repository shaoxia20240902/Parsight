<template>
  <div class="table-card">
    <div class="table-card-header">
      <h2 class="table-card-title">{{ sheetName }}</h2>
      <span class="table-card-count">共 {{ total }} 条</span>
    </div>
    <div class="table-wrap">
      <el-table
        v-loading="loading"
        :data="rows"
        stripe
        element-loading-text="加载中..."
        class="apple-table"
        height="100%"
      >
        <el-table-column
          v-for="col in columns"
          :key="col.name"
          :prop="col.name"
          :label="col.name"
          :min-width="140"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <span :class="{ 'cell-num': col.type === 'number' }">
              {{ formatCell(row[col.name], col.type) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <div class="table-footer">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        small
        @update:current-page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
interface Column {
  name: string
  type?: string
}

const props = defineProps<{
  rows: any[]
  columns: Column[]
  total: number
  page: number
  pageSize: number
  loading: boolean
  sheetName: string
}>()

const emit = defineEmits<{
  change: [page: number, pageSize: number]
}>()

function formatCell(val: any, type?: string) {
  if (val === null || val === undefined) return '-'
  if (type === 'number' && typeof val === 'number') {
    return val.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  }
  return String(val)
}

function onPageChange(nextPage: number) {
  emit('change', nextPage, props.pageSize)
}

function onPageSizeChange(nextSize: number) {
  emit('change', props.page, nextSize)
}
</script>

<style scoped>
.table-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: transparent;
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.table-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--dv-border);
  flex-shrink: 0;
}

.table-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--dv-text);
  letter-spacing: -0.01em;
}

.table-card-count {
  font-size: 12px;
  color: var(--dv-faint);
}

.table-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.table-footer {
  padding: 10px 16px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--dv-border);
  flex-shrink: 0;
}

.cell-num {
  font-family: var(--font-mono);
  font-size: var(--text-base);
}

:deep(.el-table) {
  --el-table-border-color: transparent;
  --el-table-row-hover-bg-color: var(--dv-accent-soft);
  --el-table-header-bg-color: var(--dv-surface-muted);
  font-size: 13px;
}

:deep(.el-table__header th) {
  background: var(--dv-surface-muted) !important;
  color: var(--dv-muted);
  font-weight: 500;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--dv-border) !important;
  padding: 10px 14px;
}

:deep(.el-table__body td) {
  padding: 10px 14px;
  color: var(--dv-text);
  border-bottom: 1px solid #F0EDE8;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: #FAF8F5;
}

:deep(.el-table__body tr:last-child td) {
  border-bottom: none;
}

:deep(.el-pagination) {
  --el-pagination-hover-color: var(--dv-accent);
  --el-pagination-button-color: var(--dv-muted);
}
</style>
