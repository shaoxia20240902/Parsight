<template>
  <div class="relations-view">
    <div class="page-header">
      <h1 class="page-title">XLSX 关联</h1>
      <p class="page-desc">分析同一文件中多个 Sheet 之间的跨表关联关系</p>
    </div>

    <div v-if="!currentSpaceId" class="empty-state">
      <div class="empty-icon-wrap">
        <el-icon class="empty-icon"><FolderOpened /></el-icon>
      </div>
      <p class="empty-title">请先选择空间</p>
      <p class="empty-desc">在顶部切换或创建一个空间</p>
    </div>

    <template v-else>
      <div class="card understand-card">
        <div v-if="showStageProgress" class="stage-progress">
          <div class="stage-progress-head">
            <span class="stage-progress-title">{{ activeStage.title }}</span>
            <span class="stage-progress-desc">{{ activeStage.desc }}</span>
          </div>
          <div class="stage-progress-track">
            <div
              v-for="(stage, index) in progressStages"
              :key="stage.title"
              class="stage-progress-item"
              :class="{
                active: index === activeStageIndex,
                complete: index < activeStageIndex,
                pending: index > activeStageIndex
              }"
            >
              <span class="stage-progress-dot">
                <el-icon v-if="index === activeStageIndex" class="stage-progress-spinner is-loading">
                  <Loading />
                </el-icon>
              </span>
              <span class="stage-progress-label">{{ stage.title }}</span>
            </div>
          </div>
        </div>

        <div class="understand-card-header">
          <div>
            <h3 class="card-title">跨表关联分析</h3>
            <p class="understand-subtitle">
              基于各 Sheet 单表理解与随机样本
              <span v-if="relationsUpdatedAt" class="understand-meta">
                · 更新于 {{ formatTime(relationsUpdatedAt) }}
              </span>
            </p>
          </div>
          <div v-if="relationsContent && !loading" class="understand-actions">
            <div v-if="showCompareToggle" class="compare-toggle">
              <button
                type="button"
                class="compare-btn"
                :class="{ active: contentViewMode === 'current' }"
                @click="contentViewMode = 'current'"
              >
                核对后
              </button>
              <button
                type="button"
                class="compare-btn"
                :class="{ active: contentViewMode === 'initial' }"
                @click="contentViewMode = 'initial'"
              >
                核对前
              </button>
            </div>
            <button
              class="btn-secondary btn-sm"
              :disabled="regenerating"
              @click="regenerateRelations"
            >
              {{ regenerating ? '生成中…' : '重新生成' }}
            </button>
          </div>
        </div>

        <div v-if="loading" class="understand-skeleton">
          <div v-for="i in 6" :key="i" class="skeleton-line" :class="{ 'skeleton-title': i === 1 }" />
        </div>

        <div
          v-else-if="displayContent"
          class="understand-markdown"
          v-html="renderedContent"
        />

        <div v-else class="empty-state empty-state--inline">
          <div class="empty-icon-wrap">
            <el-icon class="empty-icon"><Connection /></el-icon>
          </div>
          <p class="empty-title">暂无关联分析</p>
          <p class="empty-desc">
            请上传包含多个 Sheet 的 XLSX，并先在各表生成「理解内容」后再查看关联分析
          </p>
          <button v-if="!loading" class="btn-primary" @click="loadRelations(false)">
            开始分析
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { FolderOpened, Connection, Loading } from '@element-plus/icons-vue'
import { getRelations } from '../api/data'

type ProgressStage = {
  title: string
  desc: string
}

const currentSpaceId = ref(localStorage.getItem('xlsx-bi-active-space') || '')
const relationsContent = ref('')
const relationsContentInitial = ref('')
const relationsUpdatedAt = ref('')
const loading = ref(false)
const regenerating = ref(false)
const verificationStatus = ref<'idle' | 'verifying' | 'completed' | 'failed'>('idle')
const contentViewMode = ref<'current' | 'initial'>('current')
let verifyPollTimer: ReturnType<typeof setInterval> | null = null

marked.setOptions({ gfm: true, breaks: true })

const progressStages: ProgressStage[] = [
  { title: '数据汇总', desc: '汇总各表理解和样本信息' },
  { title: '关联识别', desc: '识别字段关系与跨表业务链路' },
  { title: '异常复核', desc: '核对可疑关联和口径冲突' },
  { title: '关联洞察', desc: '整合复核结果，形成关联总结' },
  { title: '完成', desc: '关联总结已更新' }
]

const activeStageIndex = computed(() => {
  if (verificationStatus.value === 'verifying') return 2
  if (loading.value || regenerating.value) return 1
  return 0
})

