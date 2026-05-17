<template>
  <div class="bi-gen">
    <div class="bi-gen__card" :class="{ 'bi-gen__card--error': error }">
      <!-- 图表轮播 -->
      <div class="bi-gen__stage" aria-hidden="true">
        <Transition name="chart-fade" mode="out-in">
          <div :key="activeSlide.type" class="bi-gen__chart-wrap">
            <svg
              class="bi-gen__chart"
              :style="{ color: activeSlide.color }"
              viewBox="0 0 120 80"
              fill="none"
              v-html="activeSlide.svg"
            />
          </div>
        </Transition>
      </div>

      <!-- 思考区（Claude 风格） -->
      <div v-if="!error" class="bi-gen__think">
        <div class="bi-gen__think-header">
          <span class="bi-gen__pulse" />
          <span class="bi-gen__think-label">思考中</span>
        </div>
        <Transition name="think-line" mode="out-in">
          <p :key="thinkIndex" class="bi-gen__think-line">{{ thinkingLines[thinkIndex] }}</p>
        </Transition>
        <p class="bi-gen__think-hint">正在为你生成 BI 看板，请稍候</p>
      </div>

      <div v-else class="bi-gen__error-block">
        <p class="bi-gen__error-title">生成未能完成</p>
        <p class="bi-gen__error-msg">{{ error }}</p>
        <button type="button" class="bi-gen__btn bi-gen__btn--primary" @click="$emit('retry')">重新尝试</button>
      </div>

      <!-- 思考过程 -->
      <div v-if="!error" class="bi-gen__journal">
        <button type="button" class="bi-gen__journal-toggle" @click="toggleJournal">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 4h10M2 7h7M2 10h5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          {{ journalOpen ? '收起思考过程' : '查看思考过程' }}
          <svg
            class="bi-gen__chevron"
            :class="{ 'bi-gen__chevron--open': journalOpen }"
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
          >
            <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
        </button>

        <Transition name="journal-expand">
          <div v-if="journalOpen" class="bi-gen__journal-panel">
            <div class="bi-gen__search">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.2"/>
                <path d="M9.5 9.5L12 12" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              </svg>
              <input
                v-model="searchQuery"
                type="search"
                class="bi-gen__search-input"
                placeholder="搜索思考记录…"
                @input="onSearchInput"
              />
            </div>
            <div ref="journalListRef" class="bi-gen__journal-list">
              <p v-if="journalLoading && !filteredEntries.length" class="bi-gen__journal-empty">加载思考记录…</p>
              <p v-else-if="!filteredEntries.length" class="bi-gen__journal-empty">
                {{ searchQuery ? '没有匹配的记录' : '思考记录将在此出现' }}
              </p>
              <div
                v-for="entry in filteredEntries"
                :key="entry.id"
                class="bi-gen__journal-item"
              >
                <time class="bi-gen__journal-time">{{ formatTime(entry.ts) }}</time>
                <p class="bi-gen__journal-text" v-html="highlightText(entry.text)" />
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getBIThinking, type BIThinkingEntry } from '../api'

const props = defineProps<{
  fileId: string
  active?: boolean
  error?: string
}>()

defineEmits<{ retry: [] }>()

const thinkingLines = [
  '阅读各张表的结构与六维业务理解…',
  '从不同业务角色出发，构思值得追问的分析场景…',
  '把场景落实为可量化的问题，并审视是否清晰…',
  '为每个问题挑选合适的图表形态与 SQL…',
  '试跑查询、必要时修复，并整理看板布局…',
]

