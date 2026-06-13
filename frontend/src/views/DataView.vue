<template>
  <div class="data-view" :class="{ 'data-view--fill': !!currentSpaceId }">
    <div v-if="!currentSpaceId" class="empty-state">
      <div class="empty-icon-wrap">
        <el-icon class="empty-icon"><FolderOpened /></el-icon>
      </div>
      <p class="empty-title">请先选择空间</p>
      <p class="empty-desc">在顶部切换或创建一个空间</p>
    </div>

    <template v-else>
      <div class="toolbar">
        <div class="toolbar-actions">
          <button type="button" class="btn-upload" @click="showUpload = true">
            <el-icon><Plus /></el-icon>
            <span>上传文件</span>
          </button>
          <button
            type="button"
            class="btn-toolbar"
            :disabled="!hasData || exporting"
            @click="handleExport"
          >
            <el-icon><Download /></el-icon>
            <span>{{ exporting ? '导出中…' : '导出' }}</span>
          </button>
          <button
            type="button"
            class="btn-toolbar"
            :disabled="!hasData || reimporting"
            @click="openReimportPicker"
          >
            <el-icon><Refresh /></el-icon>
            <span>更新文件</span>
          </button>
          <input
            ref="reimportInputRef"
            type="file"
            accept=".xlsx,.xls"
            class="hidden-file-input"
            @change="onReimportFileSelected"
          />
        </div>

        <div class="search-area" :class="{ 'is-disabled': relationsMode || !activeTable }">
          <el-select
            v-model="searchField"
            placeholder="所有字段"
            clearable
            size="default"
            class="search-select"
            :disabled="relationsMode || !activeTable"
          >
            <el-option label="所有字段" value="" />
            <el-option
              v-for="col in currentColumns"
              :key="col.name"
              :label="col.name"
              :value="col.name"
            />
          </el-select>
          <el-input
            v-model="searchKeyword"
            placeholder="输入关键词模糊搜索…"
            clearable
            size="default"
            class="search-input"
            :disabled="relationsMode || !activeTable"
            @keyup.enter="doSearch"
            @clear="doSearch"
          >
            <template #prefix>
              <el-icon class="search-icon"><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <div class="mode-switch">
          <button
            class="mode-btn"
            :class="{ active: viewMode === 'data' && !relationsMode, disabled: relationsMode }"
            :disabled="relationsMode"
            @click="switchToData"
          >
            数字内容
          </button>
          <button
            class="mode-btn"
            :class="{ active: viewMode === 'understand' }"
            @click="switchToUnderstand"
          >
            理解内容
          </button>
        </div>
      </div>

      <div class="content-body">
        <TableSidebar
          :tables="tables"
          :loading="loadingTables"
          :active-table="activeTable"
          :relations-active="relationsMode"
          @select="selectTable"
          @relations="switchToRelationsSummary"
        />

        <main class="content-main">
          <div
            class="content-main-inner"
            :class="{ 'content-main-inner--table': activeTable && !relationsMode && viewMode === 'data' }"
          >
            <div v-if="!activeTable && !relationsMode" class="content-empty">
              <el-icon class="empty-icon-lg"><DataBoard /></el-icon>
              <p class="empty-title">选择左侧数据表查看内容</p>
            </div>

            <RelationsCard
              v-else-if="relationsMode"
              :content="relationsContent"
              :content-initial="relationsContentInitial"
              :updated-at="relationsUpdatedAt"
              :loading="loadingRelations"
              :regenerating="regeneratingRelations"
              :verification-status="relationsVerificationStatus"
              @regenerate="regenerateRelations"
            />

            <DataTable
              v-else-if="viewMode === 'data'"
              :rows="tableRows"
              :columns="currentColumns"
              :total="tableTotal"
              :page="currentPage"
              :page-size="pageSize"
              :loading="loadingRows"
              :sheet-name="activeSheetName"
              @change="onTablePageChange"
            />

            <UnderstandCard
              v-else
              :subtitle="activeSheetName"
              :content="understandingContent"
              :content-initial="understandingContentInitial"
              :updated-at="understandingUpdatedAt"
              :loading="loadingUnderstanding"
              :regenerating="regeneratingUnderstanding"
              :verification-status="verificationStatus"
              :stream-connected="isActiveUnderstandingStreamConnected"
              :saving="savingUnderstanding"
              @regenerate="regenerateUnderstanding"
              @save="saveUnderstanding"
              @reconnect="_subscribeUnderstandingStream(activeTable)"
            />
          </div>
        </main>
      </div>
    </template>

    <UploadModal
      :visible="showUpload"
      :uploading="uploading"
      @close="showUpload = false"
      @confirm="handleUpload"
    />

    <UploadProgress
      :visible="showProgress"
      :filename="uploadFilename"
      :current-step="progressStep"
      :step-status="progressStatus"
      :step-messages="progressMessages"
      :progress="progressPct"
      :mode="progressIsReimport ? 'reimport' : 'upload'"
    />

    <ReimportModal
      :visible="showReimportMode"
      :file="pendingReimportFile"
      :warnings="reimportWarnings"
      :mode="reimportMode"
      :reimporting="reimporting"
      @close="showReimportMode = false"
      @confirm="confirmReimport"
    />

    <ValidationErrorModal
      :visible="showValidationError"
      :issues="validationIssues"
      @close="showValidationError = false"
    />

    <UnderstandingPromptModal
      :visible="showUnderstandingPrompt"
      :regenerating="regeneratingAllUnderstanding"
      @skip="skipRegenerateUnderstanding"
      @confirm="regenerateAllUnderstanding"
    />

    <transition name="toast-slide">
      <div
        v-if="understandingToast.show"
        class="understanding-toast"
        :class="`understanding-toast--${understandingToast.status}`"
        @click="onUnderstandingToastClick"
      >
        <span class="understanding-toast__pulse" />
        <span class="understanding-toast__text">{{ understandingToast.message }}</span>
        <button class="understanding-toast__close" @click.stop="hideUnderstandingToast">
          <el-icon><Close /></el-icon>
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  FolderOpened, Search, Plus,
  DataBoard, Close, Download, Refresh
} from '@element-plus/icons-vue'
import {
  getTables, getTableRows,
  getTableUnderstanding, saveTableUnderstanding, getRelations,
  generateTableUnderstandingStream, generateRelationsStream,
  uploadFileStream, validateReimport, reimportFileStream, exportSpaceData,
  type ReimportValidationIssue
} from '../api/data'
import UploadProgress from '../components/UploadProgress.vue'
import TableSidebar from '../components/dataView/TableSidebar.vue'
import DataTable from '../components/dataView/DataTable.vue'
import UnderstandCard from '../components/dataView/UnderstandCard.vue'
import RelationsCard from '../components/dataView/RelationsCard.vue'
import UploadModal from '../components/dataView/UploadModal.vue'
import ReimportModal from '../components/dataView/ReimportModal.vue'
import ValidationErrorModal from '../components/dataView/ValidationErrorModal.vue'
import UnderstandingPromptModal from '../components/dataView/UnderstandingPromptModal.vue'

