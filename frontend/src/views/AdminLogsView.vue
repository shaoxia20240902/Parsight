<template>
  <div class="logs-view">
    <section class="logs-toolbar">
      <div>
        <h1 class="page-title">日志中心</h1>
        <p class="page-desc">查看生成链路的后端流水线日志，先接入 BI 看板生成，问答链路已预留入口。</p>
      </div>
      <button type="button" class="btn-refresh" :disabled="loadingRuns" @click="loadRuns">
        {{ loadingRuns ? '刷新中…' : '刷新' }}
      </button>
    </section>

    <section class="source-strip">
      <button
        v-for="source in sources"
        :key="source.key"
        type="button"
        class="source-card"
        :class="{ active: activeSource === source.key, disabled: !source.enabled }"
        :disabled="!source.enabled"
        @click="activeSource = source.key"
      >
        <span class="source-name">{{ source.name }}</span>
        <span class="source-desc">{{ source.description }}</span>
      </button>
    </section>

    <section class="logs-grid">
      <aside class="run-list">
        <div class="panel-head">
          <h2>BI 生成批次</h2>
          <span>{{ runs.length }}</span>
        </div>
        <div v-if="loadingRuns" class="empty-state">正在读取日志…</div>
        <div v-else-if="runs.length === 0" class="empty-state">暂无 BI 生成日志</div>
        <template v-else>
          <button
            v-for="run in runs"
            :key="run.run_id"
            type="button"
            class="run-item"
            :class="{ active: selectedRunId === run.run_id }"
            @click="selectRun(run.run_id)"
          >
            <span class="run-row">
              <strong>{{ run.run_id }}</strong>
              <span class="status-pill" :class="`status-${run.status}`">{{ statusText(run.status) }}</span>
            </span>
            <span class="run-meta">{{ formatTime(run.updated_at) }} · {{ run.entry_count }} 条</span>
            <span class="run-last">{{ run.last_step }}：{{ run.last_message }}</span>
          </button>
        </template>
      </aside>

      <main class="log-detail">
        <div v-if="!selectedRunId" class="detail-empty">选择左侧批次查看完整流水线</div>
        <template v-else>
          <div class="detail-head">
            <div>
              <h2>{{ selectedRun?.run_id }}</h2>
              <p>
                {{ formatTime(selectedRun?.started_at) }} - {{ formatTime(selectedRun?.updated_at) }}
                · {{ selectedRun?.entry_count || 0 }} 条日志
              </p>
            </div>
            <div class="detail-metrics">
              <span>图表 {{ selectedRun?.chart_count ?? '—' }}</span>
              <span>警告 {{ selectedRun?.warn_count ?? 0 }}</span>
              <span>错误 {{ selectedRun?.error_count ?? 0 }}</span>
            </div>
          </div>

          <div v-if="loadingDetail" class="empty-state">正在加载详情…</div>
          <div v-else class="timeline">
            <article
              v-for="entry in entries"
              :key="`${entry.time}-${entry.step}-${entry.message}`"
              class="log-entry"
              :class="`level-${entry.level.toLowerCase()}`"
            >
              <div class="entry-top">
                <span class="entry-time">{{ entry.time }}</span>
                <span class="entry-step">{{ entry.step }}</span>
                <span class="entry-level">{{ entry.level }}</span>
              </div>
              <p class="entry-message">{{ entry.message }}</p>
              <div v-if="locationText(entry)" class="entry-location">{{ locationText(entry) }}</div>
              <pre v-if="hasExtra(entry)" class="entry-extra">{{ stringifyExtra(entry.extra) }}</pre>
              <pre v-if="entry.exception" class="entry-exception">{{ entry.exception }}</pre>
            </article>
          </div>
        </template>
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getBILogRun,
  listAdminLogSources,
  listBILogRuns,
  type AdminLogSource,
  type BILogEntry,
  type BILogRun
} from '../api/admin'

const sources = ref<AdminLogSource[]>([])
const activeSource = ref('bi')
const runs = ref<BILogRun[]>([])
const entries = ref<BILogEntry[]>([])
const selectedRunId = ref('')
const loadingRuns = ref(false)
const loadingDetail = ref(false)

const selectedRun = computed(() => runs.value.find((run) => run.run_id === selectedRunId.value))

function statusText(status?: string) {
  if (status === 'completed') return '完成'
  if (status === 'failed') return '失败'
  return '中断/进行中'
}

function formatTime(value?: string) {
  if (!value) return '—'
  const normalized = value.includes('T') ? value : value.replace(' ', 'T')
  const d = new Date(normalized)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}

function locationText(entry: BILogEntry) {
  const loc = entry.location || {}
  return [loc.sheet_name, loc.table_name, loc.role_name, loc.scenario_name, loc.question_id, loc.chart_id]
    .filter(Boolean)
    .join(' / ')
}

function hasExtra(entry: BILogEntry) {
  return entry.extra && Object.keys(entry.extra).length > 0
}

