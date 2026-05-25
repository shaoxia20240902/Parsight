<template>
  <div class="bi-dashboard">
    <!-- ============ 头部 ============ -->
    <div v-if="!generating" class="bi-dashboard__header">
      <div class="bi-dashboard__title-group">
        <h2 class="bi-dashboard__title">BI 智能看板</h2>
        <p class="bi-dashboard__subtitle" v-if="activeConfig">
          {{ activeCategoryTotal }} 个分类 · {{ charts.length }} 个图表
          <span v-if="usingDemo"> · 演示数据</span>
        </p>
      </div>
      <div class="bi-dashboard__header-actions">
        <el-button
          v-if="activeConfig"
          type="primary"
          :icon="'Refresh'"
          size="small"
          @click="usingDemo ? startAIFromChoice() : regenerateBI()"
          :loading="generating"
        >
          {{ usingDemo ? 'AI 全局构建' : '重新生成' }}
        </el-button>
      </div>
    </div>

    <template v-if="generating">
      <BIGeneratingExperience
        v-if="biError || generationView === 'planning'"
        :file-id="fileId"
        :active="!biError && generationView === 'planning'"
        :error="biError || undefined"
        :events="progressEvents"
        :generation-started-at="generationStartedAt || undefined"
        @retry="retryGenerate"
      />
      <BIStagedGeneratingBoard
        v-else
        :events="progressEvents"
        :generation-started-at="generationStartedAt || undefined"
      />
    </template>

    <BIGeneratingExperience
      v-else-if="!biConfig && biError"
      :file-id="fileId"
      :active="false"
      :error="biError"
      :events="progressEvents"
      @retry="retryGenerate"
    />

    <div v-else-if="!activeConfig" class="bi-setup">
      <div class="bi-setup__card" :class="{ 'bi-setup__card--error': biStatus === 'failed' }">
        <p class="bi-setup__eyebrow">BI 智能看板</p>
        <h2 class="bi-setup__title">
          {{ biStatus === 'failed' ? '上次生成未完成' : '准备生成看板' }}
        </h2>
        <p class="bi-setup__desc">
          表理解已完成。点击开始后，将依次规划分类、确定图表与公共筛选项，并按分类执行每个图表。
        </p>
        <div class="bi-setup__steps" aria-label="生成步骤">
          <span>分类</span>
          <span>图表方案</span>
          <span>逐类执行</span>
          <span>看板完成</span>
        </div>
        <button type="button" class="bi-setup__cta" :disabled="generationInFlight" @click="generateBI">
          开始生成看板
        </button>
      </div>
    </div>

    <!-- ============ BI 看板内容 ============ -->
    <div v-if="activeConfig && !generating" class="bi-content">
      <BIInsightsBoard
        :file-id="activeFileId"
        :config="insightsConfig"
        :demo-mode="usingDemo"
      />
    </div>

    <transition name="choice-fade">
      <div v-if="choiceVisible" class="bi-choice" role="dialog" aria-modal="true" aria-labelledby="bi-choice-title">
        <div class="bi-choice__panel">
          <p class="bi-choice__eyebrow">BI 智能看板</p>
          <h3 id="bi-choice-title" class="bi-choice__title">选择本次查看方式</h3>
          <p class="bi-choice__desc">
            表理解已完成。你可以先查看内置演示看板，也可以直接让 AI 基于当前文件完成全局构建。
          </p>
          <div class="bi-choice__cards">
            <button type="button" class="bi-choice__card" @click="showDemoFromChoice">
              <span class="bi-choice__card-title">查看演示数据</span>
              <span class="bi-choice__card-desc">打开 8 个分类、64 张图表的销售样例看板。</span>
            </button>
            <button type="button" class="bi-choice__card bi-choice__card--primary" @click="startAIFromChoice">
              <span class="bi-choice__card-title">AI 全局构建</span>
              <span class="bi-choice__card-desc">按分类规划、图表方案、逐图执行生成真实看板。</span>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { generateBIConfig, getBIConfig, getBIStatus, getBIFilterOptions } from '../api'
import type { BIProgressEvent, BIStatus } from '../api'
import BIGeneratingExperience from './BIGeneratingExperience.vue'
import BIStagedGeneratingBoard from './bi/BIStagedGeneratingBoard.vue'
import BIInsightsBoard from './bi/BIInsightsBoard.vue'
import { useBiGenerationProgress } from '../composables/useBiGenerationProgress'
import { createDemoBIConfig } from '../mocks/demoBIConfig'

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
const progressEvents = ref<BIProgressEvent[]>([])
const generationStartedAt = ref('')
const usingDemo = ref(false)
const choiceVisible = ref(false)
const choicePromptShown = ref(false)
const demoConfig = createDemoBIConfig()

