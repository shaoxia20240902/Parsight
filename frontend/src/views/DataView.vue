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
        <!-- 左侧表列表 -->
        <aside class="table-sidebar">
          <div class="sidebar-label">数据表</div>
          <div v-if="loadingTables" class="sidebar-loading">
            <div class="skeleton-line" v-for="i in 3" :key="i"></div>
          </div>
          <div v-else-if="tables.length === 0" class="sidebar-empty">
            <p>暂无数据表</p>
            <p class="sidebar-empty-desc">上传 XLSX 文件开始</p>
          </div>
          <template v-else>
            <div class="table-list-scroll">
              <div class="table-list">
                <div
                  v-for="t in tables"
                  :key="t.table_name"
                  class="table-list-item"
                  :class="{ active: !relationsMode && activeTable === t.table_name }"
                  @click="selectTable(t)"
                >
                  <div class="table-item-name">{{ t.sheet_name }}</div>
                  <div class="table-item-meta">{{ t.row_count }} 行 · {{ (t.columns || []).length }} 列</div>
                </div>
              </div>
            </div>
            <button
              type="button"
              class="relations-summary-btn"
              :class="{ active: relationsMode }"
              @click="switchToRelationsSummary"
            >
              <el-icon class="relations-summary-icon"><Connection /></el-icon>
              关联总结
            </button>
          </template>
        </aside>

        <!-- 右侧内容区（可滚动） -->
        <main class="content-main">
          <div
            class="content-main-inner"
            :class="{ 'content-main-inner--table': activeTable && !relationsMode && viewMode === 'data' }"
          >
          <!-- 未选择表且非关联模式 -->
          <div v-if="!activeTable && !relationsMode" class="content-empty">
            <el-icon class="empty-icon-lg"><DataBoard /></el-icon>
            <p class="empty-title">选择左侧数据表查看内容</p>
          </div>

          <!-- 关联总结 -->
          <template v-else-if="relationsMode">
            <div class="understand-section">
              <div class="card understand-card">
                <div v-if="showRelationsStageProgress" class="stage-progress">
                  <div class="stage-progress-head">
                    <span class="stage-progress-title">{{ activeRelationsStage.title }}</span>
                    <span class="stage-progress-desc">{{ activeRelationsStage.desc }}</span>
                  </div>
                  <div class="stage-progress-track">
                    <div
                      v-for="(stage, index) in relationsProgressStages"
                      :key="stage.title"
                      class="stage-progress-item"
                      :class="{
                        active: index === activeRelationsStageIndex,
                        complete: index < activeRelationsStageIndex,
                        pending: index > activeRelationsStageIndex
                      }"
                    >
                      <span class="stage-progress-dot">
                        <el-icon v-if="index === activeRelationsStageIndex" class="stage-progress-spinner is-loading">
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
                        · 更新于 {{ formatUnderstandingTime(relationsUpdatedAt) }}
                      </span>
                    </p>
                  </div>
                  <div v-if="relationsContent && !loadingRelations" class="understand-actions">
                    <div v-if="showRelationsCompareToggle" class="compare-toggle">
                      <button
                        type="button"
                        class="compare-btn"
                        :class="{ active: relationsContentViewMode === 'current' }"
                        @click="relationsContentViewMode = 'current'"
                      >
                        核对后
                      </button>
                      <button
                        type="button"
                        class="compare-btn"
                        :class="{ active: relationsContentViewMode === 'initial' }"
                        @click="relationsContentViewMode = 'initial'"
                      >
                        核对前
                      </button>
                    </div>
                    <button
                      class="btn-secondary btn-sm"
                      :disabled="regeneratingRelations"
                      @click="regenerateRelations"
                    >
                      {{ regeneratingRelations ? '生成中…' : '重新生成' }}
                    </button>
                  </div>
                </div>

                <div v-if="loadingRelations" class="understand-skeleton">
                  <div v-for="i in 6" :key="i" class="skeleton-line" :class="{ 'skeleton-title': i === 1 }"></div>
                </div>

                <div
                  v-else-if="displayRelationsContent"
                  class="understand-markdown"
                  v-html="renderedRelationsContent"
                />

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
            </div>
          </template>
                  
          <!-- 数字模式 -->
          <template v-else-if="viewMode === 'data'">
            <div class="table-card">
              <div class="table-card-header">
                <h2 class="table-card-title">{{ activeSheetName }}</h2>
                <span class="table-card-count">共 {{ tableTotal }} 条</span>
              </div>
              <div class="table-wrap">
                <el-table
                  :data="tableRows"
                  stripe
                  v-loading="loadingRows"
                  element-loading-text="加载中..."
                  class="apple-table"
                  height="100%"
                >
                  <el-table-column
                    v-for="col in currentColumns"
                    :key="col.name"
                    :prop="col.name"
                    :label="col.name"
                    :min-width="140"
                    show-overflow-tooltip
                  >
                    <template #default="{ row }">
                      <span :class="{ 'cell-num': col.type === 'number' }">
                        {{ formatCell(row[col.name], col.type) }}
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <div class="table-footer">
                <el-pagination
                  v-model:current-page="currentPage"
                  v-model:page-size="pageSize"
                  :total="tableTotal"
                  :page-sizes="[20, 50, 100]"
                  layout="total, sizes, prev, pager, next"
                  small
                  @change="loadTableRows"
                />
              </div>
            </div>
          </template>

          <!-- 理解模式：单卡片 Markdown -->
          <template v-else>
            <div class="understand-section">
              <div class="card understand-card">
                <div v-if="showUnderstandingStageProgress" class="stage-progress">
                  <div class="stage-progress-head">
                    <span class="stage-progress-title">{{ activeUnderstandingStage.title }}</span>
                    <span class="stage-progress-desc">{{ activeUnderstandingStage.desc }}</span>
                  </div>
                  <div class="stage-progress-track">
                    <div
                      v-for="(stage, index) in understandingProgressStages"
                      :key="stage.title"
                      class="stage-progress-item"
                      :class="{
                        active: index === activeUnderstandingStageIndex,
                        complete: index < activeUnderstandingStageIndex,
                        pending: index > activeUnderstandingStageIndex
                      }"
                    >
                      <span class="stage-progress-dot">
                        <el-icon v-if="index === activeUnderstandingStageIndex" class="stage-progress-spinner is-loading">
                          <Loading />
                        </el-icon>
                      </span>
                      <span class="stage-progress-label">{{ stage.title }}</span>
                    </div>
                  </div>
                </div>
                <div class="understand-card-header">
                  <div>
                    <h3 class="card-title">AI 业务理解</h3>
                    <p v-if="activeSheetName" class="understand-subtitle">
                      {{ activeSheetName }}
                      <span v-if="understandingUpdatedAt" class="understand-meta">
                        · 更新于 {{ formatUnderstandingTime(understandingUpdatedAt) }}
                      </span>
                    </p>
                  </div>
                  <div v-if="understandingContent && !loadingUnderstanding" class="understand-actions">
                    <div v-if="showCompareToggle && !isEditingUnderstanding" class="compare-toggle">
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
                    <template v-if="isEditingUnderstanding">
                      <button class="btn-secondary btn-sm" @click="cancelEditUnderstanding">取消</button>
                      <button class="btn-primary btn-sm" :disabled="savingUnderstanding" @click="saveUnderstanding">
                        {{ savingUnderstanding ? '保存中…' : '保存' }}
                      </button>
                    </template>
                    <template v-else>
                      <button class="btn-secondary btn-sm" :disabled="regeneratingUnderstanding" @click="regenerateUnderstanding">
                        {{ regeneratingUnderstanding ? '生成中…' : '重新生成' }}
                      </button>
                      <button class="btn-primary btn-sm" @click="startEditUnderstanding">编辑</button>
                    </template>
                  </div>
                </div>

                <div v-if="loadingUnderstanding" class="understand-skeleton">
                  <div v-for="i in 6" :key="i" class="skeleton-line" :class="{ 'skeleton-title': i === 1 }"></div>
                </div>

                <textarea
                  v-else-if="isEditingUnderstanding"
                  v-model="understandingDraft"
                  class="understand-editor"
                  placeholder="在此编辑 AI 理解内容（支持 Markdown）…"
                />

                <div
                  v-else-if="understandingContent"
                  class="understand-markdown"
                  v-html="renderedUnderstanding"
                />

                <div v-else class="parsing-state">
                  <div class="parsing-card">
                    <div class="parsing-animation">
                      <div class="parsing-dot"></div>
                      <div class="parsing-dot"></div>
                      <div class="parsing-dot"></div>
                    </div>
                    <div class="parsing-text">
                      <span class="parsing-title">正在解析数据…</span>
                      <span class="parsing-desc">AI 正在分析表结构与样本，生成业务理解</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
          </div>
        </main>
      </div>
    </template>

    <!-- 上传弹窗 -->
    <teleport to="body">
      <transition name="modal-fade">
        <div v-if="showUpload" class="modal-overlay" @click.self="showUpload = false">
          <div class="modal-panel upload-modal">
            <div class="modal-header">
              <h3 class="modal-title">上传 XLSX 文件</h3>
              <button class="modal-close" @click="showUpload = false">
                <el-icon><Close /></el-icon>
              </button>
            </div>

            <el-upload
              class="upload-area"
              drag
              :auto-upload="false"
              :on-change="handleFileChange"
              :show-file-list="false"
              accept=".xlsx,.xls"
            >
              <div class="upload-inner">
                <div class="upload-icon-wrap">
                  <el-icon class="upload-icon"><UploadFilled /></el-icon>
                </div>
                <div class="upload-text">
                  将文件拖到此处，或<span class="upload-link">点击上传</span>
                </div>
                <div class="upload-tip">支持 .xlsx / .xls 格式，最多 5 个 Sheet</div>
              </div>
            </el-upload>

            <div v-if="selectedFile" class="selected-file">
              <el-icon><Document /></el-icon>
              <span>{{ selectedFile.name }}</span>
            </div>

            <div class="modal-footer">
              <button class="btn-secondary" @click="showUpload = false">取消</button>
              <button class="btn-primary" :disabled="!selectedFile || uploading" @click="handleUpload">
                {{ uploading ? '上传中…' : '确认上传' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>

    <!-- 上传/更新进度 -->
    <UploadProgress
      :visible="showProgress"
      :filename="uploadFilename"
      :current-step="progressStep"
      :step-status="progressStatus"
      :step-messages="progressMessages"
      :progress="progressPct"
      :mode="progressIsReimport ? 'reimport' : 'upload'"
    />

    <!-- 更新模式选择 -->
    <teleport to="body">
      <transition name="modal-fade">
        <div v-if="showReimportMode" class="modal-overlay" @click.self="closeReimportMode">
          <div class="modal-panel reimport-modal">
            <div class="modal-header">
              <h3 class="modal-title">选择更新方式</h3>
              <button class="modal-close" @click="closeReimportMode">
                <el-icon><Close /></el-icon>
              </button>
            </div>
            <p class="reimport-file-name">
              <el-icon><Document /></el-icon>
              {{ pendingReimportFile?.name }}
            </p>
            <div class="reimport-mode-list">
              <label class="reimport-mode-item" :class="{ active: reimportMode === 'overwrite' }">
                <input v-model="reimportMode" type="radio" value="overwrite" />
                <div class="mode-body">
                  <span class="mode-title">全量覆盖</span>
                  <span class="mode-desc">清空各表现有数据，用新文件内容完整替换</span>
                </div>
              </label>
              <label class="reimport-mode-item" :class="{ active: reimportMode === 'insert' }">
                <input v-model="reimportMode" type="radio" value="insert" />
                <div class="mode-body">
                  <span class="mode-title">全量插入</span>
                  <span class="mode-desc">保留现有数据，将新文件全部行追加到表尾</span>
                </div>
              </label>
            </div>
            <div v-if="reimportWarnings.length" class="reimport-warnings">
              <p v-for="(w, i) in reimportWarnings" :key="i">{{ w.message }}</p>
            </div>
            <div class="modal-footer">
              <button class="btn-secondary" @click="closeReimportMode">取消</button>
              <button class="btn-primary" :disabled="reimporting" @click="confirmReimport">
                {{ reimporting ? '更新中…' : '开始更新' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>

    <!-- 字段校验失败 -->
    <teleport to="body">
      <transition name="modal-fade">
        <div v-if="showValidationError" class="modal-overlay" @click.self="showValidationError = false">
          <div class="modal-panel validation-modal">
            <div class="modal-header">
              <h3 class="modal-title">无法更新：表结构不一致</h3>
              <button class="modal-close" @click="showValidationError = false">
                <el-icon><Close /></el-icon>
              </button>
            </div>
            <p class="validation-intro">请修正 Excel 后重新选择文件。各 Sheet 须与当前已导入表<strong>字段名及顺序完全一致</strong>。</p>
            <ul class="validation-list">
              <li v-for="(issue, i) in validationIssues" :key="i">
                <p class="validation-msg">{{ issue.message }}</p>
                <p v-if="issue.detail" class="validation-detail">{{ issue.detail }}</p>
                <p v-if="issue.expected_columns?.length" class="validation-cols">
                  当前字段：{{ issue.expected_columns.join('、') }}
                </p>
                <p v-if="issue.actual_columns?.length" class="validation-cols validation-cols--actual">
                  文件字段：{{ issue.actual_columns.join('、') }}
                </p>
              </li>
            </ul>
            <div class="modal-footer">
              <button class="btn-primary" @click="showValidationError = false">我知道了</button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>

    <!-- 更新后：是否重新生成理解 -->
    <teleport to="body">
      <transition name="modal-fade">
        <div v-if="showUnderstandingPrompt" class="modal-overlay">
          <div class="modal-panel understanding-prompt-modal">
            <h3 class="modal-title">数据已更新</h3>
            <p class="understanding-prompt-lead">是否重新生成各表的「理解内容」？</p>
            <div class="understanding-prompt-tips">
              <p><strong>通常无需重新生成</strong>：若本次仅为行数增减、数值刷新，字段含义与表结构未变，现有理解仍可继续使用。</p>
              <p><strong>建议重新生成</strong>：若调整了表头含义、业务口径变化较大，或覆盖后数据语义已与原理解明显不符。</p>
            </div>
            <div class="modal-footer">
              <button class="btn-secondary" :disabled="regeneratingAllUnderstanding" @click="skipRegenerateUnderstanding">
                暂不生成
              </button>
              <button class="btn-primary" :disabled="regeneratingAllUnderstanding" @click="regenerateAllUnderstanding">
                {{ regeneratingAllUnderstanding ? '生成中…' : '重新生成理解' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import {
  UploadFilled, Document, FolderOpened, Search, Plus,
  DataBoard, Close, Loading, Connection, Download, Refresh
} from '@element-plus/icons-vue'
import {
  getTables, getTableRows,
  getTableUnderstanding, saveTableUnderstanding, getRelations,
  uploadFileStream, validateReimport, reimportFileStream, exportSpaceData,
  type ReimportValidationIssue
} from '../api/data'
import UploadProgress from '../components/UploadProgress.vue'

type ProgressStage = {
  title: string
  desc: string
}

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
const relationsVerificationStatus = ref<'idle' | 'verifying' | 'completed' | 'failed'>('idle')
const relationsContentViewMode = ref<'current' | 'initial'>('current')
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
const isEditingUnderstanding = ref(false)
const verificationStatus = ref<'idle' | 'verifying' | 'completed' | 'failed'>('idle')
const contentViewMode = ref<'current' | 'initial'>('current')
let verifyPollTimer: ReturnType<typeof setInterval> | null = null

marked.setOptions({ gfm: true, breaks: true })

const understandingProgressStages: ProgressStage[] = [
  { title: '数据理解', desc: '读取字段、样本和基础结构' },
  { title: 'AI洞察', desc: '生成表角色、指标口径和业务语义' },
  { title: '异常复核', desc: '核对可能有争议的字段与结论' },
  { title: '深度理解', desc: '整合复核结果，完善最终理解' },
  { title: '完成', desc: '理解内容已更新' }
]

const relationsProgressStages: ProgressStage[] = [
  { title: '数据汇总', desc: '汇总各表理解和样本信息' },
  { title: '关联识别', desc: '识别字段关系与跨表业务链路' },
  { title: '异常复核', desc: '核对可疑关联和口径冲突' },
  { title: '关联洞察', desc: '整合复核结果，形成关联总结' },
  { title: '完成', desc: '关联总结已更新' }
]

const activeUnderstandingStageIndex = computed(() => {
  if (verificationStatus.value === 'verifying') return 2
  if (loadingUnderstanding.value || regeneratingUnderstanding.value) return 1
  return 0
})

const activeUnderstandingStage = computed(() => {
  return understandingProgressStages[activeUnderstandingStageIndex.value]
})

const showUnderstandingStageProgress = computed(() => {
  return loadingUnderstanding.value || regeneratingUnderstanding.value || verificationStatus.value === 'verifying'
})

const activeRelationsStageIndex = computed(() => {
  if (relationsVerificationStatus.value === 'verifying') return 2
  if (loadingRelations.value || regeneratingRelations.value) return 1
  return 0
})

const activeRelationsStage = computed(() => {
  return relationsProgressStages[activeRelationsStageIndex.value]
})

const showRelationsStageProgress = computed(() => {
  return loadingRelations.value || regeneratingRelations.value || relationsVerificationStatus.value === 'verifying'
})

const showCompareToggle = computed(() => {
  const initial = understandingContentInitial.value
  const current = understandingContent.value
  return Boolean(initial && current && initial !== current)
})

const displayUnderstandingContent = computed(() => {
  if (contentViewMode.value === 'initial' && understandingContentInitial.value) {
    return understandingContentInitial.value
  }
  return understandingContent.value
})

const renderedUnderstanding = computed(() => {
  if (!displayUnderstandingContent.value) return ''
  return marked.parse(displayUnderstandingContent.value) as string
})

const showRelationsCompareToggle = computed(() => {
  const initial = relationsContentInitial.value
  const current = relationsContent.value
  return Boolean(initial && current && initial !== current)
})

const displayRelationsContent = computed(() => {
  if (relationsContentViewMode.value === 'initial' && relationsContentInitial.value) {
    return relationsContentInitial.value
  }
  return relationsContent.value
})

const renderedRelationsContent = computed(() => {
  if (!displayRelationsContent.value) return ''
  return marked.parse(displayRelationsContent.value) as string
})

// 上传
const showUpload = ref(false)
const selectedFile = ref<File | null>(null)
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

// ========== 计算 ==========

function formatCell(val: any, type: string) {
  if (val === null || val === undefined) return '-'
  if (type === 'number' && typeof val === 'number') {
    return val.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  }
  return String(val)
}

// ========== 方法 ==========

async function loadTables() {
  if (!currentSpaceId.value) return
  loadingTables.value = true
  try {
    const res = await getTables(currentSpaceId.value)
    tables.value = res.data.data || []
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
  contentViewMode.value = 'current'
  stopVerifyPoll()
  isEditingUnderstanding.value = false
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
    regeneratingRelations.value = true
  } else {
    loadingRelations.value = true
  }
  stopRelationsVerifyPoll()
  try {
    const res = await getRelations(currentSpaceId.value, regenerate)
    relationsContent.value = res.data.content || ''
    relationsContentInitial.value = res.data.content_initial || ''
    relationsUpdatedAt.value = res.data.updated_at || ''
    relationsVerificationStatus.value = res.data.verification_status || 'idle'
    relationsContentViewMode.value = 'current'

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
  isEditingUnderstanding.value = false

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

function doSearch() {
  currentPage.value = 1
  loadTableRows()
}

function formatUnderstandingTime(iso: string) {
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
  loadingUnderstanding.value = true
  stopVerifyPoll()
  try {
    const res = await getTableUnderstanding(activeTable.value, regenerate)
    understandingContent.value = res.data.content || ''
    understandingContentInitial.value = res.data.content_initial || ''
    understandingUpdatedAt.value = res.data.updated_at || ''
    understandingDraft.value = understandingContent.value
    verificationStatus.value = res.data.verification_status || 'idle'
    contentViewMode.value = 'current'

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

function startEditUnderstanding() {
  understandingDraft.value = understandingContent.value
  isEditingUnderstanding.value = true
}

function cancelEditUnderstanding() {
  understandingDraft.value = understandingContent.value
  isEditingUnderstanding.value = false
}

async function saveUnderstanding() {
  if (!activeTable.value) return
  savingUnderstanding.value = true
  try {
    const res = await saveTableUnderstanding(activeTable.value, understandingDraft.value)
    understandingContent.value = res.data.content
    understandingUpdatedAt.value = res.data.updated_at || ''
    verificationStatus.value = res.data.verification_status || 'idle'
    stopVerifyPoll()
    isEditingUnderstanding.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    savingUnderstanding.value = false
  }
}

async function regenerateUnderstanding() {
  if (!activeTable.value) return
  regeneratingUnderstanding.value = true
  isEditingUnderstanding.value = false
  try {
    await loadUnderstanding(true)
    ElMessage.success('已重新生成')
  } catch (e) {
    ElMessage.error(extractErrorMessage(e))
  } finally {
    regeneratingUnderstanding.value = false
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

function closeReimportMode() {
  showReimportMode.value = false
  pendingReimportFile.value = null
  reimportWarnings.value = []
}

async function confirmReimport() {
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
      reimportMode.value,
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
      await getTableUnderstanding(tableName, true)
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

function handleFileChange(file: any) {
  selectedFile.value = file.raw
}

async function handleUpload() {
  if (!selectedFile.value) return
  uploading.value = true
  showUpload.value = false
  showProgress.value = true
  progressIsReimport.value = false
  uploadFilename.value = selectedFile.value.name

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
    await uploadFileStream(
      selectedFile.value,
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
    await loadTables()
    selectedFile.value = null
  } catch (e: any) {
    ElMessage.error('上传失败：' + (e.message || '未知错误'))
  } finally {
    uploading.value = false
    setTimeout(() => {
      showProgress.value = false
    }, 1500)
  }
}

// ========== 监听空间切换 ==========
watch(currentSpaceId, () => {
  localStorage.setItem('xlsx-bi-active-space', currentSpaceId.value)
  activeTable.value = ''
  relationsMode.value = false
  relationsContent.value = ''
  relationsContentInitial.value = ''
  relationsUpdatedAt.value = ''
  relationsContentViewMode.value = 'current'
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
})
</script>

<style scoped>
/* Claude Code 风格：暖色底、陶土橙强调、细边框少阴影 */
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

/* ========== Left Sidebar ========== */
.table-sidebar {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--dv-surface);
  border: 1px solid var(--dv-border);
  border-radius: 12px;
  box-shadow: none;
  padding: 12px;
  min-height: 0;
  overflow: hidden;
}

.table-list-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin-bottom: var(--spacing-sm);
}

.relations-summary-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 36px;
  margin-top: auto;
  flex-shrink: 0;
  border: 1px solid rgba(217, 119, 87, 0.35);
  border-radius: 10px;
  background: var(--dv-accent-soft);
  color: var(--dv-accent);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
}

.relations-summary-btn:hover {
  background: rgba(217, 119, 87, 0.18);
  border-color: rgba(217, 119, 87, 0.5);
}

.relations-summary-btn.active {
  background: var(--dv-accent);
  border-color: var(--dv-accent);
  color: #fff;
}

.relations-summary-icon {
  font-size: 16px;
}

.sidebar-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--dv-faint);
  margin-bottom: 8px;
  padding: 0 4px;
}

.sidebar-loading,
.sidebar-empty {
  padding: var(--spacing-base) var(--spacing-xs);
}

.sidebar-empty-desc {
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
  margin-top: var(--spacing-xs);
}

.table-list {
  display: flex;
  flex-direction: column;
}

.table-list-item {
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s var(--ease-out);
}

.table-list-item:hover {
  background: var(--dv-hover);
}

.table-list-item.active {
  background: var(--dv-accent-soft);
}

.table-item-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--dv-text);
  line-height: 1.4;
}

.table-list-item.active .table-item-name {
  color: var(--dv-accent);
}

.table-item-meta {
  font-size: 11px;
  color: var(--dv-faint);
  margin-top: 2px;
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

.content-main-inner--table .table-card {
  flex: 1;
  min-height: 0;
  height: auto;
}

.content-main-inner--table .table-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.content-main-inner--table .table-footer {
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

.content-empty--inline {
  min-height: 320px;
  padding: 48px 20px;
}

.content-empty--inline .empty-desc {
  margin-bottom: var(--spacing-base);
}

.empty-icon-lg {
  font-size: 56px;
  color: var(--color-text-tertiary);
  opacity: 0.2;
  margin-bottom: var(--spacing-base);
}

/* ========== Table Card ========== */
.table-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: transparent;
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.table-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--dv-border);
  flex-shrink: 0;
}

.table-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--dv-text);
  letter-spacing: -0.01em;
}

.table-card-count {
  font-size: 12px;
  color: var(--dv-faint);
}

.table-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.table-footer {
  padding: 10px 16px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--dv-border);
  flex-shrink: 0;
}

.cell-num {
  font-family: var(--font-mono);
  font-size: var(--text-base);
}

/* 表格样式 */
:deep(.el-table) {
  --el-table-border-color: transparent;
  --el-table-row-hover-bg-color: var(--dv-accent-soft);
  --el-table-header-bg-color: var(--dv-surface-muted);
  font-size: 13px;
}

:deep(.el-table__header th) {
  background: var(--dv-surface-muted) !important;
  color: var(--dv-muted);
  font-weight: 500;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--dv-border) !important;
  padding: 10px 14px;
}

:deep(.el-table__body td) {
  padding: 10px 14px;
  color: var(--dv-text);
  border-bottom: 1px solid #F0EDE8;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: #FAF8F5;
}

:deep(.el-table__body tr:last-child td) {
  border-bottom: none;
}

/* ========== Understanding Section ========== */
.understand-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-base);
}