function stringifyExtra(extra: Record<string, any>) {
  return JSON.stringify(extra, null, 2)
}

async function loadSources() {
  try {
    const res = await listAdminLogSources()
    sources.value = res.data.data || []
  } catch {
    sources.value = [
      { key: 'bi', name: 'BI 看板生成', description: 'BI 生成流水线日志', enabled: true },
      { key: 'qa', name: '问答日志', description: '预留', enabled: false }
    ]
  }
}

async function loadRuns() {
  loadingRuns.value = true
  try {
    const res = await listBILogRuns(80)
    runs.value = res.data.data || []
    if (!selectedRunId.value && runs.value.length) {
      await selectRun(runs.value[0].run_id)
    } else if (selectedRunId.value && !runs.value.some((run) => run.run_id === selectedRunId.value)) {
      selectedRunId.value = ''
      entries.value = []
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '加载日志失败')
  } finally {
    loadingRuns.value = false
  }
}

async function selectRun(runId: string) {
  selectedRunId.value = runId
  loadingDetail.value = true
  try {
    const res = await getBILogRun(runId)
    entries.value = res.data.data.entries || []
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '加载日志详情失败')
    entries.value = []
  } finally {
    loadingDetail.value = false
  }
}

onMounted(async () => {
  await loadSources()
  await loadRuns()
})
</script>

<style scoped>
.logs-view {
  --accent: #D97757;
  --surface: #FFFFFF;
  --border: #E5E0D8;
  --text: #1C1917;
  --muted: #736C64;
  --faint: #A39E96;
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: var(--text);
}

.logs-toolbar,
.source-strip,
.run-list,
.log-detail {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
}

.logs-toolbar {
  min-height: 72px;
  padding: 16px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-title,
.panel-head h2,
.detail-head h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
}

.page-desc,
.detail-head p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 13px;
}

.btn-refresh {
  height: 34px;
  padding: 0 14px;
  border: 1px solid rgba(217, 119, 87, 0.35);
  border-radius: 8px;
  background: rgba(217, 119, 87, 0.1);
  color: #C6613F;
  font: inherit;
  cursor: pointer;
}

.source-strip {
  padding: 10px;
  display: flex;
  gap: 8px;
}

.source-card {
  width: 220px;
  min-height: 64px;
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #FDFCFA;
  padding: 10px 12px;
  cursor: pointer;
}

.source-card.active {
  border-color: rgba(217, 119, 87, 0.5);
  background: rgba(217, 119, 87, 0.08);
}

.source-card.disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.source-name,
.source-desc {
  display: block;
}

.source-name {
  font-size: 13px;
  font-weight: 650;
}

.source-desc {
  margin-top: 5px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.35;
}

.logs-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 12px;
}

.run-list,
.log-detail {
  min-height: 0;
  overflow: hidden;
}

.run-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.panel-head,
.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-head {
  padding: 2px 2px 8px;
}

.panel-head span {
  color: var(--faint);
  font-size: 12px;
}

.run-item {
  width: 100%;
  border: 1px solid transparent;
  border-radius: 10px;
  background: #FAF8F5;
  padding: 10px;
  text-align: left;
  cursor: pointer;
}

.run-item.active {
  border-color: rgba(217, 119, 87, 0.45);
  background: rgba(217, 119, 87, 0.08);
}

.run-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.run-row strong {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

.run-meta,
.run-last {
  display: block;
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.35;
}

.run-last {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 2px 7px;
  font-size: 11px;
  background: #EDE8E1;
  color: var(--muted);
}

.status-completed {
  background: rgba(42, 157, 143, 0.12);
  color: #167C70;
}

.status-failed {
  background: rgba(201, 74, 66, 0.12);
  color: #B42318;
}

.log-detail {
  padding: 14px;
  display: flex;
  flex-direction: column;
}

.detail-head {
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.detail-metrics {
  display: flex;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}

.detail-metrics span {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 5px 8px;
  background: #FDFCFA;
}

.timeline {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px 2px 2px;
}

.log-entry {
  border-left: 3px solid #D7D0C6;
  padding: 8px 10px 10px;
  margin-bottom: 10px;
  background: #FAF8F5;
  border-radius: 0 8px 8px 0;
}

.level-warn {
  border-left-color: #D97757;
}

.level-error {
  border-left-color: #C94A42;
}

.entry-top {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}

.entry-step,
.entry-level {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.entry-message {
  margin: 7px 0 0;
  font-size: 13px;
  line-height: 1.45;
}

.entry-location {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
}

.entry-extra,
.entry-exception {
  margin: 8px 0 0;
  padding: 8px;
  max-height: 260px;
  overflow: auto;
  border-radius: 8px;
  background: #F1ECE5;
  color: #3A332E;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
}

.entry-exception {
  background: rgba(201, 74, 66, 0.1);
  color: #8F1D18;
}

.empty-state,
.detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  color: var(--muted);
  font-size: 13px;
}
</style>
