<template>
  <div class="bi-view">
    <BIDashboard v-if="fileId" :file-id="fileId" />

    <div v-else-if="checked" class="bi-shell">
      <div class="bi-shell__card">
        <p class="bi-shell__eyebrow">BI 智能看板</p>
        <h2 class="bi-shell__title">暂无数据</h2>
        <p class="bi-shell__desc">在数据页面上传 XLSX 文件<br>完成分析后可手动生成 BI 看板</p>
        <button type="button" class="bi-shell__btn" @click="goToData">前往数据页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BIDashboard from '../components/BIDashboard.vue'
import { getBIStatus } from '../api'
import { listFiles } from '../api/space'

const router = useRouter()
const SPACE_KEY = 'xlsx-bi-active-space'

const fileId = ref('')
const loading = ref(false)
const errorMessage = ref('')
const checked = ref(false)

function goToData() {
  router.push('/data')
}

async function loadBI() {
  loading.value = true
  checked.value = false
  errorMessage.value = ''
  fileId.value = ''

  try {
    const spaceId = localStorage.getItem(SPACE_KEY) || ''
    const filesRes = await listFiles(spaceId)
    const files = filesRes.data.data || []
    const latest =
      files.find((f: any) => f.status === 'analyzed' || f.status === 'understanding_ready') ||
      files[0]
    if (!latest) return

    fileId.value = latest.id
    const statusRes = await getBIStatus(latest.id)
    if (statusRes.data.data?.status === 'blocked') {
      fileId.value = ''
    }
  } catch (e: any) {
    errorMessage.value = e.response?.data?.detail || e.message || '无法加载'
  } finally {
    loading.value = false
    checked.value = true
  }
}

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
}

.bi-shell {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - var(--header-height, 52px) - 20px);
  padding: 32px 20px;
  background:
    radial-gradient(ellipse 70% 45% at 50% 0%, rgba(198, 97, 63, 0.07), transparent),
    #F4F1EA;
}

.bi-shell__card {
  width: min(440px, calc(100vw - 40px));
  padding: 44px 36px;
  text-align: center;
  background: #FDFCFA;
  border: 1px solid rgba(28, 25, 23, 0.08);
  border-radius: 24px;
  box-shadow: 0 12px 40px rgba(28, 25, 23, 0.07);
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
  border-radius: 10px;
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
</style>