.understand-card {
  position: relative;
  padding: 20px 20px 24px;
}

.stage-progress {
  padding: 12px 14px;
  margin-bottom: 18px;
  background: var(--dv-surface-muted);
  border: 1px solid var(--dv-border);
  border-radius: 10px;
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
  color: var(--dv-text);
  white-space: nowrap;
}

.stage-progress-desc {
  min-width: 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--dv-muted);
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
  background: #E7E1D8;
  border-radius: 999px;
}

.stage-progress-item.complete:not(:last-child)::after {
  background: var(--dv-accent);
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
  background: #E7E1D8;
  border: 2px solid var(--dv-surface-muted);
}

.stage-progress-item.complete .stage-progress-dot,
.stage-progress-item.active .stage-progress-dot {
  background: var(--dv-accent);
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
  color: var(--dv-faint);
}

.stage-progress-item.complete .stage-progress-label,
.stage-progress-item.active .stage-progress-label {
  color: var(--dv-text);
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

.understand-editor {
  width: 100%;
  min-height: 480px;
  padding: var(--spacing-base);
  font-size: 14px;
  line-height: 1.6;
  font-family: var(--font-mono);
  color: var(--color-text-primary);
  border: 1px solid var(--color-separator);
  border-radius: var(--radius-base);
  resize: vertical;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.understand-editor:focus {
  border-color: var(--dv-accent);
  box-shadow: 0 0 0 3px var(--dv-accent-soft);
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

.insight-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.insight-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-base);
  background: rgba(0, 122, 255, 0.06);
  color: var(--color-primary);
  font-size: var(--text-base);
  border-radius: var(--radius-full);
}

/* ========== Card ========== */
.card {
  background: transparent;
  border-radius: 0;
  padding: 20px;
  box-shadow: none;
}

.card-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-md);
}

