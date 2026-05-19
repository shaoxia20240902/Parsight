<template>
  <div class="bi-dashboard">
    <!-- ============ 头部 ============ -->
    <div v-if="!generating" class="bi-dashboard__header">
      <div class="bi-dashboard__title-group">
        <h2 class="bi-dashboard__title">BI 智能看板</h2>
        <p class="bi-dashboard__subtitle" v-if="biConfig">
          {{ biConfig.categories?.length || 0 }} 个分类 · {{ charts.length }} 个图表
        </p>
      </div>
      <div class="bi-dashboard__header-actions">
        <el-button
          v-if="biConfig"
          type="primary"
          :icon="'Refresh'"
          size="small"
          @click="regenerateBI"
          :loading="generating"
        >
          重新生成
        </el-button>
      </div>
    </div>

    <BIGeneratingExperience
      v-if="generating || (!biConfig && biError)"
      :file-id="fileId"
      :active="generating"
      :error="biError || undefined"
      @retry="retryGenerate"
    />

    <!-- ============ BI 看板内容 ============ -->
    <div v-if="biConfig && !generating" class="bi-content">
      <BIInsightsBoard :file-id="fileId" :config="insightsConfig" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { generateBIConfig, getBIConfig, getBIStatus, getBIFilterOptions } from '../api'
import type { BIStatus } from '../api'
import BIGeneratingExperience from './BIGeneratingExperience.vue'
import BIInsightsBoard from './bi/BIInsightsBoard.vue'

// ============ Props ============
const props = defineProps<{
  fileId: string
}>()

// ============ State ============
const biConfig = ref<any>(null)
const activeCategory = ref('')
const generating = ref(false)
const biError = ref('')
const biStatus = ref<BIStatus>('none')
const generationInFlight = ref(false)

// 全局筛选
const globalFilters = reactive<Record<string, any>>({})
const filterOptions = ref<Array<{ field: string; type: string; sample_values: string[] }>>([])

let statusPollTimer: ReturnType<typeof setInterval> | null = null

// ============ Computed ============
const charts = computed(() => biConfig.value?.charts || [])
const insightsConfig = computed(() => ({
  ...(biConfig.value || {}),
  global_filters: biConfig.value?.global_filters?.length
    ? biConfig.value.global_filters
    : filterOptions.value
}))

// ============ 数据加载 ============
const loadBIConfig = async () => {
  try {
    const res = await getBIConfig(props.fileId)
    biConfig.value = res.data.data

    if (biConfig.value?.categories?.length > 0 && !activeCategory.value) {
      activeCategory.value = biConfig.value.categories[0].name
    }

    // 加载全局筛选选项
    await loadFilterOptions()
  } catch (err: any) {
    console.error('获取BI配置失败:', err)
    biError.value = err.message || '无法加载 BI 看板'
  }
}

const loadFilterOptions = async () => {
  try {
    const res = await getBIFilterOptions(props.fileId)
    filterOptions.value = res.data.data || []
  } catch (err) {
    console.error('获取筛选选项失败:', err)
  }
}

const checkBIStatus = async () => {
  try {
    const res = await getBIStatus(props.fileId)
    const status = res.data.data?.status as BIStatus
    biStatus.value = status

    if (status === 'completed') {
      // 已完成，直接加载配置
      stopStatusPoll()
      await loadBIConfig()
    } else if (status === 'generating') {
      // 正在生成中，显示加载态并轮询
      generating.value = true
      biError.value = ''
      startStatusPoll()
    } else if (status === 'failed' || status === 'none') {
      // 失败或未生成，启动生成
      stopStatusPoll()
      await generateBI()
    } else if (status === 'blocked') {
      // 理解尚未完成
      biError.value = '数据理解尚未完成，请稍后再试'
    }
  } catch (err: any) {
    console.error('查询BI状态失败:', err)
    biError.value = err.message || '无法查询 BI 状态'
  }
}

const generateBI = async () => {
  if (generationInFlight.value) return
  generationInFlight.value = true
  generating.value = true
  biError.value = ''

  try {
    const res = await generateBIConfig(props.fileId)
    biConfig.value = res.data.data
    if (biConfig.value?.categories?.length > 0) {
      activeCategory.value = biConfig.value.categories[0].name
    }
    await loadFilterOptions()
  } catch (err: any) {
    console.error('BI生成失败:', err)
    biError.value = err.message || '未知错误'
    return
  } finally {
    generationInFlight.value = false
    if (!biError.value) {
      setTimeout(() => {
        generating.value = false
      }, 600)
    } else {
      generating.value = false
    }
  }
}

const regenerateBI = () => {
  if (generationInFlight.value) return
  biConfig.value = null
  activeCategory.value = ''
  stopStatusPoll()
  generateBI()
}

const retryGenerate = () => {
  if (generationInFlight.value) return
  biError.value = ''
  stopStatusPoll()
  generateBI()
}