const slides = [
  {
    type: 'bar',
    label: '柱状图',
    color: '#C6613F',
    svg: `<rect x="8" y="38" width="14" height="34" rx="3" fill="currentColor" opacity="0.85"/>
          <rect x="28" y="28" width="14" height="44" rx="3" fill="currentColor" opacity="0.65"/>
          <rect x="48" y="18" width="14" height="54" rx="3" fill="currentColor" opacity="0.9"/>
          <rect x="68" y="32" width="14" height="40" rx="3" fill="currentColor" opacity="0.7"/>
          <rect x="88" y="42" width="14" height="30" rx="3" fill="currentColor" opacity="0.55"/>`,
  },
  {
    type: 'line',
    label: '折线图',
    color: '#6B8F71',
    svg: `<path d="M6 58 Q26 42 46 48 Q66 54 86 28 Q98 18 110 24" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/>
          <circle cx="46" cy="48" r="4" fill="currentColor"/><circle cx="86" cy="28" r="4" fill="currentColor"/>`,
  },
  {
    type: 'pie',
    label: '饼图',
    color: '#8B7355',
    svg: `<path d="M60 12 A38 38 0 0 1 94 52 L60 50 Z" fill="currentColor" opacity="0.88"/>
          <path d="M94 52 A38 38 0 0 1 32 28 L60 50 Z" fill="currentColor" opacity="0.55"/>
          <path d="M32 28 A38 38 0 0 1 60 12 L60 50 Z" fill="currentColor" opacity="0.35"/>`,
  },
  {
    type: 'table',
    label: '表格',
    color: '#7A6E8A',
    svg: `<rect x="10" y="16" width="100" height="52" rx="4" stroke="currentColor" stroke-width="1.5" opacity="0.35" fill="none"/>
          <line x1="10" y1="30" x2="110" y2="30" stroke="currentColor" stroke-width="1.2" opacity="0.4"/>
          <line x1="10" y1="44" x2="110" y2="44" stroke="currentColor" stroke-width="1" opacity="0.25"/>
          <line x1="10" y1="58" x2="110" y2="58" stroke="currentColor" stroke-width="1" opacity="0.25"/>
          <line x1="42" y1="16" x2="42" y2="68" stroke="currentColor" stroke-width="1" opacity="0.2"/>
          <line x1="74" y1="16" x2="74" y2="68" stroke="currentColor" stroke-width="1" opacity="0.2"/>`,
  },
  {
    type: 'area',
    label: '面积图',
    color: '#5C7A8C',
    svg: `<path d="M6 68 L6 52 Q30 36 54 42 Q78 48 102 26 L102 68 Z" fill="currentColor" opacity="0.22"/>
          <path d="M6 52 Q30 36 54 42 Q78 48 102 26" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round"/>`,
  },
  {
    type: 'rank',
    label: '排名',
    color: '#B8860B',
    svg: `<rect x="12" y="22" width="72" height="8" rx="2" fill="currentColor" opacity="0.9"/>
          <rect x="12" y="36" width="58" height="8" rx="2" fill="currentColor" opacity="0.7"/>
          <rect x="12" y="50" width="44" height="8" rx="2" fill="currentColor" opacity="0.5"/>`,
  },
]

const carouselIndex = ref(0)
const thinkIndex = ref(0)
const journalOpen = ref(false)
const searchQuery = ref('')
const journalEntries = ref<BIThinkingEntry[]>([])
const journalLoading = ref(false)
const journalListRef = ref<HTMLElement | null>(null)

let carouselTimer: ReturnType<typeof setInterval> | null = null
let thinkTimer: ReturnType<typeof setInterval> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let searchDebounce: ReturnType<typeof setTimeout> | null = null

const activeSlide = computed(() => slides[carouselIndex.value])

const filteredEntries = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return journalEntries.value
  return journalEntries.value.filter((e) => {
    const blob = [e.text, e.sheet_name, e.table_name, e.role_name, e.scenario_name]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return blob.includes(q)
  })
})

function formatTime(ts?: string) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ts
  }
}

function escapeHtml(s: string) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function highlightText(text: string) {
  const safe = escapeHtml(text || '')
  const q = searchQuery.value.trim()
  if (!q) return safe
  const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return safe.replace(re, '<mark>$1</mark>')
}