// 全局筛选
const globalFilters = reactive<Record<string, any>>({})
const filterOptions = ref<Array<{ field: string; type: string; sample_values: string[] }>>([])

let statusPollTimer: ReturnType<typeof setInterval> | null = null

// ============ Computed ============
const activeConfig = computed(() => usingDemo.value ? demoConfig : biConfig.value)
const charts = computed(() => activeConfig.value?.charts || [])
const activeFileId = computed(() => usingDemo.value ? 'demo-sales-bi' : props.fileId)
const activeCategoryTotal = computed(() =>
  (activeConfig.value?.categories?.length || 0) + (activeConfig.value?.custom_categories?.length || 0)
)
const insightsConfig = computed(() => ({
  ...(activeConfig.value || {}),
  global_filters: activeConfig.value?.global_filters?.length
    ? activeConfig.value.global_filters
    : filterOptions.value
}))

const { generationView } = useBiGenerationProgress(progressEvents)

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
    const statusData = res.data.data
    const status = statusData?.status as BIStatus
    biStatus.value = status
    generationStartedAt.value = statusData?.generation_started_at || ''

    if (status === 'completed') {
      // 已完成，直接加载配置
      stopStatusPoll()
      await loadBIConfig()
      openReadyChoice()
    } else if (status === 'generating') {
      // 正在生成中，显示加载态并轮询
      generating.value = true
      biError.value = ''
      startStatusPoll()
    } else if (status === 'failed' || status === 'none') {
      // 失败或未生成，等待用户手动启动
      stopStatusPoll()
      generating.value = false
      openReadyChoice()
    } else if (status === 'blocked') {
      // 理解尚未完成
      biError.value = '数据理解尚未完成，请稍后再试'
    }
  } catch (err: any) {
    console.error('查询BI状态失败:', err)
    biError.value = err.message || '无法查询 BI 状态'
  }
}

function openReadyChoice() {
  if (choicePromptShown.value || generationInFlight.value || generating.value) return
  choicePromptShown.value = true
  choiceVisible.value = true
}

function showDemoFromChoice() {
  stopStatusPoll()
  choiceVisible.value = false
  usingDemo.value = true
  generating.value = false
  biError.value = ''
}

function startAIFromChoice() {
  if (generationInFlight.value) return
  choiceVisible.value = false
  usingDemo.value = false
  if (biConfig.value || biStatus.value === 'completed') {
    regenerateBI()
  } else {
    generateBI()
  }
}

const generateBI = async () => {
  if (generationInFlight.value) return
  generationInFlight.value = true
  generating.value = true
  biError.value = ''
  progressEvents.value = []
  generationStartedAt.value = ''
  usingDemo.value = false

  try {
    const res = await generateBIConfig(props.fileId, (event) => {
      if (event.generation_started_at) {
        generationStartedAt.value = event.generation_started_at
      }
      progressEvents.value = [...progressEvents.value, event]
    })
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
      const statusData = res.data.data
      const status = statusData?.status as BIStatus
      biStatus.value = status
      generationStartedAt.value = statusData?.generation_started_at || generationStartedAt.value
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
      progressEvents.value = []
      generationStartedAt.value = ''
      usingDemo.value = false
      choiceVisible.value = false
      choicePromptShown.value = false
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
  --bi-page-bg: #F4F1EA;
  --bi-ink: #1F1A17;
  --bi-muted: #736A61;
  --bi-faint: #A39B92;
  --bi-rust: #C6613F;
  --bi-rust-dark: #A84F33;
  --bi-line: #E8E1D8;
  --bi-paper: #FDFBF8;
  --bi-paper-muted: #F8F4EE;

  min-height: calc(100vh - var(--header-height, 52px) - 20px);
  margin-top: 0;
  background: var(--bi-page-bg);
}

.bi-dashboard__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 56px;
  padding: 0 20px;
  margin-bottom: 0;
  background: rgba(253, 251, 248, 0.86);
  border-bottom: 1px solid var(--bi-line);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.bi-dashboard__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--bi-ink);
}

.bi-dashboard__subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--bi-faint);
}

.bi-dashboard__header-actions :deep(.el-button) {
  border-radius: 8px;
  border-color: rgba(198, 97, 63, 0.28);
  background: rgba(198, 97, 63, 0.1);
  color: var(--bi-rust);
  box-shadow: none;
}