// ============ 状态轮询 ============
function startStatusPoll() {
  stopStatusPoll()
  statusPollTimer = setInterval(async () => {
    try {
      const res = await getBIStatus(props.fileId)
      const status = res.data.data?.status as BIStatus
      biStatus.value = status
      if (status === 'completed') {
        stopStatusPoll()
        generating.value = false
        await loadBIConfig()
      } else if (status === 'failed') {
        stopStatusPoll()
        generating.value = false
        biError.value = 'BI 生成失败，请重试'
      }
      // generating 状态继续轮询
    } catch (err) {
      console.error('轮询BI状态失败:', err)
    }
  }, 10000)
}

function stopStatusPoll() {
  if (statusPollTimer) {
    clearInterval(statusPollTimer)
    statusPollTimer = null
  }
}

// ============ Lifecycle ============
onMounted(() => {
  if (props.fileId) {
    checkBIStatus()
  }
})

onUnmounted(() => {
  stopStatusPoll()
})

watch(
  () => props.fileId,
  (newVal) => {
    if (newVal) {
      biConfig.value = null
      activeCategory.value = ''
      biError.value = ''
      biStatus.value = 'none'
      generationInFlight.value = false
      Object.keys(globalFilters).forEach(k => delete globalFilters[k])
      stopStatusPoll()
      checkBIStatus()
    }
  }
)
</script>

<style scoped>
/* ============ 头部 ============ */
.bi-dashboard {
  margin-top: var(--spacing-xl);
}

.bi-dashboard__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.bi-dashboard__title {
  margin: 0;
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--color-text-primary);
}

.bi-dashboard__subtitle {
  margin: 4px 0 0;
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
}

/* ============ 未生成（Claude 暖色） ============ */
.bi-setup {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - var(--header-height, 52px) - 80px);
  padding: 32px 20px;
  margin: 0 calc(-1 * var(--spacing-base, 16px));
  background:
    radial-gradient(ellipse 70% 45% at 50% 0%, rgba(198, 97, 63, 0.07), transparent),
    #F4F1EA;
}

.bi-setup__card {
  width: min(440px, 100%);
  padding: 40px 36px;
  text-align: center;
  background: #FDFCFA;
  border: 1px solid rgba(28, 25, 23, 0.08);
  border-radius: 24px;
  box-shadow: 0 12px 40px rgba(28, 25, 23, 0.07);
}

.bi-setup__eyebrow {
  margin: 0 0 12px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #C6613F;
}

.bi-setup__title {
  margin: 0 0 10px;
  font-size: 22px;
  font-weight: 600;
  color: #1C1917;
  letter-spacing: -0.02em;
}

.bi-setup__desc {
  margin: 0 0 28px;
  font-size: 14px;
  line-height: 1.6;
  color: #736C64;
}

.bi-setup__cta {
  height: 44px;
  padding: 0 28px;
  border: none;
  border-radius: 12px;
  background: #C6613F;
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}

.bi-setup__cta:hover {
  background: #B55534;
}

.bi-setup__cta:active {
  transform: scale(0.98);
}

.bi-dashboard:has(.bi-gen) {
  margin-top: 0;
}

/* ============ 全局筛选栏 ============ */
.global-filter-bar {
  background: var(--color-white);
  border-radius: var(--radius-lg);
  padding: var(--spacing-base) var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
  box-shadow: var(--shadow-card);
  border: 1px solid rgba(0, 122, 255, 0.08);
}

.global-filter-bar__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.global-filter-bar__icon {
  color: var(--color-success);
  flex-shrink: 0;
}

.global-filter-bar__label {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.global-filter-bar__clear {
  margin-left: auto;
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
  font-family: inherit;
}

.global-filter-bar__clear:hover {
  color: var(--color-danger);
  background: rgba(255, 59, 48, 0.06);
}

.global-filter-bar__filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-base);
}

.global-filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.global-filter-item__label {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--color-text-secondary);
}

.global-filter-item :deep(.el-select) {
  width: 180px;
}

/* ============ 分类 Tab ============ */
.bi-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  padding: 4px;
  background: var(--color-bg);
  border-radius: var(--radius-base);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.bi-tab {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-base);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition-fast);
  font-family: var(--font-family);
}

.bi-tab:hover {
  color: var(--color-text-primary);
  background: rgba(0, 0, 0, 0.04);
}

.bi-tab--active {
  background: var(--color-white);
  color: var(--color-text-primary);
  font-weight: 500;
  box-shadow: var(--shadow-xs);
}

.bi-tab__icon {
  font-size: 14px;
}

.bi-tab__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: var(--color-bg);
  border-radius: 999px;
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.bi-tab--active .bi-tab__count {
  background: rgba(0, 122, 255, 0.1);
  color: var(--color-primary);
}

/* ============ 图表网格 ============ */
.bi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-lg);
}

.bi-grid__item {
  transition: transform 0.15s ease, opacity 0.15s ease;
}

.bi-grid__item--full {
  grid-column: 1 / -1;
}

.bi-grid__item--drag-over {
  transform: scale(0.98);
  opacity: 0.7;
}

.bi-empty-category {
  text-align: center;
  padding: 48px 20px;
  color: var(--color-text-tertiary);
  font-size: var(--text-sm);
}

/* ============ 响应式 ============ */
@media (max-width: 900px) {
  .bi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