// ========== 状态 ==========
const currentSpaceId = ref(localStorage.getItem('xlsx-bi-active-space') || '')
const tables = ref<any[]>([])
const activeTable = ref('')
const activeSheetName = ref('')
const currentColumns = ref<any[]>([])
const viewMode = ref<'data' | 'understand'>('data')
const relationsMode = ref(false)

// 关联总结
const relationsContent = ref('')
const relationsContentInitial = ref('')
const relationsUpdatedAt = ref('')
const loadingRelations = ref(false)
const regeneratingRelations = ref(false)
const relationsVerificationStatus = ref<'idle' | 'generating' | 'verifying' | 'completed' | 'failed'>('idle')
let relationsVerifyPollTimer: ReturnType<typeof setInterval> | null = null

// 表格数据
const tableRows = ref<any[]>([])
const tableTotal = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const loadingRows = ref(false)
const loadingTables = ref(false)

// 搜索
const searchKeyword = ref('')
const searchField = ref('')

// 理解数据（Markdown）
const understandingContent = ref('')
const understandingContentInitial = ref('')
const understandingUpdatedAt = ref('')
const understandingDraft = ref('')
const loadingUnderstanding = ref(false)
const savingUnderstanding = ref(false)
const regeneratingUnderstanding = ref(false)
const verificationStatus = ref<'idle' | 'generating' | 'verifying' | 'completed' | 'failed'>('idle')
let verifyPollTimer: ReturnType<typeof setInterval> | null = null

// 上传
const showUpload = ref(false)
const uploading = ref(false)

// 上传进度
const showProgress = ref(false)
const uploadFilename = ref('')
const progressStep = ref('')
const progressStatus = ref<Record<string, string>>({})
const progressMessages = ref<Record<string, string>>({})
const progressPct = ref(0)
const progressIsReimport = ref(false)

// 导出 / 更新
const hasData = computed(() => tables.value.length > 0)
const exporting = ref(false)
const reimporting = ref(false)
const reimportInputRef = ref<HTMLInputElement | null>(null)
const pendingReimportFile = ref<File | null>(null)
const showReimportMode = ref(false)
const reimportMode = ref<'overwrite' | 'insert'>('overwrite')
const reimportWarnings = ref<ReimportValidationIssue[]>([])
const showValidationError = ref(false)
const validationIssues = ref<ReimportValidationIssue[]>([])
const showUnderstandingPrompt = ref(false)
const regeneratingAllUnderstanding = ref(false)
const updatedTableNames = ref<string[]>([])

// 表理解悬浮提示
const understandingToast = ref<{
  show: boolean
  message: string
  tableName: string
  sheetName: string
  status: 'generating' | 'completed'
}>({ show: false, message: '', tableName: '', sheetName: '', status: 'generating' })
let understandingToastTimer: ReturnType<typeof setTimeout> | null = null
let understandingStatusPollTimer: ReturnType<typeof setInterval> | null = null
const understandingStatusMap = ref<Record<string, string>>({})
const understandingStreamState = ref<Record<string, {
  content: string
  contentInitial: string
  updatedAt: string
  status: 'idle' | 'generating' | 'verifying' | 'completed' | 'failed'
  connected: boolean
  error?: string
}>>({})
const activeUnderstandingStreams = new Set<string>()
const activeRelationsStreams = new Set<string>()