.bi-dashboard__header-actions :deep(.el-button:hover) {
  border-color: rgba(198, 97, 63, 0.42);
  background: rgba(198, 97, 63, 0.14);
  color: var(--bi-rust-dark);
}

/* ============ 未生成（Claude 暖色） ============ */
.bi-setup {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - var(--header-height, 52px) - 80px);
  padding: 32px 20px;
  margin: 0 calc(-1 * var(--spacing-base, 16px));
  background: var(--bi-page-bg);
}

.bi-setup__card {
  width: min(520px, 100%);
  padding: 34px 34px 32px;
  text-align: center;
  background: var(--bi-paper);
  border: 1px solid var(--bi-line);
  border-radius: 8px;
  box-shadow: 0 18px 44px rgba(58, 45, 34, 0.08);
}

.bi-setup__eyebrow {
  margin: 0 0 12px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--bi-rust);
}

.bi-setup__title {
  margin: 0 0 10px;
  font-size: 22px;
  font-weight: 600;
  color: var(--bi-ink);
  letter-spacing: 0;
}

.bi-setup__desc {
  margin: 0 0 24px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--bi-muted);
}

.bi-setup__steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0 0 24px;
}

.bi-setup__steps span {
  min-width: 0;
  padding: 8px 6px;
  border: 1px solid var(--bi-line);
  border-radius: 8px;
  background: var(--bi-paper-muted);
  color: var(--bi-muted);
  font-size: 12px;
  white-space: nowrap;
}

.bi-setup__cta {
  height: 44px;
  padding: 0 28px;
  border: none;
  border-radius: 8px;
  background: var(--bi-rust);
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}

.bi-setup__cta:hover {
  background: var(--bi-rust-dark);
}

.bi-setup__cta:focus-visible {
  outline: 2px solid rgba(198, 97, 63, 0.38);
  outline-offset: 3px;
}

.bi-setup__cta:active {
  transform: scale(0.98);
}

@media (max-width: 560px) {
  .bi-dashboard__header {
    padding: 0 14px;
  }

  .bi-setup {
    padding: 24px 14px;
  }

  .bi-setup__card {
    padding: 28px 22px;
  }

  .bi-setup__steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .bi-choice__panel {
    padding: 24px 20px;
  }

  .bi-choice__cards {
    grid-template-columns: 1fr;
  }
}

.bi-dashboard:has(.bi-gen) {
  margin-top: 0;
}

.choice-fade-enter-active,
.choice-fade-leave-active {
  transition: opacity 0.16s ease;
}

.choice-fade-enter-from,
.choice-fade-leave-to {
  opacity: 0;
}

.bi-choice {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(31, 26, 23, 0.34);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.bi-choice__panel {
  width: min(560px, calc(100vw - 32px));
  padding: 30px;
  background: var(--bi-paper);
  border: 1px solid var(--bi-line);
  border-radius: 8px;
  box-shadow: 0 24px 70px rgba(58, 45, 34, 0.18);
}

.bi-choice__eyebrow {
  margin: 0 0 10px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--bi-rust);
}

.bi-choice__title {
  margin: 0 0 10px;
  font-size: 22px;
  font-weight: 600;
  color: var(--bi-ink);
  letter-spacing: 0;
}

.bi-choice__desc {
  margin: 0 0 22px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--bi-muted);
}

.bi-choice__cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.bi-choice__card {
  min-height: 112px;
  padding: 16px;
  text-align: left;
  border: 1px solid var(--bi-line);
  border-radius: 8px;
  background: var(--bi-paper-muted);
  color: var(--bi-ink);
  font-family: inherit;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, transform 0.15s ease;
}

.bi-choice__card:hover {
  border-color: rgba(198, 97, 63, 0.45);
  background: #fff;
}

.bi-choice__card:focus-visible {
  outline: 2px solid rgba(198, 97, 63, 0.38);
  outline-offset: 3px;
}

.bi-choice__card:active {
  transform: scale(0.99);
}

.bi-choice__card--primary {
  border-color: rgba(198, 97, 63, 0.42);
  background: rgba(198, 97, 63, 0.1);
}

.bi-choice__card-title {
  display: block;
  margin-bottom: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--bi-ink);
}

.bi-choice__card-desc {
  display: block;
  font-size: 12px;
  line-height: 1.55;
  color: var(--bi-muted);
}

@media (max-width: 560px) {
  .bi-choice__panel {
    padding: 24px 20px;
  }

  .bi-choice__cards {
    grid-template-columns: 1fr;
  }
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
  border-radius: 8px;
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