/* ========== Tags ========== */
.tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 var(--spacing-sm);
  font-size: var(--text-xs);
  font-weight: 500;
  border-radius: var(--radius-base);
}

.tag--blue   { background: rgba(0, 122, 255, 0.1); color: var(--color-primary); }
.tag--green  { background: rgba(52, 199, 89, 0.12); color: var(--color-success); }
.tag--orange { background: rgba(255, 149, 0, 0.12); color: var(--color-warning); }
.tag--gray   { background: var(--color-bg); color: var(--color-text-secondary); }

/* ========== Skeleton ========== */
.skeleton-line {
  height: var(--spacing-md);
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-sm);
  animation: shimmer 1.5s infinite;
}

.skeleton-title { width: 60%; height: 16px; }
.skeleton-short { width: 40%; }

.skeleton-card {
  padding: var(--spacing-lg);
}

@keyframes shimmer {
  0% { opacity: 0.5; }
  50% { opacity: 1; }
  100% { opacity: 0.5; }
}

/* ========== Modal ========== */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.modal-panel {
  background: var(--color-white);
  border-radius: var(--radius-xl);
  padding: var(--spacing-xl);
  width: 480px;
  max-width: 90vw;
  box-shadow: var(--shadow-modal);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-lg);
}

.modal-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--color-text-primary);
}