// ========== 计算 ==========

const isActiveUnderstandingStreamConnected = computed(() => {
  if (!activeTable.value) return false
  return Boolean(understandingStreamState.value[activeTable.value]?.connected)
})

// ========== 方法 ==========

async function loadTables() {
  if (!currentSpaceId.value) return
  loadingTables.value = true
  try {
    const res = await getTables(currentSpaceId.value)
    tables.value = res.data.data || []
    if (tables.value.length > 0 && !activeTable.value && !relationsMode.value) {
      selectTable(tables.value[0])
    }
  } catch (e) {
    console.error('加载表列表失败', e)
  } finally {
    loadingTables.value = false
  }
}

function selectTable(t: any) {
  relationsMode.value = false
  stopRelationsVerifyPoll()
  activeTable.value = t.table_name
  activeSheetName.value = t.sheet_name
  currentColumns.value = t.columns || []
  currentPage.value = 1
  searchKeyword.value = ''
  searchField.value = ''
  tableRows.value = []
  understandingContent.value = ''
  understandingContentInitial.value = ''
  understandingUpdatedAt.value = ''
  verificationStatus.value = 'idle'
  stopVerifyPoll()
  viewMode.value = 'data'
  loadTableRows()
}

function switchToData() {
  if (relationsMode.value) return
  viewMode.value = 'data'
}

function stopRelationsVerifyPoll() {
  if (relationsVerifyPollTimer) {
    clearInterval(relationsVerifyPollTimer)
    relationsVerifyPollTimer = null
  }
}

