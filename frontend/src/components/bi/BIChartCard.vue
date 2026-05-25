<template>
  <article
    class="chart-card"
    :class="{
      'chart-card--collapsed': chart.collapsed,
      'chart-card--expanded': chart.expanded,
      'chart-card--dragging': isDragging,
      'chart-card--chat-open': chatOpen
    }"
  >
    <header class="chart-card__header">
      <button
        type="button"
        class="chart-card__drag"
        title="拖动排序"
        draggable="true"
        @dragstart="onDragStart"
        @dragend="onDragEnd"
      >
        <el-icon><Rank /></el-icon>
      </button>
      <button
        type="button"
        class="chart-card__collapse"
        :title="chart.collapsed ? '展开' : '收起'"
        @click="$emit('toggle-collapse', chart.id)"
      >
        <el-icon><component :is="chart.collapsed ? ArrowDown : ArrowUp" /></el-icon>
      </button>
      <div class="chart-card__titles">
        <h3 class="chart-card__title">{{ chart.title }}</h3>
        <p class="chart-card__question">{{ chart.question }}</p>
        <p v-if="hasChartFilters" class="chart-card__filter-hint">已启用图表独立筛选（优先于全局）</p>
      </div>
      <div class="chart-card__actions">
        <div class="action-wrap">
          <button
            type="button"
            class="btn-icon btn-icon--chat"
            title="对话修改图表"
            :class="{ 'btn-icon--chat-active': chatOpen }"
            @click.stop="toggleChatDialog"
          >
            <el-icon><ChatDotRound /></el-icon>
          </button>
          <transition name="bubble-fade">
            <div v-if="chatOpen" class="chat-dialog" @click.stop>
              <div class="chat-dialog__header">
                <span class="chat-dialog__title">对话修改图表</span>
                <button type="button" class="chat-dialog__close" aria-label="关闭" @click="chatOpen = false">
                  <el-icon><Close /></el-icon>
                </button>
              </div>
              <p class="chat-dialog__hint">
                用自然语言描述你想如何调整本图，例如图表类型、维度拆分或样式偏好（Mock 演示，暂不请求后端）。
              </p>
              <textarea
                ref="chatInputRef"
                v-model="chatInput"
                class="chat-dialog__input"
                rows="3"
                placeholder="例如：改成堆叠柱状图，按月份展示各区域销售额…"
                @keydown.enter.exact.prevent="sendChat"
              />
              <div class="chat-dialog__footer">
                <button type="button" class="chat-dialog__send" :disabled="!chatInput.trim()" @click="sendChat">
                  发送
                </button>
              </div>
            </div>
          </transition>
        </div>

        <div class="action-wrap">
          <button
            type="button"
            class="btn-icon btn-icon--filter"
            :class="{
              'btn-icon--filter-applied': hasChartFilters,
              'btn-icon--filter-open': filterOpen
            }"
            :title="hasChartFilters ? '本图独立筛选已生效（不跟随全局）' : '图表筛选（未设置时沿用全局）'"
            @click.stop="toggleFilterPanel"
          >
            <el-icon><Filter /></el-icon>
          </button>
          <div v-if="filterOpen" class="filter-panel" @click.stop>
            <p class="filter-panel__title">本图筛选</p>
            <p class="filter-panel__hint">未设置时沿用左侧全局筛选</p>
            <div v-for="f in globalFilterFields" :key="f.field" class="filter-panel__row">
              <label>{{ f.label }}</label>
              <el-select
                :model-value="localFilters[f.field] ?? ''"
                :placeholder="effectivePlaceholder(f)"
                clearable
                size="small"
                @update:model-value="(v: string) => setChartFilter(f.field, v)"
              >
                <el-option v-for="opt in f.options" :key="opt" :label="opt" :value="opt" />
              </el-select>
            </div>
            <button type="button" class="filter-panel__clear" @click="clearChartFilters">清除本图筛选</button>
          </div>
        </div>

        <div class="action-wrap">
          <button
            type="button"
            class="btn-icon"
            :title="chart.expanded ? '恢复半宽' : '通栏放大'"
            @click="$emit('toggle-expand', chart.id)"
          >
            <el-icon><component :is="chart.expanded ? Crop : FullScreen" /></el-icon>
          </button>
        </div>

        <div class="action-wrap">
          <button
            type="button"
            class="btn-icon"
            title="移入仓库"
            @click.stop="openBubble('warehouse')"
          >
            <el-icon><Box /></el-icon>
          </button>
          <transition name="bubble-fade">
            <div v-if="activeBubble === 'warehouse'" class="action-bubble action-bubble--confirm">
              <p>确认移入仓库？图表将从看板移除，仍保留在仓库中。</p>
              <div class="bubble-actions">
                <button type="button" class="bubble-btn" @click="activeBubble = null">取消</button>
                <button type="button" class="bubble-btn bubble-btn--primary" @click="confirmWarehouse">确认</button>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </header>

    <div v-if="!chart.collapsed" class="chart-card__body">
      <BIChartRenderer
        v-if="!['table', 'detail_table'].includes(chart.chartType)"
        :chart="chart"
        :visible="true"
        :expanded="Boolean(chart.expanded)"
        @update-kpi-items="(items) => $emit('update-kpi-items', chart.id, items)"
      />
      <BIMiniTablePreview v-else :preview="chart.tablePreview" :max-rows="6" layout="board" />
    </div>
  </article>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowDown, ArrowUp, Box, ChatDotRound, Filter, Rank, FullScreen, Crop, Close
} from '@element-plus/icons-vue'
import type { BIChartItem, BIGlobalFilterField } from '../../mocks/biInsightsMock'
import BIChartRenderer from './BIChartRenderer.vue'
import BIMiniTablePreview from './BIMiniTablePreview.vue'