const activeStage = computed(() => progressStages[activeStageIndex.value])

const showStageProgress = computed(() => {
  return loading.value || regenerating.value || verificationStatus.value === 'verifying'
})

const showCompareToggle = computed(() => {
  const initial = relationsContentInitial.value
  const current = relationsContent.value
  return Boolean(initial && current && initial !== current)
})

const displayContent = computed(() => {
  if (contentViewMode.value === 'initial' && relationsContentInitial.value) {
    return relationsContentInitial.value
  }
  return relationsContent.value
})

const renderedContent = computed(() => {
  if (!displayContent.value) return ''
  return marked.parse(displayContent.value) as string
})

function formatTime(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', { hour12: false })
}

function extractErrorMessage(e: unknown): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string }
  return err.response?.data?.detail || err.message || '请求失败'
}

function stopVerifyPoll() {
  if (verifyPollTimer) {
    clearInterval(verifyPollTimer)
    verifyPollTimer = null
  }
}

function startVerifyPoll() {
  stopVerifyPoll()
  if (!currentSpaceId.value) return
  const spaceAtStart = currentSpaceId.value
  let lastUpdated = relationsUpdatedAt.value

  verifyPollTimer = setInterval(async () => {
    if (currentSpaceId.value !== spaceAtStart) {
      stopVerifyPoll()
      return
    }
    try {
      const res = await getRelations(spaceAtStart, false)
      const status = res.data.verification_status || 'idle'
      verificationStatus.value = status
      relationsContentInitial.value = res.data.content_initial || ''

      if (res.data.updated_at && res.data.updated_at !== lastUpdated) {
        relationsContent.value = res.data.content || ''
        relationsUpdatedAt.value = res.data.updated_at || ''
        lastUpdated = res.data.updated_at
      }

      if (status === 'completed') {
        relationsContent.value = res.data.content || ''
        relationsUpdatedAt.value = res.data.updated_at || ''
        stopVerifyPoll()
        ElMessage.success('跨表关联核对完成，内容已更新')
      } else if (status === 'failed') {
        stopVerifyPoll()
        ElMessage.error('跨表关联核对失败，请重新生成')
      }
    } catch {
      // 轮询失败不打断阅读
    }
  }, 3000)
}

async function loadRelations(regenerate = false) {
  if (!currentSpaceId.value) return
  if (regenerate) {
    regenerating.value = true
  } else {
    loading.value = true
  }
  stopVerifyPoll()
  try {
    const res = await getRelations(currentSpaceId.value, regenerate)
    relationsContent.value = res.data.content || ''
    relationsContentInitial.value = res.data.content_initial || ''
    relationsUpdatedAt.value = res.data.updated_at || ''
    verificationStatus.value = res.data.verification_status || 'idle'
    contentViewMode.value = 'current'

    if (verificationStatus.value === 'verifying') {
      startVerifyPoll()
    }
  } catch (e) {
    relationsContent.value = ''
    relationsContentInitial.value = ''
    verificationStatus.value = 'idle'
    ElMessage.error(extractErrorMessage(e))
  } finally {
    loading.value = false
    regenerating.value = false
  }
}

async function regenerateRelations() {
  await loadRelations(true)
  if (relationsContent.value) {
    ElMessage.success('已重新生成')
  }
}

watch(currentSpaceId, () => {
  localStorage.setItem('xlsx-bi-active-space', currentSpaceId.value)
  relationsContent.value = ''
  relationsContentInitial.value = ''
  contentViewMode.value = 'current'
  loadRelations(false)
})

onMounted(() => {
  if (currentSpaceId.value) {
    loadRelations(false)
  }
  window.addEventListener('space-changed', ((e: CustomEvent) => {
    currentSpaceId.value = e.detail?.id || ''
  }) as EventListener)
})

onUnmounted(() => {
  stopVerifyPoll()
})
</script>

<style scoped>
.relations-view {
  max-width: 1200px;
}

.page-header {
  margin-bottom: var(--spacing-xl);
}

.page-title {
  font-size: 32px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
  letter-spacing: -0.02em;
}

.page-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.card {
  background: var(--color-white);
  border-radius: var(--radius-xl);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-card);
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.understand-card {
  position: relative;
  padding: var(--spacing-xl);
}

.stage-progress {
  padding: 12px 14px;
  margin-bottom: var(--spacing-lg);
  background: var(--color-bg);
  border: 1px solid var(--color-separator);
  border-radius: var(--radius-base);
}

.stage-progress-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.stage-progress-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  white-space: nowrap;
}

.stage-progress-desc {
  min-width: 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--color-text-secondary);
  text-align: right;
}

.stage-progress-track {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  column-gap: 8px;
}