function startRelationsVerifyPoll() {
  stopRelationsVerifyPoll()
  if (!currentSpaceId.value) return
  const spaceAtStart = currentSpaceId.value
  let lastUpdated = relationsUpdatedAt.value

  relationsVerifyPollTimer = setInterval(async () => {
    if (currentSpaceId.value !== spaceAtStart || !relationsMode.value) {
      stopRelationsVerifyPoll()
      return
    }
    try {
      const res = await getRelations(spaceAtStart, false)
      const status = res.data.verification_status || 'idle'
      relationsVerificationStatus.value = status
      relationsContentInitial.value = res.data.content_initial || ''

      if (res.data.updated_at && res.data.updated_at !== lastUpdated) {
        relationsContent.value = res.data.content || ''
        relationsUpdatedAt.value = res.data.updated_at || ''
        lastUpdated = res.data.updated_at
      }

      if (status === 'completed') {
        relationsContent.value = res.data.content || ''
        relationsUpdatedAt.value = res.data.updated_at || ''
        stopRelationsVerifyPoll()
        ElMessage.success('跨表关联核对完成，内容已更新')
      } else if (status === 'failed') {
        stopRelationsVerifyPoll()
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
    stopRelationsVerifyPoll()
    startRelationsLongStream(true)
    return
  }
  loadingRelations.value = true
  stopRelationsVerifyPoll()
  try {
    const res = await getRelations(currentSpaceId.value, regenerate)
    relationsContent.value = res.data.content || ''
    relationsContentInitial.value = res.data.content_initial || ''
    relationsUpdatedAt.value = res.data.updated_at || ''
    relationsVerificationStatus.value = res.data.verification_status || 'idle'

    if (relationsVerificationStatus.value === 'verifying') {
      startRelationsVerifyPoll()
    }
  } catch (e) {
    relationsContent.value = ''
    relationsContentInitial.value = ''
    relationsVerificationStatus.value = 'idle'
    ElMessage.error(extractErrorMessage(e))
  } finally {
    loadingRelations.value = false
    regeneratingRelations.value = false
  }
}

async function regenerateRelations() {
  await loadRelations(true)
  if (relationsContent.value) {
    ElMessage.success('已重新生成')
  }
}

async function switchToRelationsSummary() {
  relationsMode.value = true
  activeTable.value = ''
  activeSheetName.value = ''
  currentColumns.value = []
  viewMode.value = 'understand'
  stopVerifyPoll()

  if (!relationsContent.value && !loadingRelations.value) {
    await loadRelations(false)
  } else if (relationsVerificationStatus.value === 'verifying') {
    startRelationsVerifyPoll()
  }
}

async function loadTableRows() {
  if (!activeTable.value) return
  loadingRows.value = true
  try {
    const res = await getTableRows(
      activeTable.value,
      currentPage.value,
      pageSize.value,
      searchKeyword.value,
      searchField.value
    )
    const d = res.data.data
    tableRows.value = d.rows || []
    tableTotal.value = d.total || 0
  } catch (e) {
    console.error('加载表数据失败', e)
  } finally {
    loadingRows.value = false
  }
}

function onTablePageChange(page: number, size: number) {
  currentPage.value = page
  pageSize.value = size
  loadTableRows()
}

function doSearch() {
  currentPage.value = 1
  loadTableRows()
}

function extractErrorMessage(e: unknown): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string }
  return err.response?.data?.detail || err.message || '请求失败'
}

function syncActiveUnderstandingFromStream(tableName: string) {
  if (activeTable.value !== tableName) return
  const state = understandingStreamState.value[tableName]
  if (!state) return
  understandingContent.value = state.content
  understandingContentInitial.value = state.contentInitial
  understandingUpdatedAt.value = state.updatedAt
  understandingDraft.value = state.content
  verificationStatus.value = state.status
}

function startUnderstandingLongStream(table: any, regenerate = false) {
  const tableName = table?.table_name
  if (!tableName || activeUnderstandingStreams.has(tableName)) return
  activeUnderstandingStreams.add(tableName)
  const existing = understandingStreamState.value[tableName]
  understandingStreamState.value[tableName] = {
    content: regenerate ? '' : existing?.content || '',
    contentInitial: regenerate ? '' : existing?.contentInitial || '',
    updatedAt: regenerate ? '' : existing?.updatedAt || '',
    status: 'generating',
    connected: true
  }
  showUnderstandingToastMessage(table.sheet_name || tableName, tableName, 'generating')
  syncActiveUnderstandingFromStream(tableName)

  generateTableUnderstandingStream(
    tableName,
    regenerate,
    (chunk: string) => {
      const state = understandingStreamState.value[tableName]
      if (!state) return
      state.content += chunk
      state.connected = true
      state.status = state.status === 'idle' ? 'generating' : state.status
      syncActiveUnderstandingFromStream(tableName)
    },
    (data: any) => {
      const state = understandingStreamState.value[tableName]
      if (!state) return
      state.content = data.content || state.content
      if (Object.prototype.hasOwnProperty.call(data, 'content_initial')) {
        state.contentInitial = data.content_initial || ''
      }
      state.updatedAt = data.updated_at || state.updatedAt
      state.status = data.verification_status || state.status
      state.connected = state.status === 'generating' || state.status === 'verifying'
      syncActiveUnderstandingFromStream(tableName)
      if (state.status === 'completed') {
        showUnderstandingToastMessage(table.sheet_name || tableName, tableName, 'completed')
      }
    },
    (message: string) => {
      const state = understandingStreamState.value[tableName]
      if (state) {
        state.connected = false
        state.error = message
        state.status = 'failed'
      }
      if (activeTable.value === tableName) ElMessage.error(message)
    }
  ).catch((e: any) => {
    const state = understandingStreamState.value[tableName]
    if (state) {
      state.connected = false
      state.error = e?.message || '长链接已断开'
    }
  }).finally(() => {
    activeUnderstandingStreams.delete(tableName)
    const state = understandingStreamState.value[tableName]
    if (state && state.status !== 'generating' && state.status !== 'verifying') {
      state.connected = false
    }
  })
}

function startRelationsLongStream(regenerate = false) {
  const spaceId = currentSpaceId.value
  if (!spaceId || activeRelationsStreams.has(spaceId)) return
  activeRelationsStreams.add(spaceId)
  if (regenerate) {
    relationsContent.value = ''
    relationsContentInitial.value = ''
    relationsUpdatedAt.value = ''
  }
  relationsVerificationStatus.value = 'generating'
  regeneratingRelations.value = true

  generateRelationsStream(
    spaceId,
    regenerate,
    (chunk: string) => {
      if (currentSpaceId.value !== spaceId) return
      relationsContent.value += chunk
      relationsVerificationStatus.value = relationsVerificationStatus.value === 'idle' ? 'generating' : relationsVerificationStatus.value
    },
    (data: any) => {
      if (currentSpaceId.value !== spaceId) return
      relationsContent.value = data.content || relationsContent.value
      if (Object.prototype.hasOwnProperty.call(data, 'content_initial')) {
        relationsContentInitial.value = data.content_initial || ''
      }
      relationsUpdatedAt.value = data.updated_at || relationsUpdatedAt.value
      relationsVerificationStatus.value = data.verification_status || relationsVerificationStatus.value
    },
    (message: string) => {
      if (currentSpaceId.value === spaceId) ElMessage.error(message)
    }
  ).catch((e: any) => {
    if (currentSpaceId.value === spaceId) ElMessage.error(e?.message || '关联总结长链接已断开，请重新生成')
  }).finally(() => {
    activeRelationsStreams.delete(spaceId)
    regeneratingRelations.value = false
  })
}

function stopVerifyPoll() {
  if (verifyPollTimer) {
    clearInterval(verifyPollTimer)
    verifyPollTimer = null
  }
}

function startVerifyPoll() {
  stopVerifyPoll()
  if (!activeTable.value) return
  const tableAtStart = activeTable.value
  let lastUpdated = understandingUpdatedAt.value

  verifyPollTimer = setInterval(async () => {
    if (activeTable.value !== tableAtStart || viewMode.value !== 'understand') {
      stopVerifyPoll()
      return
    }
    try {
      const res = await getTableUnderstanding(tableAtStart, false)
      const status = res.data.verification_status || 'idle'
      verificationStatus.value = status
      understandingContentInitial.value = res.data.content_initial || ''

      if (res.data.updated_at && res.data.updated_at !== lastUpdated) {
        understandingContent.value = res.data.content || ''
        understandingUpdatedAt.value = res.data.updated_at || ''
        understandingDraft.value = understandingContent.value
        lastUpdated = res.data.updated_at
      }

      if (status === 'completed') {
        understandingContent.value = res.data.content || ''
        understandingUpdatedAt.value = res.data.updated_at || ''
        understandingDraft.value = understandingContent.value
        stopVerifyPoll()
        ElMessage.success('异常点核对完成，理解内容已更新')
      } else if (status === 'failed') {
        stopVerifyPoll()
        ElMessage.error('异常点核对失败，请重新生成')
      }
    } catch {
      // 轮询失败不打断用户阅读
    }
  }, 3000)
}

async function loadUnderstanding(regenerate = false) {
  if (!activeTable.value) return

  // 重新生成走 SSE 流式
  if (regenerate) {
    const target = tables.value.find((t: any) => t.table_name === activeTable.value) || {
      table_name: activeTable.value,
      sheet_name: activeSheetName.value
    }
    startUnderstandingLongStream(target, true)
    return
  }

  const streamed = understandingStreamState.value[activeTable.value]
  if (streamed?.content || streamed?.connected) {
    syncActiveUnderstandingFromStream(activeTable.value)
    return
  }

  // 非重新生成：走普通 GET 读取缓存
  loadingUnderstanding.value = true
  stopVerifyPoll()
  try {
    const res = await getTableUnderstanding(activeTable.value, false)
    understandingContent.value = res.data.content || ''
    understandingContentInitial.value = res.data.content_initial || ''
    understandingUpdatedAt.value = res.data.updated_at || ''
    understandingDraft.value = understandingContent.value
    verificationStatus.value = res.data.verification_status || 'idle'

    // 内容为空但后台正在生成中，自动接入 SSE 流式
    if (!understandingContent.value && (verificationStatus.value === 'verifying' || verificationStatus.value === 'generating')) {
      loadingUnderstanding.value = false
      await _subscribeUnderstandingStream(activeTable.value)
      return
    }

    if (verificationStatus.value === 'verifying') {
      startVerifyPoll()
    }
  } catch (e) {
    understandingContent.value = ''
    verificationStatus.value = 'idle'
    ElMessage.error(extractErrorMessage(e))
    throw e
  } finally {
    loadingUnderstanding.value = false
  }
}

/** 接入表理解的 SSE 流式生成（用于后台任务正在生成时） */
async function _subscribeUnderstandingStream(tableName: string) {
  if (!tableName) return
  const table = tables.value.find((t: any) => t.table_name === tableName) || {
    table_name: tableName,
    sheet_name: activeSheetName.value || tableName
  }
  startUnderstandingLongStream(table, false)
}

async function switchToUnderstand() {
  if (relationsMode.value) return
  if (!activeTable.value) {
    ElMessage.warning('请先选择数据表')
    return
  }
  viewMode.value = 'understand'
  if (!understandingContent.value) {
    try {
      await loadUnderstanding(false)
    } catch {
      viewMode.value = 'data'
    }
  } else if (verificationStatus.value === 'verifying') {
    startVerifyPoll()
  }
}

async function saveUnderstanding(content: string) {
  if (!activeTable.value) return
  savingUnderstanding.value = true
  try {
    const res = await saveTableUnderstanding(activeTable.value, content)
    understandingContent.value = res.data.content
    understandingUpdatedAt.value = res.data.updated_at || ''
    verificationStatus.value = res.data.verification_status || 'idle'
    stopVerifyPoll()
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    savingUnderstanding.value = false
  }
}

async function regenerateUnderstanding() {
  if (!activeTable.value) return
  try {
    await loadUnderstanding(true)
  } catch (e) {
    // 错误已在 loadUnderstanding 中提示
  }
}

// ========== 导出 / 更新 ==========

async function handleExport() {
  if (!currentSpaceId.value || !hasData.value) return
  exporting.value = true
  try {
    await exportSpaceData(currentSpaceId.value, `析见导出_${Date.now()}.xlsx`)
    ElMessage.success('导出成功')
  } catch (e: any) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

function openReimportPicker() {
  if (!hasData.value) return
  reimportInputRef.value?.click()
}

function resetReimportInput() {
  if (reimportInputRef.value) reimportInputRef.value.value = ''
}

async function onReimportFileSelected(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  resetReimportInput()
  if (!file || !currentSpaceId.value) return

  try {
    const res = await validateReimport(file, currentSpaceId.value)
    const data = res.data.data
    if (!data.valid) {
      validationIssues.value = data.issues || []
      showValidationError.value = true
      return
    }
    pendingReimportFile.value = file
    reimportWarnings.value = data.warnings || []
    reimportMode.value = 'overwrite'
    showReimportMode.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '文件校验失败')
  }
}

async function confirmReimport(mode: 'overwrite' | 'insert') {
  const file = pendingReimportFile.value
  if (!file || !currentSpaceId.value) return

  reimporting.value = true
  showReimportMode.value = false
  showProgress.value = true
  progressIsReimport.value = true
  uploadFilename.value = file.name
  progressStatus.value = {
    saving: 'pending',
    parsing: 'pending',
    importing: 'pending',
    done: 'pending'
  }
  progressMessages.value = {}
  progressPct.value = 0

  try {
    const result = await reimportFileStream(
      file,
      currentSpaceId.value,
      mode,
      (event: any) => {
        progressStep.value = event.step
        if (event.step === 'error') {
          progressStatus.value[event.step] = 'error'
        } else if (event.step === 'done') {
          Object.keys(progressStatus.value).forEach((k) => {
            progressStatus.value[k] = 'completed'
          })
        } else {
          progressStatus.value[event.step] = event.status
        }
        if (event.message) progressMessages.value[event.step] = event.message
        if (event.progress !== undefined) progressPct.value = event.progress
      }
    )
    updatedTableNames.value = (result?.tables || []).map((t: any) => t.table_name)
    ElMessage.success('数据更新成功')
    await loadTables()
    if (activeTable.value) await loadTableRows()
    showUnderstandingPrompt.value = true
  } catch (e: any) {
    ElMessage.error('更新失败：' + (e.message || '未知错误'))
  } finally {
    reimporting.value = false
    pendingReimportFile.value = null
    setTimeout(() => {
      showProgress.value = false
      progressIsReimport.value = false
    }, 1500)
  }
}

function skipRegenerateUnderstanding() {
  showUnderstandingPrompt.value = false
  updatedTableNames.value = []
}

async function regenerateAllUnderstanding() {
  const names = updatedTableNames.value.length
    ? updatedTableNames.value
    : tables.value.map((t) => t.table_name)
  if (!names.length) {
    showUnderstandingPrompt.value = false
    return
  }

  regeneratingAllUnderstanding.value = true
  let ok = 0
  try {
    for (const tableName of names) {
      const table = tables.value.find((t: any) => t.table_name === tableName) || { table_name: tableName, sheet_name: tableName }
      startUnderstandingLongStream(table, true)
      ok++
    }
    ElMessage.success(`已触发 ${ok} 张表的理解重新生成`)
    if (activeTable.value && viewMode.value === 'understand') {
      await loadUnderstanding()
    }
  } catch (e: any) {
    ElMessage.error(e.message || '重新生成理解失败')
  } finally {
    regeneratingAllUnderstanding.value = false
    showUnderstandingPrompt.value = false
    updatedTableNames.value = []
  }
}

// ========== 上传 ==========

async function handleUpload(file: File) {
  if (!file) return
  uploading.value = true
  showUpload.value = false
  showProgress.value = true
  progressIsReimport.value = false
  uploadFilename.value = file.name

  const resetProgress = () => {
    progressStatus.value = {
      saving: 'pending',
      parsing: 'pending',
      creating_tables: 'pending',
      inserting_data: 'pending',
      analyzing: 'pending',
      done: 'pending'
    }
    progressMessages.value = {}
    progressPct.value = 0
  }
  resetProgress()

  try {
    const uploadResult = await uploadFileStream(
      file,
      currentSpaceId.value,
      (event: any) => {
        progressStep.value = event.step
        if (event.step === 'error') {
          progressStatus.value[event.step] = 'error'
        } else if (event.step === 'done') {
          Object.keys(progressStatus.value).forEach(k => {
            progressStatus.value[k] = 'completed'
          })
        } else {
          progressStatus.value[event.step] = event.status
        }
        if (event.message) {
          progressMessages.value[event.step] = event.message
        }
        if (event.progress !== undefined) {
          progressPct.value = event.progress
        }
      }
    )
    ElMessage.success('文件导入成功')
    activeTable.value = ''
    await loadTables()
    const uploadedSheets = uploadResult?.sheets || tables.value
    for (const sheet of uploadedSheets) {
      startUnderstandingLongStream({
        table_name: sheet.table_name,
        sheet_name: sheet.sheet_name || sheet.name || sheet.table_name
      })
    }
    startRelationsLongStream(false)
    // 保留轮询作为刷新/断线后的兜底提示
    startUnderstandingStatusPoll()
  } catch (e: any) {
    ElMessage.error('上传失败：' + (e.message || '未知错误'))
  } finally {
    uploading.value = false
    setTimeout(() => {
      showProgress.value = false
    }, 1500)
  }
}

// ========== 表理解悬浮提示 ==========

function showUnderstandingToastMessage(
  sheetName: string,
  tableName: string,
  status: 'generating' | 'completed'
) {
  const message =
    status === 'generating'
      ? `【${sheetName}】表理解正在生成，点击查看`
      : `【${sheetName}】表理解已完成，点击查看`
  understandingToast.value = { show: true, message, tableName, sheetName, status }

  if (understandingToastTimer) clearTimeout(understandingToastTimer)
  understandingToastTimer = setTimeout(() => {
    hideUnderstandingToast()
  }, 3000)
}

function hideUnderstandingToast() {
  understandingToast.value.show = false
  if (understandingToastTimer) {
    clearTimeout(understandingToastTimer)
    understandingToastTimer = null
  }
}

function onUnderstandingToastClick() {
  const { tableName } = understandingToast.value
  if (!tableName) return
  const t = tables.value.find((tbl: any) => tbl.table_name === tableName)
  if (!t) return

  // 直接切换到理解模式，不调用 selectTable（避免 understandingContent 被清空）
  relationsMode.value = false
  stopRelationsVerifyPoll()
  activeTable.value = tableName
  activeSheetName.value = t.sheet_name
  currentColumns.value = t.columns || []
  viewMode.value = 'understand'

  // 加载表理解（如果已有缓存则快速返回，不会长时间骨架屏）
  loadUnderstanding(false)

  hideUnderstandingToast()
}

function stopUnderstandingStatusPoll() {
  if (understandingStatusPollTimer) {
    clearInterval(understandingStatusPollTimer)
    understandingStatusPollTimer = null
  }
}

function startUnderstandingStatusPoll() {
  stopUnderstandingStatusPoll()
  if (!tables.value.length) return

  // 初始化状态映射
  const initialMap: Record<string, string> = {}
  for (const t of tables.value) {
    initialMap[t.table_name] = 'idle'
  }
  understandingStatusMap.value = initialMap

  let pollCount = 0
  const maxPolls = 120 // 最多轮询 120 次（约 6 分钟）

  understandingStatusPollTimer = setInterval(async () => {
    pollCount++
    if (pollCount > maxPolls) {
      stopUnderstandingStatusPoll()
      return
    }

    const currentTables = tables.value
    if (!currentTables.length) return

    let allCompleted = true
    let anyGenerating = false

    for (const t of currentTables) {
      try {
        const res = await getTableUnderstanding(t.table_name, false)
        const status = res.data.verification_status || 'idle'
        const prevStatus = understandingStatusMap.value[t.table_name] || 'idle'

        // 状态变化检测
        if (prevStatus === 'idle' && (status === 'verifying' || status === 'generating')) {
          showUnderstandingToastMessage(t.sheet_name, t.table_name, 'generating')
        } else if ((prevStatus === 'verifying' || prevStatus === 'generating') && status === 'completed') {
          showUnderstandingToastMessage(t.sheet_name, t.table_name, 'completed')
        }

        understandingStatusMap.value[t.table_name] = status

        if (status !== 'completed' && status !== 'failed') {
          allCompleted = false
        }
        if (status === 'verifying') {
          anyGenerating = true
        }
      } catch {
        // 忽略单张表查询失败
      }
    }

    // 所有表都完成或失败，停止轮询
    if (allCompleted && !anyGenerating) {
      stopUnderstandingStatusPoll()
    }
  }, 3000)
}

// ========== 监听空间切换 ==========
watch(currentSpaceId, () => {
  localStorage.setItem('xlsx-bi-active-space', currentSpaceId.value)
  activeTable.value = ''
  relationsMode.value = false
  relationsContent.value = ''
  relationsContentInitial.value = ''
  relationsUpdatedAt.value = ''
  stopRelationsVerifyPoll()
  tables.value = []
  loadTables()
})

onMounted(() => {
  loadTables()
  window.addEventListener('space-changed', ((e: CustomEvent) => {
    currentSpaceId.value = e.detail?.id || ''
  }) as EventListener)
})

onUnmounted(() => {
  stopVerifyPoll()
  stopRelationsVerifyPoll()
  stopUnderstandingStatusPoll()
  if (understandingToastTimer) clearTimeout(understandingToastTimer)
})
</script>

<style scoped>
.data-view,
.modal-panel {
  --dv-accent: #D97757;
  --dv-accent-hover: #C6613F;
  --dv-accent-soft: rgba(217, 119, 87, 0.12);
  --dv-bg: #F5F2EB;
  --dv-surface: #FFFFFF;
  --dv-surface-muted: #FAF8F5;
  --dv-border: #E5E0D8;
  --dv-text: #1C1917;
  --dv-muted: #736C64;
  --dv-faint: #A39E96;
  --dv-hover: rgba(28, 25, 23, 0.05);
}

.data-view {
  max-width: none;
  color: var(--dv-text);
}

.data-view--fill {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--header-height, 52px) - 20px);
  min-height: 0;
}

