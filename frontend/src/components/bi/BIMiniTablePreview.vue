<template>
  <div class="mini-table" :class="`mini-table--${layout}`">
    <table>
      <thead>
        <tr>
          <th v-for="col in columns" :key="col">{{ col }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, ri) in displayRows" :key="ri">
          <td v-for="col in columns" :key="col">{{ formatCell(row[col]) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BITablePreview } from '../../mocks/biInsightsMock'

const props = withDefaults(
  defineProps<{
    preview: BITablePreview
    maxRows?: number
    /** board：看板内完整表格宽度 */
    layout?: 'mini' | 'board'
  }>(),
  { maxRows: 4, layout: 'mini' }
)

const columns = computed(() => props.preview.columns)
const displayRows = computed(() => props.preview.rows.slice(0, props.maxRows))

function formatCell(v: string | number | undefined) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return v.toLocaleString('zh-CN')
  return String(v)
}
</script>

<style scoped>
.mini-table {
  overflow: hidden;
  border-radius: 8px;
  border: 1px solid var(--bi-border, #E5E0D8);
  background: #fff;
  font-size: 10px;
}

.mini-table table {
  width: 100%;
  border-collapse: collapse;
}

.mini-table th {
  padding: 4px 6px;
  text-align: left;
  font-weight: 500;
  color: var(--bi-muted, #736C64);
  background: var(--bi-surface-muted, #FAF8F5);
  border-bottom: 1px solid var(--bi-border, #E5E0D8);
  white-space: nowrap;
}

.mini-table td {
  padding: 4px 6px;
  color: var(--bi-text, #1C1917);
  border-bottom: 1px solid #F0EDE8;
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mini-table tr:last-child td {
  border-bottom: none;
}

.mini-table--board {
  font-size: 13px;
}

.mini-table--board table {
  table-layout: fixed;
  width: 100%;
}

.mini-table--board th,
.mini-table--board td {
  padding: 10px 12px;
  max-width: none;
  white-space: normal;
  word-break: break-word;
}
</style>