.modal-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: all 0.15s;
}

.modal-close:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--color-text-primary);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-xl);
}

.upload-modal .upload-area :deep(.el-upload-dragger) {
  background: var(--color-bg);
  border: 2px dashed rgba(0, 0, 0, 0.08);
  border-radius: var(--radius-lg);
  padding: 32px 20px;
}

.upload-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.upload-icon-wrap {
  margin-bottom: var(--spacing-base);
}

.upload-icon {
  font-size: 40px;
  color: var(--color-text-tertiary);
  opacity: 0.5;
}

.upload-text {
  color: var(--color-text-secondary);
  font-size: var(--text-base);
}

.upload-link {
  color: var(--dv-accent);
  cursor: pointer;
}

.upload-tip {
  color: var(--color-text-tertiary);
  font-size: var(--text-sm);
  margin-top: var(--spacing-sm);
}

.selected-file {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-base);
  padding: var(--spacing-sm) var(--spacing-base);
  background: rgba(52, 199, 89, 0.06);
  border-radius: var(--radius-base);
  color: var(--color-success);
  font-size: var(--text-base);
}

/* ========== Buttons ========== */
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

.content-main-inner :deep(.el-pagination) {
  --el-pagination-hover-color: var(--dv-accent);
  --el-pagination-button-color: var(--dv-muted);
}