/* ========== Toolbar ========== */
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.btn-upload {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  flex-shrink: 0;
  background: var(--dv-accent);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s var(--ease-out), transform 0.15s var(--ease-out);
}

.btn-upload:hover {
  background: var(--dv-accent-hover);
}

.btn-upload:active {
  transform: scale(0.98);
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.btn-toolbar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  background: var(--dv-surface);
  color: var(--dv-text);
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  border: 1px solid var(--dv-border);
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s var(--ease-out), border-color 0.15s var(--ease-out), transform 0.15s var(--ease-out);
}

.btn-toolbar:hover:not(:disabled) {
  background: var(--dv-surface-muted);
  border-color: #D4CEC4;
}

.btn-toolbar:active:not(:disabled) {
  transform: scale(0.98);
}

.btn-toolbar:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.hidden-file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.search-area {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.search-area.is-disabled {
  opacity: 0.45;
  pointer-events: none;
}

.search-select {
  width: 128px;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  min-width: 120px;
}

.search-icon {
  color: var(--dv-faint);
}

.toolbar :deep(.el-input__wrapper),
.toolbar :deep(.el-select__wrapper) {
  background: var(--dv-surface);
  border-radius: 10px;
  box-shadow: none;
  border: 1px solid var(--dv-border);
  transition: border-color 0.15s var(--ease-out), box-shadow 0.15s var(--ease-out);
}

.toolbar :deep(.el-input__wrapper:hover),
.toolbar :deep(.el-select__wrapper:hover) {
  border-color: #D4CEC4;
}

.toolbar :deep(.el-input__wrapper.is-focus),
.toolbar :deep(.el-select__wrapper.is-focused) {
  border-color: var(--dv-accent);
  box-shadow: 0 0 0 3px var(--dv-accent-soft);
}

/* Mode Switch */
.mode-switch {
  display: flex;
  flex-shrink: 0;
  background: var(--dv-surface-muted);
  border: 1px solid var(--dv-border);
  border-radius: 10px;
  padding: 3px;
}

.mode-btn {
  padding: 6px 14px;
  border: none;
  background: transparent;
  border-radius: 8px;
  color: var(--dv-muted);
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
}

.mode-btn:hover:not(:disabled) {
  color: var(--dv-text);
}

.mode-btn.active {
  background: var(--dv-surface);
  color: var(--dv-accent);
  box-shadow: 0 1px 2px rgba(28, 25, 23, 0.06);
}

.mode-btn.disabled,
.mode-btn:disabled {
  color: var(--dv-faint);
  cursor: not-allowed;
  opacity: 0.55;
}

.mode-btn.disabled.active,
.mode-btn:disabled.active {
  background: transparent;
  color: var(--dv-faint);
  box-shadow: none;
}

/* ========== Content Body ========== */
.content-body {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

/* ========== Main Content ========== */
.content-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--dv-surface);
  border: 1px solid var(--dv-border);
  border-radius: 12px;
  box-shadow: none;
  overflow: hidden;
}