.stage-progress-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.stage-progress-item:not(:last-child)::after {
  content: "";
  position: absolute;
  left: calc(100% + 2px);
  right: -6px;
  top: 8px;
  height: 2px;
  background: var(--color-separator);
  border-radius: 999px;
}

.stage-progress-item.complete:not(:last-child)::after {
  background: var(--color-primary);
}

.stage-progress-dot {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  border-radius: 50%;
  background: var(--color-separator);
  border: 2px solid var(--color-bg);
}

.stage-progress-item.complete .stage-progress-dot,
.stage-progress-item.active .stage-progress-dot {
  background: var(--color-primary);
}

.stage-progress-spinner {
  font-size: 12px;
  color: #fff;
}

.stage-progress-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-tertiary);
}

.stage-progress-item.complete .stage-progress-label,
.stage-progress-item.active .stage-progress-label {
  color: var(--color-text-primary);
}

.verify-badge {
  position: absolute;
  top: var(--spacing-base);
  right: var(--spacing-base);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-warning);
  background: rgba(255, 149, 0, 0.12);
  border: 1px solid rgba(255, 149, 0, 0.25);
  border-radius: var(--radius-full);
  z-index: 2;
}

.verify-icon {
  font-size: 14px;
}

.understand-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-base);
  margin-bottom: var(--spacing-lg);
  flex-wrap: wrap;
}

.understand-subtitle {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: var(--spacing-xs);
}

.understand-meta {
  color: var(--color-text-tertiary);
}

.understand-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.compare-toggle {
  display: inline-flex;
  padding: 2px;
  background: var(--color-bg);
  border-radius: var(--radius-base);
}

.compare-btn {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.compare-btn:hover {
  color: var(--color-text-primary);
}

.compare-btn.active {
  background: var(--color-white);
  color: var(--color-primary);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.btn-sm {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  padding: 0 20px;
  background: var(--color-primary);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  border: none;
  border-radius: var(--radius-base);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-primary:hover {
  background: var(--color-primary-hover);
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  padding: 0 20px;
  background: var(--color-white);
  color: var(--color-primary);
  font-size: 14px;
  font-weight: 500;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: var(--radius-base);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-secondary:hover {
  background: rgba(0, 122, 255, 0.04);
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.understand-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  padding: var(--spacing-base) 0;
}

.skeleton-line {
  height: 14px;
  background: linear-gradient(90deg, #f0f0f2 25%, #e8e8ed 50%, #f0f0f2 75%);
  background-size: 200% 100%;
  border-radius: 4px;
  animation: shimmer 1.2s ease-in-out infinite;
}

.skeleton-title {
  height: 20px;
  width: 40%;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.understand-markdown {
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-primary);
}

.understand-markdown :deep(h2) {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: var(--spacing-xl) 0 var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--color-separator);
}

.understand-markdown :deep(h2:first-child) {
  margin-top: 0;
}

.understand-markdown :deep(p) {
  margin: 0 0 var(--spacing-md);
  color: var(--color-text-secondary);
}

.understand-markdown :deep(ul),
.understand-markdown :deep(ol) {
  margin: 0 0 var(--spacing-md);
  padding-left: var(--spacing-xl);
  color: var(--color-text-secondary);
}

.understand-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: var(--spacing-md) 0 var(--spacing-lg);
  font-size: 14px;
}

.understand-markdown :deep(thead th) {
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-weight: 500;
  font-size: 12px;
  text-align: left;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-separator);
}

.understand-markdown :deep(tbody td) {
  padding: 12px 16px;
  color: var(--color-text-primary);
  border-bottom: 1px solid #f5f5f7;
  vertical-align: top;
}

.understand-markdown :deep(tbody tr:nth-child(even)) {
  background: rgba(0, 0, 0, 0.012);
}

.understand-markdown :deep(tbody tr:hover) {
  background: rgba(0, 122, 255, 0.04);
}

.understand-markdown :deep(strong) {
  color: var(--color-text-primary);
  font-weight: 600;
}

.empty-state {
  text-align: center;
  padding: 80px var(--spacing-xl);
  background: var(--color-white);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
}

.empty-state--inline {
  padding: 48px var(--spacing-xl);
  background: transparent;
  box-shadow: none;
}

.empty-icon-wrap {
  margin-bottom: var(--spacing-base);
}

.empty-icon {
  font-size: 48px;
  color: var(--color-text-tertiary);
  opacity: 0.25;
}

.empty-title {
  font-size: 18px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-xs);
}

.empty-desc {
  font-size: 13px;
  color: var(--color-text-tertiary);
  margin-bottom: var(--spacing-base);
}
</style>