/* ========== 更新 / 校验弹窗 ========== */
.reimport-file-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--dv-muted);
  margin-bottom: 16px;
}

.reimport-mode-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reimport-mode-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--dv-border);
  border-radius: 12px;
  cursor: pointer;
  transition: border-color 0.15s var(--ease-out), background 0.15s var(--ease-out);
}

.reimport-mode-item:hover {
  border-color: #D4CEC4;
  background: var(--dv-surface-muted);
}

.reimport-mode-item.active {
  border-color: var(--dv-accent);
  background: var(--dv-accent-soft);
}

.reimport-mode-item input {
  margin-top: 4px;
  accent-color: var(--dv-accent);
}

.mode-title {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--dv-text);
  margin-bottom: 4px;
}

.mode-desc {
  display: block;
  font-size: 13px;
  color: var(--dv-muted);
  line-height: 1.5;
}

.reimport-warnings {
  margin-top: 12px;
  padding: 10px 12px;
  background: rgba(255, 149, 0, 0.08);
  border-radius: 8px;
  font-size: 12px;
  color: #B45309;
  line-height: 1.5;
}

.reimport-warnings p + p {
  margin-top: 4px;
}

.validation-intro {
  font-size: 14px;
  color: var(--dv-muted);
  line-height: 1.6;
  margin-bottom: 16px;
}

