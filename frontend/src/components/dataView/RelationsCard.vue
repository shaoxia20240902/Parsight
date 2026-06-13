<template>
  <div class="card understand-card">
    <StageProgress
      v-if="showStageProgress"
      :title="activeStage.title"
      :desc="activeStage.desc"
      :stages="progressStages"
      :active-index="activeStageIndex"
    />
    <div class="understand-card-header">
      <div>
        <h3 class="card-title">跨表关联分析</h3>
        <p class="understand-subtitle">
          基于各 Sheet 单表理解与随机样本
          <span v-if="updatedAt" class="understand-meta"> · 更新于 {{ formatTime(updatedAt) }}</span>
        </p>
      </div>
      <div v-if="content && !loading" class="understand-actions">
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
          @click="$emit('regenerate')"
        >
          {{ regenerating ? '生成中…' : '重新生成' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="understand-skeleton">
      <div v-for="i in 6" :key="i" class="skeleton-line" :class="{ 'skeleton-title': i === 1 }"></div>
    </div>

    <div v-else-if="displayContent" class="understand-markdown" v-html="renderedContent" />

    <div v-else class="parsing-state">
      <div class="parsing-card">
        <div class="parsing-animation">
          <div class="parsing-dot"></div>
          <div class="parsing-dot"></div>
          <div class="parsing-dot"></div>
        </div>
        <div class="parsing-text">
          <span class="parsing-title">正在解析数据…</span>
          <span class="parsing-desc">AI 正在分析跨表关联，生成关联总结</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { marked } from 'marked'
import StageProgress from '../StageProgress.vue'

interface ProgressStage {
  title: string
  desc: string
}

const props = defineProps<{
  content: string
  contentInitial: string
  updatedAt: string
  loading: boolean
  regenerating: boolean
  verificationStatus: 'idle' | 'generating' | 'verifying' | 'completed' | 'failed'
}>()

defineEmits<{
  regenerate: []
}>()

const contentViewMode = ref<'current' | 'initial'>('current')

const progressStages: ProgressStage[] = [
  { title: '数据汇总', desc: '汇总各表理解和样本信息' },
  { title: '关联识别', desc: '识别字段关系与跨表业务链路' },
  { title: '异常复核', desc: '核对可疑关联和口径冲突' },
  { title: '关联洞察', desc: '整合复核结果，形成关联总结' },
  { title: '生成推荐问题', desc: '基于数据理解生成对话推荐问题' },
  { title: '完成', desc: '关联总结已更新' }
]

const activeStageIndex = computed(() => {
  if (props.verificationStatus === 'verifying') return 2
  if (props.verificationStatus === 'generating' || props.loading || props.regenerating) return 1
  return 0
})

const activeStage = computed(() => progressStages[activeStageIndex.value])

const showStageProgress = computed(() => {
  return props.loading || props.regenerating || props.verificationStatus === 'verifying' || props.verificationStatus === 'generating'
})

const showCompareToggle = computed(() => {
  return Boolean(props.contentInitial && props.content && props.contentInitial !== props.content)
})

const displayContent = computed(() => {
  if (contentViewMode.value === 'initial' && props.contentInitial) {
    return props.contentInitial
  }
  return props.content
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
</script>

<style scoped>
.understand-card {
  position: relative;
  padding: 20px 20px 24px;
}

.understand-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-base);
  margin-bottom: var(--spacing-lg);
}

.card-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-md);
}

.understand-subtitle {
  font-size: var(--text-sm);
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
  background: var(--dv-surface-muted);
  border: 1px solid var(--dv-border);
  border-radius: 8px;
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
  background: var(--dv-surface);
  color: var(--dv-accent);
  box-shadow: 0 1px 2px rgba(28, 25, 23, 0.06);
}

.btn-sm {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
}

.understand-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  padding: var(--spacing-base) 0;
}

.skeleton-line {
  height: var(--spacing-md);
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-sm);
  animation: shimmer 1.5s infinite;
}

.skeleton-title {
  width: 60%;
  height: 16px;
}

@keyframes shimmer {
  0% { opacity: 0.5; }
  50% { opacity: 1; }
  100% { opacity: 0.5; }
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

.understand-markdown :deep(li) {
  margin-bottom: var(--spacing-xs);
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
  border-bottom: 1px solid #F5F5F7;
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

.parsing-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  padding: 48px 20px;
}

.parsing-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 32px 48px;
  background: var(--dv-surface);
  border: 1px solid var(--dv-border);
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.06);
}

.parsing-animation {
  display: flex;
  align-items: center;
  gap: 8px;
}

.parsing-dot {
  width: 10px;
  height: 10px;
  background: var(--dv-accent);
  border-radius: 50%;
  animation: parsingPulse 1.2s ease-in-out infinite;
}

.parsing-dot:nth-child(1) { animation-delay: 0s; }
.parsing-dot:nth-child(2) { animation-delay: 0.2s; }
.parsing-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes parsingPulse {
  0%, 100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  50% {
    opacity: 1;
    transform: scale(1.1);
  }
}

.parsing-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.parsing-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--dv-text);
}

.parsing-desc {
  font-size: 13px;
  color: var(--dv-muted);
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 32px;
  padding: 0 14px;
  background: var(--dv-accent, #D97757);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
}
.btn-primary:hover { background: var(--dv-accent-hover); }
.btn-primary:active { transform: scale(0.98); }
.btn-primary:disabled {
  background: var(--dv-faint, #A39E96);
  color: #fff;
  cursor: not-allowed;
  transform: none;
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  padding: 0 14px;
  background: var(--dv-surface);
  color: var(--dv-text);
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  border: 1px solid var(--dv-border);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
}
.btn-secondary:hover { background: var(--dv-hover); border-color: #D4CEC4; }
.btn-secondary:active { transform: scale(0.98); }
</style>
