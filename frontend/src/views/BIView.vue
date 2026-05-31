<template>
  <div class="bi-view">
    <BIDashboard v-if="fileId" :file-id="fileId" :data-ready="dataReady" />

    <div v-else-if="showDemoBoard" class="bi-demo">
      <div class="bi-demo__notice">
        <div class="bi-demo__callout" role="status" aria-live="polite">
          <div class="bi-demo__callout-icon" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path
                d="M10 1.75a8.25 8.25 0 1 0 0 16.5 8.25 8.25 0 0 0 0-16.5Zm0 3.5a.875.875 0 1 1 0 1.75.875.875 0 0 1 0-1.75ZM9.125 9.5h1.75v5.25H9.125V9.5Z"
                fill="currentColor"
              />
            </svg>
          </div>
          <div class="bi-demo__callout-body">
            <p class="bi-demo__callout-title">
              <span class="bi-demo__badge">演示</span>
              当前展示演示数据
            </p>
            <p class="bi-demo__callout-desc">
              数据文件未上传、表理解未完成或关联总结未就绪时，BI 模块默认展示企业销售样例看板。
            </p>
          </div>
        </div>
        <button type="button" class="bi-demo__btn" @click="goToData">上传数据</button>
      </div>
      <BIInsightsBoard file-id="demo-sales-bi" :config="demoConfig" demo-mode />
    </div>

    <div v-else-if="loading" class="bi-shell">
      <div class="bi-shell__card">
        <div class="bi-shell__spinner" aria-label="加载中" />
      </div>
    </div>

    <div v-else-if="checked" class="bi-shell">
      <div class="bi-shell__card" :class="{ 'bi-shell__card--error': errorMessage }">
        <p class="bi-shell__eyebrow">BI 智能看板</p>
        <h2 class="bi-shell__title">{{ shellTitle }}</h2>
        <p class="bi-shell__desc">{{ shellDesc }}</p>
        <button type="button" class="bi-shell__btn" @click="goToData">前往数据页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BIDashboard from '../components/BIDashboard.vue'
import BIInsightsBoard from '../components/bi/BIInsightsBoard.vue'
import { getBIStatus } from '../api'
import { listFiles } from '../api/space'
import { createDemoBIConfig } from '../mocks/demoBIConfig'

const router = useRouter()
const SPACE_KEY = 'xlsx-bi-active-space'

const fileId = ref('')
const loading = ref(false)
const errorMessage = ref('')
const checked = ref(false)
const blocked = ref(false)
const showDemoBoard = ref(false)
const dataReady = ref(false)
const demoConfig = createDemoBIConfig()

function goToData() {
  router.push('/data')
}

async function loadBI() {
  loading.value = true
  checked.value = false
  errorMessage.value = ''
  fileId.value = ''
  blocked.value = false
  showDemoBoard.value = false
  dataReady.value = false

  try {
    const spaceId = localStorage.getItem(SPACE_KEY) || ''
    const filesRes = await listFiles(spaceId)
    const files = filesRes.data.data || []
    const latest =
      files.find((f: any) => f.status === 'analyzed' || f.status === 'understanding_ready') ||
      files[0]
    if (!latest) {
      showDemoBoard.value = true
      return
    }

    const isUnderstandingReady = latest.status === 'analyzed' || latest.status === 'understanding_ready'
    if (!isUnderstandingReady) {
      showDemoBoard.value = true
      return
    }

    try {
      const statusRes = await getBIStatus(latest.id)
      if (statusRes.data.data?.status === 'blocked') {
        showDemoBoard.value = true
        return
      }
      dataReady.value = true
      fileId.value = latest.id
    } catch {
      dataReady.value = true
      fileId.value = latest.id
    }
  } catch (e: any) {
    showDemoBoard.value = true
    errorMessage.value = e.response?.data?.detail || e.message || ''
  } finally {
    loading.value = false
    checked.value = true
  }
}

const shellTitle = computed(() => {
  if (errorMessage.value) return '加载失败'
  if (blocked.value) return '数据理解尚未完成'
  return '暂无数据'
})

