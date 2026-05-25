<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="visible" class="warehouse-overlay" @click.self="$emit('close')">
        <div class="warehouse-panel">
          <header class="warehouse-header">
            <div class="warehouse-header-left">
              <h2 class="warehouse-title">图表仓库</h2>
              <span class="warehouse-count">{{ charts.length }} / {{ maxTotal }}</span>
              <span v-if="atLimit" class="warehouse-limit-tag">已达上限</span>
            </div>
            <div class="warehouse-header-right">
              <label class="dev-toggle">
                <input v-model="devModeLocal" type="checkbox" />
                <span>开发者模式</span>
              </label>
              <button type="button" class="btn-close" @click="$emit('close')">
                <el-icon><Close /></el-icon>
              </button>
            </div>
          </header>

          <p class="warehouse-desc">
            仓库最多 {{ maxTotal }} 个图表；分类最多 8 个（5 个 Sheet + 3 个自定义），每类看板最多展示 {{ maxPerCategory }} 个。
          </p>

          <div class="warehouse-filters">
            <button type="button" class="wh-filter-tab" :class="{ active: filterCategoryId === '' }" @click="filterCategoryId = ''">全部分类</button>
            <button v-for="cat in categories" :key="cat.id" type="button" class="wh-filter-tab" :class="{ active: filterCategoryId === cat.id }" @click="filterCategoryId = cat.id">{{ cat.name }}</button>
          </div>
          <div v-if="filteredCharts.length === 0" class="warehouse-empty">暂无图表</div>
          <div v-else class="warehouse-grid">
            <div
              v-for="chart in filteredCharts"
              :key="chart.id"
              class="warehouse-card"
              :class="{ 'warehouse-card--on-board': chart.onBoard }"
            >
              <div class="warehouse-card__top">
                <span class="warehouse-card__cat">{{ categoryName(chart.categoryId) }}</span>
                <span v-if="chart.onBoard" class="badge-on-board">看板中</span>
              </div>
              <h4 class="warehouse-card__title">{{ chart.title }}</h4>
              <p class="warehouse-card__question">{{ chart.question }}</p>

              <div v-if="devModeLocal" class="warehouse-sql">
                <pre>{{ chart.sql }}</pre>
              </div>
              <BIMiniTablePreview v-else :preview="chart.tablePreview" :max-rows="3" />

              <div class="warehouse-card__footer">
                <button type="button" class="btn-sm" @click="openEdit(chart)">编辑</button>
                <button
                  v-if="!chart.onBoard"
                  type="button"
                  class="btn-sm btn-sm--primary"
                  :disabled="!canAddToBoard(chart)"
                  :title="boardDisabledReason(chart)"
                  @click="$emit('add-to-board', chart.id)"
                >
                  添加到看板
                </button>
                <button
                  v-else
                  type="button"
                  class="btn-sm"
                  @click="$emit('remove-from-board', chart.id)"
                >
                  移出看板
                </button>
                <button type="button" class="btn-sm btn-sm--danger" @click="$emit('delete', chart.id)">
                  删除
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <transition name="modal-fade">
      <div v-if="editVisible" class="edit-overlay" @click.self="closeEdit">
        <div class="edit-panel">
          <header class="edit-header">
            <h3 class="edit-title">编辑图表</h3>
            <button type="button" class="btn-close" @click="closeEdit">
              <el-icon><Close /></el-icon>
            </button>
          </header>
          <form class="edit-form" @submit.prevent="submitEdit">
            <label class="edit-field">
              <span class="edit-label">标题</span>
              <input
                v-model.trim="editForm.title"
                type="text"
                class="edit-input"
                maxlength="80"
                placeholder="图表标题"
                required
              />
            </label>
            <label class="edit-field">
              <span class="edit-label">说明</span>
              <textarea
                v-model.trim="editForm.description"
                class="edit-input edit-textarea"
                maxlength="500"
                rows="3"
                placeholder="业务问题或图表说明"
              />
            </label>
            <label class="edit-field">
              <span class="edit-label">分类</span>
              <select v-model="editForm.categoryId" class="edit-input edit-select" required>
                <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
              </select>
            </label>
            <div class="edit-footer">
              <button type="button" class="btn-edit btn-edit--secondary" :disabled="savingEdit" @click="closeEdit">
                取消
              </button>
              <button type="submit" class="btn-edit btn-edit--primary" :disabled="savingEdit || !canSubmitEdit">
                {{ savingEdit ? '保存中…' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import type { BIChartItem, BICategory } from '../../mocks/biInsightsMock'
import { BI_MAX_BOARD_PER_CATEGORY, BI_MAX_WAREHOUSE_TOTAL } from '../../mocks/biInsightsMock'
import { updateBIChart } from '../../api'
import BIMiniTablePreview from './BIMiniTablePreview.vue'

const props = defineProps<{
  visible: boolean
  fileId: string
  charts: BIChartItem[]
  categories: BICategory[]
  devMode: boolean
  demoMode?: boolean
  boardCountByCategory: Record<string, number>
}>()

export interface BIChartEditPayload {
  id: string
  title: string
  description: string
  categoryId: string
}

const emit = defineEmits<{
  close: []
  delete: [id: string]
  'add-to-board': [id: string]
  'remove-from-board': [id: string]
  'chart-updated': [payload: BIChartEditPayload]
  'update:devMode': [value: boolean]
}>()

const devModeLocal = computed({
  get: () => props.devMode,
  set: (v: boolean) => emit('update:devMode', v)
})

const maxTotal = BI_MAX_WAREHOUSE_TOTAL
const maxPerCategory = BI_MAX_BOARD_PER_CATEGORY
const atLimit = computed(() => props.charts.length >= maxTotal)
const filterCategoryId = ref('')

const filteredCharts = computed(() => {
  if (!filterCategoryId.value) return props.charts
  return props.charts.filter((c) => c.categoryId === filterCategoryId.value)
})

const categoryMap = computed(() =>
  Object.fromEntries(props.categories.map((c) => [c.id, c.name]))
)

function categoryName(id: string) {
  return categoryMap.value[id] || id
}

function canAddToBoard(chart: BIChartItem) {
  const count = props.boardCountByCategory[chart.categoryId] || 0
  return count < maxPerCategory
}

function boardDisabledReason(chart: BIChartItem) {
  if (canAddToBoard(chart)) return ''
  return `该分类看板已满（最多 ${maxPerCategory} 个）`
}

const editVisible = ref(false)
const savingEdit = ref(false)
const editingChartId = ref('')
const editForm = reactive({
  title: '',
  description: '',
  categoryId: ''
})

const canSubmitEdit = computed(
  () => !!editForm.title.trim() && !!editForm.categoryId
)

function openEdit(chart: BIChartItem) {
  editingChartId.value = chart.id
  editForm.title = chart.title
  editForm.description = chart.question
  editForm.categoryId = chart.categoryId
  editVisible.value = true
}

function closeEdit() {
  if (savingEdit.value) return
  editVisible.value = false
  editingChartId.value = ''
}

async function submitEdit() {
  if (!canSubmitEdit.value || !editingChartId.value || (!props.fileId && !props.demoMode)) return
  const payload: BIChartEditPayload = {
    id: editingChartId.value,
    title: editForm.title.trim(),
    description: editForm.description.trim(),
    categoryId: editForm.categoryId
  }
  savingEdit.value = true
  try {
    if (!props.demoMode) {
      await updateBIChart(props.fileId, payload.id, {
        title: payload.title,
        description: payload.description,
        category_id: payload.categoryId
      })
    }
    emit('chart-updated', payload)
    editVisible.value = false
    editingChartId.value = ''
    ElMessage.success('已保存')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '保存失败')
  } finally {
    savingEdit.value = false
  }
}
</script>

<style scoped>
.warehouse-overlay {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(28, 25, 23, 0.35);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.warehouse-panel {
  width: min(1080px, 96vw);
  max-height: min(88vh, 900px);
  display: flex;
  flex-direction: column;
  background: #FAF8F5;
  border: 1px solid #E5E0D8;
  border-radius: 20px;
  box-shadow: 0 8px 40px rgba(28, 25, 23, 0.12);
  overflow: hidden;
}

.warehouse-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 12px;
  flex-shrink: 0;
}

.warehouse-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.warehouse-title {
  font-size: 18px;
  font-weight: 600;
  color: #1C1917;
  margin: 0;
}

.warehouse-count {
  font-size: 12px;
  color: #736C64;
  padding: 2px 8px;
  background: #fff;
  border: 1px solid #E5E0D8;
  border-radius: 20px;
}

.warehouse-limit-tag {
  font-size: 11px;
  color: #B45309;
  background: rgba(255, 149, 0, 0.1);
  padding: 2px 8px;
  border-radius: 6px;
}

.warehouse-header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.dev-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #736C64;
  cursor: pointer;
  user-select: none;
}