const props = defineProps<{
  chart: BIChartItem
  globalFilterFields: BIGlobalFilterField[]
  globalFilterValues: Record<string, string>
  isDragging?: boolean
}>()

const emit = defineEmits<{
  'toggle-collapse': [id: string]
  'toggle-expand': [id: string]
  'move-to-warehouse': [id: string]
  'update-chart-filters': [id: string, filters: Record<string, string>]
  'update-kpi-items': [id: string, items: Array<{ label: string; value_field: string; format?: string }>]
  dragstart: [id: string, event: DragEvent]
  dragend: []
}>()

const activeBubble = ref<'warehouse' | null>(null)
const chatOpen = ref(false)
const chatInput = ref('')
const chatInputRef = ref<HTMLTextAreaElement | null>(null)
const filterOpen = ref(false)
const localFilters = reactive<Record<string, string>>({ ...props.chart.chartFilters })

watch(
  () => props.chart.chartFilters,
  (v) => {
    Object.keys(localFilters).forEach((k) => delete localFilters[k])
    Object.assign(localFilters, v || {})
  },
  { deep: true }
)

const hasChartFilters = computed(() =>
  Object.values(localFilters).some((v) => v !== undefined && v !== null && v !== '')
)

function effectivePlaceholder(f: BIGlobalFilterField) {
  const global = props.globalFilterValues[f.field]
  if (global) return `全局：${global}`
  return `选择${f.label}`
}

function setChartFilter(field: string, value: string) {
  if (value) localFilters[field] = value
  else delete localFilters[field]
  emit('update-chart-filters', props.chart.id, { ...localFilters })
}

function clearChartFilters() {
  Object.keys(localFilters).forEach((k) => delete localFilters[k])
  emit('update-chart-filters', props.chart.id, {})
}

function toggleFilterPanel() {
  filterOpen.value = !filterOpen.value
  activeBubble.value = null
  chatOpen.value = false
}

function toggleChatDialog() {
  chatOpen.value = !chatOpen.value
  if (chatOpen.value) {
    activeBubble.value = null
    filterOpen.value = false
    nextTick(() => chatInputRef.value?.focus())
  }
}

function openBubble(type: 'warehouse') {
  activeBubble.value = activeBubble.value === type ? null : type
  filterOpen.value = false
  chatOpen.value = false
}

function sendChat() {
  const text = chatInput.value.trim()
  if (!text) return
  ElMessage.success('已提交修改意图，后续将据此调整图表（Mock）')
  chatInput.value = ''
  chatOpen.value = false
}

function confirmWarehouse() {
  activeBubble.value = null
  emit('move-to-warehouse', props.chart.id)
}