const shellDesc = computed(() => {
  if (errorMessage.value) return errorMessage.value
  if (blocked.value) return '已检测到上传文件，请等待表理解完成后再进入 BI 构建。'
  return '在数据页面上传 XLSX 文件，完成分析后可手动生成 BI 看板。'
})

function onSpaceChanged() {
  loadBI()
}

onMounted(() => {
  loadBI()
  window.addEventListener('space-changed', onSpaceChanged)
})

onUnmounted(() => {
  window.removeEventListener('space-changed', onSpaceChanged)
})
</script>

<style scoped>
.bi-view {
  min-height: calc(100vh - var(--header-height, 52px) - 20px);
  background: #F4F1EA;
}

.bi-demo {
  min-height: calc(100vh - var(--header-height, 52px) - 20px);
  background: #F4F1EA;
}

.bi-demo__notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 20px 16px;
  background: #F4F1EA;
  border-bottom: 1px solid #E8E1D8;
}

.bi-demo__callout {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  background: linear-gradient(
    135deg,
    rgba(255, 149, 0, 0.14) 0%,
    rgba(198, 97, 63, 0.1) 100%
  );
  border: 1px solid rgba(198, 97, 63, 0.28);
  border-left: 4px solid #C6613F;
  border-radius: 12px;
  box-shadow:
    0 1px 3px rgba(58, 45, 34, 0.06),
    0 4px 12px rgba(198, 97, 63, 0.08);
}

.bi-demo__callout-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(198, 97, 63, 0.16);
  color: #9A4E32;
}

.bi-demo__callout-body {
  min-width: 0;
}

.bi-demo__callout-title {
  margin: 0 0 4px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  color: #7A3D28;
}

.bi-demo__badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 6px;
  background: rgba(198, 97, 63, 0.2);
  color: #9A4E32;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.bi-demo__callout-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: #5C534C;
}

.bi-demo__btn {
  flex-shrink: 0;
  height: 34px;
  padding: 0 14px;
  border: 1px solid rgba(198, 97, 63, 0.35);
  border-radius: 8px;
  background: rgba(198, 97, 63, 0.1);
  color: #C6613F;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
}

.bi-demo__btn:hover {
  background: rgba(198, 97, 63, 0.16);
}

.bi-shell {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - var(--header-height, 52px) - 20px);
  padding: 32px 20px;
  background: #F4F1EA;
}

.bi-shell__card {
  width: min(440px, calc(100vw - 40px));
  padding: 36px 34px;
  text-align: center;
  background: #FDFCFA;
  border: 1px solid #E8E1D8;
  border-radius: 8px;
  box-shadow: 0 16px 42px rgba(58, 45, 34, 0.08);
}

.bi-shell__eyebrow {
  margin: 0 0 12px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #C6613F;
}

.bi-shell__title {
  margin: 0 0 10px;
  font-size: 22px;
  font-weight: 600;
  color: #1C1917;
  letter-spacing: -0.02em;
}

.bi-shell__desc {
  margin: 0 0 28px;
  font-size: 14px;
  line-height: 1.6;
  color: #736C64;
}

.bi-shell__card--error .bi-shell__title {
  color: #B42318;
}

.bi-shell__spinner {
  width: 36px;
  height: 36px;
  margin: 0 auto;
  border: 2px solid #EDE8E1;
  border-top-color: #C6613F;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.bi-shell__btn {
  height: 40px;
  padding: 0 22px;
  border: 1px solid rgba(198, 97, 63, 0.35);
  border-radius: 8px;
  background: rgba(198, 97, 63, 0.1);
  color: #C6613F;
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
}

.bi-shell__btn:hover {
  background: rgba(198, 97, 63, 0.16);
}

.bi-shell__btn:active {
  transform: scale(0.98);
}

@media (max-width: 720px) {
  .bi-demo__notice {
    align-items: stretch;
    flex-direction: column;
    padding: 12px 14px 16px;
  }

  .bi-demo__btn {
    width: 100%;
  }
}
</style>