async function fetchJournal() {
  if (!props.fileId) return
  journalLoading.value = true
  try {
    const res = await getBIThinking(props.fileId, searchQuery.value.trim() || undefined)
    journalEntries.value = res.data.data?.entries || []
    if (journalOpen.value && journalListRef.value) {
      requestAnimationFrame(() => {
        journalListRef.value?.scrollTo({ top: journalListRef.value.scrollHeight, behavior: 'smooth' })
      })
    }
  } catch {
    /* 保持已有条目 */
  } finally {
    journalLoading.value = false
  }
}

function onSearchInput() {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    if (journalOpen.value) fetchJournal()
  }, 300)
}

function toggleJournal() {
  journalOpen.value = !journalOpen.value
  if (journalOpen.value) {
    fetchJournal()
    startPoll()
  } else {
    stopPoll()
  }
}

function startCarousel() {
  stopCarousel()
  carouselTimer = setInterval(() => {
    carouselIndex.value = (carouselIndex.value + 1) % slides.length
  }, 2000)
}

function stopCarousel() {
  if (carouselTimer) {
    clearInterval(carouselTimer)
    carouselTimer = null
  }
}

function startThinkCycle() {
  stopThinkCycle()
  thinkTimer = setInterval(() => {
    thinkIndex.value = (thinkIndex.value + 1) % thinkingLines.length
  }, 4200)
}

function stopThinkCycle() {
  if (thinkTimer) {
    clearInterval(thinkTimer)
    thinkTimer = null
  }
}

function startPoll() {
  stopPoll()
  pollTimer = setInterval(() => fetchJournal(), 2500)
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(
  () => props.active,
  (on) => {
    if (on && !props.error) {
      startCarousel()
      startThinkCycle()
      if (journalOpen.value) startPoll()
    } else {
      stopCarousel()
      stopThinkCycle()
      stopPoll()
    }
  },
  { immediate: true }
)

onMounted(() => {
  if (props.active && !props.error) {
    startCarousel()
    startThinkCycle()
  }
})

onUnmounted(() => {
  stopCarousel()
  stopThinkCycle()
  stopPoll()
  if (searchDebounce) clearTimeout(searchDebounce)
})
</script>

<style scoped>
.bi-gen {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - var(--header-height, 52px) - 48px);
  padding: 32px 20px;
  background:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(198, 97, 63, 0.06), transparent),
    #F4F1EA;
  animation: bi-gen-fade-in 0.4s ease;
}

@keyframes bi-gen-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.bi-gen__card {
  width: min(520px, calc(100vw - 40px));
  padding: 44px 40px 36px;
  background: #FDFCFA;
  border: 1px solid rgba(28, 25, 23, 0.08);
  border-radius: 24px;
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.04),
    0 12px 40px rgba(28, 25, 23, 0.07);
  text-align: center;
  animation: bi-gen-card-in 0.45s cubic-bezier(0.25, 0.1, 0.25, 1);
}