function onDragStart(e: DragEvent) {
  emit('dragstart', props.chart.id, e)
}

function onDragEnd() {
  emit('dragend')
}

function onDocClick() {
  activeBubble.value = null
  filterOpen.value = false
  chatOpen.value = false
}

onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))
</script>

<style scoped>
.chart-card {
  background: var(--bi-surface, #fff);
  border: 1px solid var(--bi-border, #E5E0D8);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, opacity 0.15s ease;
  height: fit-content;
  position: relative;
  box-shadow: 0 1px 0 rgba(31, 26, 23, 0.03);
}

.chart-card--expanded {
  box-shadow: 0 12px 34px rgba(58, 45, 34, 0.08);
}

.chart-card--chat-open {
  overflow: visible;
  z-index: 25;
}

.chart-card--dragging {
  opacity: 0.55;
}

.chart-card:hover {
  border-color: var(--bi-border-strong, #D8CEC2);
  box-shadow: 0 10px 28px rgba(58, 45, 34, 0.08);
}

.chart-card__header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 13px 14px 12px;
  border-bottom: 1px solid transparent;
  background: rgba(253, 251, 248, 0.78);
}

.chart-card--collapsed .chart-card__header {
  border-bottom: none;
}

.chart-card:not(.chart-card--collapsed) .chart-card__header {
  border-bottom-color: var(--bi-border, #E5E0D8);
}

.chart-card__drag,
.chart-card__collapse {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--bi-border);
  border-radius: 7px;
  background: var(--bi-surface-muted, #FAF8F5);
  color: var(--bi-muted);
  cursor: grab;
  transition: background 0.15s ease;
}

.chart-card__collapse {
  cursor: pointer;
}

.chart-card__drag:active {
  cursor: grabbing;
}

.chart-card__drag:hover,
.chart-card__collapse:hover {
  background: var(--bi-accent-soft, rgba(217, 119, 87, 0.12));
  color: var(--bi-accent, #D97757);
  border-color: rgba(217, 119, 87, 0.35);
}

.chart-card__titles {
  flex: 1;
  min-width: 0;
}

.chart-card__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--bi-text);
  margin: 0 0 4px;
  line-height: 1.35;
  letter-spacing: 0;
}

.chart-card__question {
  font-size: 12px;
  color: var(--bi-muted);
  line-height: 1.55;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.chart-card__filter-hint {
  font-size: 11px;
  color: var(--bi-blue, #4E6D80);
  margin: 6px 0 0;
}

.chart-card__actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  position: relative;
}

.action-wrap {
  position: relative;
}

.btn-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--bi-border);
  border-radius: 7px;
  background: #fff;
  color: var(--bi-muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-icon:hover {
  border-color: var(--bi-border-strong, #D4CEC4);
  color: var(--bi-text);
  background: var(--bi-surface-muted, #FAF8F5);
}

.chart-card__drag:focus-visible,
.chart-card__collapse:focus-visible,
.btn-icon:focus-visible,
.chat-dialog__close:focus-visible,
.chat-dialog__send:focus-visible,
.bubble-btn:focus-visible,
.filter-panel__clear:focus-visible {
  outline: 2px solid rgba(198, 97, 63, 0.36);
  outline-offset: 2px;
}

.btn-icon--filter.btn-icon--filter-applied {
  color: var(--bi-blue, #4E6D80);
  border-color: rgba(78, 109, 128, 0.35);
  background: rgba(78, 109, 128, 0.1);
}

.btn-icon--filter.btn-icon--filter-applied:hover {
  color: #3B5C70;
  border-color: rgba(78, 109, 128, 0.5);
  background: rgba(78, 109, 128, 0.14);
}

.btn-icon--filter.btn-icon--filter-open:not(.btn-icon--filter-applied) {
  border-color: rgba(217, 119, 87, 0.45);
  background: rgba(217, 119, 87, 0.08);
  color: var(--bi-accent, #D97757);
}

.btn-icon--filter.btn-icon--filter-applied.btn-icon--filter-open {
  box-shadow: 0 0 0 2px rgba(78, 109, 128, 0.14);
}

.btn-icon--chat {
  color: var(--bi-green, #4D7B62);
  border-color: rgba(77, 123, 98, 0.32);
  background: rgba(77, 123, 98, 0.08);
}

.btn-icon--chat:hover,
.btn-icon--chat-active {
  background: rgba(77, 123, 98, 0.14);
  color: #3F6A52;
  border-color: rgba(77, 123, 98, 0.48);
}

.chat-dialog {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 40;
  width: min(320px, calc(100vw - 48px));
  padding: 14px;
  background: #fff;
  border: 1px solid rgba(52, 199, 89, 0.35);
  border-radius: 8px;
  box-shadow: 0 14px 34px rgba(58, 45, 34, 0.14);
}

.chat-dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.chat-dialog__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--bi-text);
}

.chat-dialog__close {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--bi-muted);
  border-radius: 7px;
  cursor: pointer;
}

.chat-dialog__close:hover {
  background: rgba(28, 25, 23, 0.06);
  color: var(--bi-text);
}

.chat-dialog__hint {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--bi-muted);
}

.chat-dialog__input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.5;
  font-family: inherit;
  color: var(--bi-text);
  background: #FAF8F5;
  border: 1px solid var(--bi-border);
  border-radius: 8px;
  resize: vertical;
  min-height: 72px;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.chat-dialog__input:focus {
  border-color: rgba(52, 199, 89, 0.55);
  box-shadow: 0 0 0 3px rgba(52, 199, 89, 0.12);
  background: #fff;
}

.chat-dialog__input::placeholder {
  color: var(--bi-faint, #A39E96);
}

.chat-dialog__footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.chat-dialog__send {
  height: 34px;
  padding: 0 18px;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  color: #fff;
  background: #3D9A6A;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease, opacity 0.15s ease;
}

.chat-dialog__send:hover:not(:disabled) {
  background: #2D8A5E;
}

.chat-dialog__send:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.action-bubble {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 30;
  min-width: 220px;
  max-width: 280px;
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--bi-text);
  background: #fff;
  border: 1px solid var(--bi-border);
  border-radius: 8px;
  box-shadow: 0 12px 28px rgba(58, 45, 34, 0.12);
}

.action-bubble--confirm p {
  margin: 0 0 10px;
  color: var(--bi-muted);
}

.bubble-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.bubble-btn {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
  font-family: inherit;
  border: 1px solid var(--bi-border);
  border-radius: 7px;
  background: #fff;
  cursor: pointer;
}

.bubble-btn--primary {
  background: var(--bi-accent, #D97757);
  border-color: var(--bi-accent, #D97757);
  color: #fff;
}

.filter-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 30;
  width: 240px;
  padding: 12px;
  background: #fff;
  border: 1px solid var(--bi-border);
  border-radius: 8px;
  box-shadow: 0 12px 28px rgba(58, 45, 34, 0.12);
}

.filter-panel__title {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 4px;
}

.filter-panel__hint {
  font-size: 11px;
  color: var(--bi-faint, #A39E96);
  margin: 0 0 12px;
}

.filter-panel__row {
  margin-bottom: 10px;
}

.filter-panel__row label {
  display: block;
  font-size: 11px;
  color: var(--bi-muted);
  margin-bottom: 4px;
}

.filter-panel__row :deep(.el-select) {
  width: 100%;
}

.filter-panel__clear {
  width: 100%;
  margin-top: 4px;
  height: 28px;
  font-size: 12px;
  color: var(--bi-accent);
  background: none;
  border: none;
  cursor: pointer;
}

.chart-card__body {
  padding: 14px 16px 16px;
  min-width: 0;
  background: #fff;
  transition: padding 0.18s ease;
}

.chart-card--expanded .chart-card__body {
  padding: 18px 22px 22px;
}

@media (max-width: 720px) {
  .chart-card__header {
    flex-wrap: wrap;
  }

  .chart-card__actions {
    width: 100%;
    justify-content: flex-end;
  }
}

.kpi-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  gap: 8px;
}

.kpi-value {
  font-size: 40px;
  font-weight: 600;
  color: var(--bi-accent);
}

.kpi-sub {
  font-size: 13px;
  color: var(--bi-muted);
}

.bubble-fade-enter-active,
.bubble-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.bubble-fade-enter-from,
.bubble-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