.dev-toggle input {
  accent-color: #D97757;
}

.btn-close {
  width: 36px;
  height: 36px;
  border: 1px solid #E5E0D8;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #736C64;
}

.warehouse-desc {
  padding: 0 24px 12px;
  margin: 0;
  font-size: 13px;
  color: #A39E96;
  line-height: 1.5;
  flex-shrink: 0;
}

.warehouse-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 24px 16px;
  flex-shrink: 0;
}

.wh-filter-tab {
  height: 32px;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  color: #736C64;
  background: #fff;
  border: 1px solid #E5E0D8;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.wh-filter-tab:hover {
  border-color: #D4CEC4;
  color: #1C1917;
}

.wh-filter-tab.active {
  background: rgba(217, 119, 87, 0.12);
  border-color: rgba(217, 119, 87, 0.4);
  color: #C6613F;
}

.warehouse-empty {
  padding: 48px;
  text-align: center;
  color: #A39E96;
}

.warehouse-grid {
  flex: 1;
  overflow-y: auto;
  padding: 0 24px 24px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  align-content: start;
}

.warehouse-card {
  background: #fff;
  border: 1px solid #E5E0D8;
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.warehouse-card--on-board {
  border-color: rgba(217, 119, 87, 0.45);
  box-shadow: 0 0 0 1px rgba(217, 119, 87, 0.12);
}

.warehouse-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.warehouse-card__cat {
  font-size: 11px;
  color: #736C64;
  font-weight: 500;
}

.badge-on-board {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(217, 119, 87, 0.12);
  color: #C6613F;
  font-weight: 500;
}

.warehouse-card__title {
  font-size: 14px;
  font-weight: 600;
  color: #1C1917;
  margin: 0;
}

.warehouse-card__question {
  font-size: 12px;
  color: #736C64;
  line-height: 1.45;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.warehouse-sql {
  flex: 1;
  min-height: 80px;
  max-height: 120px;
  overflow: auto;
  background: #1C1917;
  border-radius: 8px;
  padding: 10px;
}

.warehouse-sql pre {
  margin: 0;
  font-size: 10px;
  line-height: 1.5;
  color: #E7E5E4;
  font-family: 'SF Mono', Menlo, monospace;
  white-space: pre-wrap;
  word-break: break-all;
}

.warehouse-card__footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.btn-sm {
  flex: 1 1 calc(50% - 4px);
  min-width: 72px;
  height: 30px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid #E5E0D8;
  border-radius: 8px;
  background: #fff;
  color: #1C1917;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-sm:hover:not(:disabled) {
  border-color: #D4CEC4;
  background: #FAF8F5;
}

.btn-sm:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-sm--primary {
  background: #D97757;
  border-color: #D97757;
  color: #fff;
}

.btn-sm--primary:hover:not(:disabled) {
  background: #C6613F;
  border-color: #C6613F;
}

.btn-sm--danger:hover {
  border-color: rgba(255, 59, 48, 0.4);
  color: #FF3B30;
}

.edit-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(28, 25, 23, 0.45);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.edit-panel {
  width: min(420px, 92vw);
  background: #fff;
  border: 1px solid #E5E0D8;
  border-radius: 16px;
  box-shadow: 0 8px 40px rgba(28, 25, 23, 0.14);
  overflow: hidden;
}

.edit-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 8px;
}

.edit-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1C1917;
}

.edit-form {
  padding: 8px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.edit-label {
  font-size: 13px;
  font-weight: 500;
  color: #1C1917;
}

.edit-input {
  width: 100%;
  box-sizing: border-box;
  font-size: 14px;
  font-family: inherit;
  color: #1C1917;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  padding: 8px 12px;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.edit-input:focus {
  border-color: #D97757;
  box-shadow: 0 0 0 3px rgba(217, 119, 87, 0.15);
}

.edit-textarea {
  resize: vertical;
  min-height: 72px;
  line-height: 1.5;
}

.edit-select {
  cursor: pointer;
}

.edit-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}

.btn-edit {
  height: 32px;
  padding: 0 16px;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-edit:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-edit--secondary {
  background: #fff;
  border: 1px solid #E5E0D8;
  color: #1C1917;
}

.btn-edit--secondary:hover:not(:disabled) {
  background: #FAF8F5;
}

.btn-edit--primary {
  background: #D97757;
  border: 1px solid #D97757;
  color: #fff;
}

.btn-edit--primary:hover:not(:disabled) {
  background: #C6613F;
  border-color: #C6613F;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.25s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