.validation-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 320px;
  overflow-y: auto;
}

.validation-list li {
  padding: 12px 0;
  border-bottom: 1px solid var(--dv-border);
}

.validation-list li:last-child {
  border-bottom: none;
}

.validation-msg {
  font-size: 14px;
  font-weight: 500;
  color: var(--dv-text);
  margin-bottom: 6px;
}

.validation-detail,
.validation-cols {
  font-size: 13px;
  color: var(--dv-muted);
  line-height: 1.5;
  margin-top: 4px;
}

.validation-cols--actual {
  color: #B45309;
}

.understanding-prompt-lead {
  font-size: 14px;
  color: var(--dv-muted);
  margin: 8px 0 16px;
  line-height: 1.6;
}

.understanding-prompt-tips {
  padding: 14px 16px;
  background: var(--dv-surface-muted);
  border-radius: 12px;
  border: 1px solid var(--dv-border);
  margin-bottom: 8px;
}

.understanding-prompt-tips p {
  font-size: 13px;
  color: var(--dv-muted);
  line-height: 1.6;
  margin: 0 0 10px;
}

.understanding-prompt-tips p:last-child {
  margin-bottom: 0;
}

.understanding-prompt-tips strong {
  color: var(--dv-text);
  font-weight: 600;
}

/* ========== Parsing State ========== */
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
</style>