.content-main-inner {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0;
}

/* 数字内容：仅表格滚动，分页固定底部 */
.content-main-inner--table {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.content-main-inner--table :deep(.table-card) {
  flex: 1;
  min-height: 0;
  height: auto;
}

.content-main-inner--table :deep(.table-wrap) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.content-main-inner--table :deep(.table-footer) {
  flex-shrink: 0;
  background: var(--dv-surface);
}

.content-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 80px 20px;
  background: transparent;
  border-radius: var(--radius-xl);
  box-shadow: none;
}

.empty-icon-lg {
  font-size: 56px;
  color: var(--color-text-tertiary);
  opacity: 0.2;
  margin-bottom: var(--spacing-base);
}

/* ========== Empty State ========== */
.empty-state {
  text-align: center;
  padding: 48px 24px;
  background: var(--dv-surface);
  border: 1px solid var(--dv-border);
  border-radius: 12px;
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
  font-size: 15px;
  font-weight: 500;
  color: var(--dv-muted);
  margin-bottom: 4px;
}

.empty-desc {
  font-size: 13px;
  color: var(--dv-faint);
}

/* ========== Transitions ========== */
.modal-fade-enter-active {
  transition: opacity 0.25s var(--ease-out);
}
.modal-fade-leave-active {
  transition: opacity 0.2s var(--ease-out);
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* ========== 表理解悬浮提示 ========== */
.understanding-toast {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 2000;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(139, 60, 38, 0.28), 0 1px 3px rgba(0, 0, 0, 0.1);
  transition: all 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
  max-width: 380px;
  min-width: 240px;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.understanding-toast--generating {
  background: linear-gradient(135deg, #B54D2F 0%, #9A3D24 100%);
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.understanding-toast--completed {
  background: linear-gradient(135deg, #2D7A4B 0%, #236B3E 100%);
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.understanding-toast:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 22px rgba(139, 60, 38, 0.35), 0 2px 6px rgba(0, 0, 0, 0.12);
}

.understanding-toast:active {
  transform: translateY(0) scale(0.98);
}

.understanding-toast__pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.55);
  animation: toast-pulse 1.6s ease-out infinite;
  flex-shrink: 0;
}

.understanding-toast--completed .understanding-toast__pulse {
  background: #A5E8C0;
  box-shadow: 0 0 0 0 rgba(165, 232, 192, 0.55);
  animation: toast-pulse-completed 1.6s ease-out infinite;
}

@keyframes toast-pulse {
  0% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.55); }
  70% { box-shadow: 0 0 0 10px rgba(255, 255, 255, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); }
}

@keyframes toast-pulse-completed {
  0% { box-shadow: 0 0 0 0 rgba(165, 232, 192, 0.55); }
  70% { box-shadow: 0 0 0 10px rgba(165, 232, 192, 0); }
  100% { box-shadow: 0 0 0 0 rgba(165, 232, 192, 0); }
}

.understanding-toast__text {
  flex: 1;
  line-height: 1.45;
  word-break: break-word;
}

.understanding-toast__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  margin-left: 4px;
  background: rgba(255, 255, 255, 0.15);
  border: none;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.understanding-toast__close:hover {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}

.toast-slide-enter-active {
  transition: all 0.35s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.toast-slide-leave-active {
  transition: all 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateX(40px) scale(0.96);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(40px) scale(0.96);
}
</style>