@keyframes bi-gen-card-in {
  from {
    opacity: 0;
    transform: translateY(16px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.bi-gen__card--error {
  border-color: rgba(255, 59, 48, 0.15);
}

.bi-gen__stage {
  margin-bottom: 28px;
}

.bi-gen__chart-wrap {
  display: flex;
  align-items: center;
  min-height: 150px;
  justify-content: center;
}

.bi-gen__chart {
  width: 220px;
  height: 147px;
}

.chart-fade-enter-active,
.chart-fade-leave-active {
  transition: opacity 0.35s ease, transform 0.35s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.chart-fade-enter-from {
  opacity: 0;
  transform: scale(0.92) translateY(6px);
}

.chart-fade-leave-to {
  opacity: 0;
  transform: scale(1.04) translateY(-4px);
}

.bi-gen__think {
  text-align: left;
  padding: 0 4px;
}

.bi-gen__think-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.bi-gen__pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #C6613F;
  box-shadow: 0 0 0 0 rgba(198, 97, 63, 0.45);
  animation: pulse-ring 1.8s ease-out infinite;
}

@keyframes pulse-ring {
  0% { box-shadow: 0 0 0 0 rgba(198, 97, 63, 0.45); }
  70% { box-shadow: 0 0 0 10px rgba(198, 97, 63, 0); }
  100% { box-shadow: 0 0 0 0 rgba(198, 97, 63, 0); }
}

.bi-gen__think-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #8B7355;
  text-transform: uppercase;
}

.bi-gen__think-line {
  margin: 0 0 8px;
  font-size: 15px;
  line-height: 1.65;
  color: #3D3835;
  font-weight: 400;
  min-height: 48px;
}

.bi-gen__think-hint {
  margin: 0;
  font-size: 13px;
  color: #A39E96;
  line-height: 1.5;
}

.think-line-enter-active,
.think-line-leave-active {
  transition: opacity 0.28s ease, transform 0.28s ease;
}

.think-line-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.think-line-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.bi-gen__error-block {
  padding: 8px 4px 0;
}

.bi-gen__error-title {
  margin: 0 0 8px;
  font-size: 17px;
  font-weight: 600;
  color: #1C1917;
}

.bi-gen__error-msg {
  margin: 0 0 20px;
  font-size: 14px;
  color: #736C64;
  line-height: 1.55;
}

.bi-gen__journal {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid rgba(28, 25, 23, 0.06);
  text-align: left;
}

.bi-gen__journal-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0;
  border: none;
  background: none;
  font-size: 13px;
  font-weight: 500;
  color: #6B6560;
  cursor: pointer;
  font-family: inherit;
  transition: color 0.15s ease;
}

.bi-gen__journal-toggle:hover {
  color: #C6613F;
}

.bi-gen__chevron {
  transition: transform 0.2s ease;
}

.bi-gen__chevron--open {
  transform: rotate(180deg);
}

.bi-gen__journal-panel {
  margin-top: 14px;
  overflow: hidden;
}

.journal-expand-enter-active,
.journal-expand-leave-active {
  transition: opacity 0.25s ease, max-height 0.3s ease;
  max-height: 320px;
}

.journal-expand-enter-from,
.journal-expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.bi-gen__search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(28, 25, 23, 0.03);
  border: 1px solid rgba(28, 25, 23, 0.08);
  border-radius: 10px;
  margin-bottom: 12px;
  color: #A39E96;
}

.bi-gen__search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #1C1917;
  outline: none;
  font-family: inherit;
}

.bi-gen__search-input::placeholder {
  color: #C4BDB4;
}

.bi-gen__journal-list {
  max-height: 220px;
  overflow-y: auto;
  padding-right: 4px;
}

.bi-gen__journal-list::-webkit-scrollbar {
  width: 4px;
}

.bi-gen__journal-list::-webkit-scrollbar-thumb {
  background: #D4CEC6;
  border-radius: 2px;
}

.bi-gen__journal-empty {
  margin: 0;
  padding: 16px 0;
  font-size: 13px;
  color: #A39E96;
  text-align: center;
}

.bi-gen__journal-item {
  padding: 10px 0;
  border-bottom: 1px solid rgba(28, 25, 23, 0.05);
}

.bi-gen__journal-item:last-child {
  border-bottom: none;
}

.bi-gen__journal-time {
  display: block;
  font-size: 11px;
  color: #C4BDB4;
  margin-bottom: 4px;
  font-variant-numeric: tabular-nums;
}

.bi-gen__journal-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: #4A4541;
}

.bi-gen__journal-text :deep(mark) {
  background: rgba(198, 97, 63, 0.18);
  color: #8B4513;
  border-radius: 2px;
  padding: 0 2px;
}

.bi-gen__btn {
  height: 36px;
  padding: 0 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
}

.bi-gen__btn--primary {
  background: #C6613F;
  color: #FFF;
}

.bi-gen__btn--primary:hover {
  background: #B55534;
}

.bi-gen__btn--primary:active {
  transform: scale(0.98);
}
</style>
