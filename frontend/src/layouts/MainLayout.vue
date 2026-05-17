<template>
  <div class="layout">
    <header class="header">
      <div class="header-left">
        <button type="button" class="brand" @click="$router.push('/data')">
          <BrandLogo variant="compact" :show-text="true" />
        </button>
      </div>

      <nav class="header-center" aria-label="主导航">
        <div class="module-tabs">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            class="module-tab"
            :class="{ active: currentModule === tab.key }"
            @click="goModule(tab)"
          >
            <el-icon class="tab-icon"><component :is="tab.icon" /></el-icon>
            <span class="tab-label">{{ tab.label }}</span>
          </button>
        </div>
      </nav>

      <div class="header-right">
        <SpaceSwitcher @space-changed="onSpaceChanged" />
        <el-dropdown
          trigger="click"
          placement="bottom-end"
          :show-arrow="false"
          popper-class="user-popper"
          @command="handleUserCommand"
        >
          <div class="user-avatar-wrap">
            <el-avatar :size="32" class="user-avatar">{{ avatarText }}</el-avatar>
          </div>
          <template #dropdown>
            <el-dropdown-menu class="user-dropdown">
              <el-dropdown-item command="logout" class="user-menu-item user-menu-item--danger">
                <span class="user-menu-row">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="body">
      <aside class="aside" v-if="!hideSidebar">
        <component :is="currentNav" />
      </aside>

      <main class="main" :class="{ 'main--flush': route.path.startsWith('/data') || route.path.startsWith('/admin') || route.path.startsWith('/bi') || route.path.startsWith('/chat') }">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <GlobalLoading :visible="showGlobalLoading" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  Document, TrendCharts, ChatDotRound, SwitchButton, Setting
} from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import SpaceSwitcher from '../components/SpaceSwitcher.vue'
import GlobalLoading from '../components/GlobalLoading.vue'
import BrandLogo from '../components/brand/BrandLogo.vue'
import DataNav from './navs/DataNav.vue'
import BINav from './navs/BINav.vue'
import AdminNav from './navs/AdminNav.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const showGlobalLoading = ref(false)
const previousSpaceId = ref<string | null>(null)

const tabs = computed(() => {
  const base = [
    { key: 'data', label: '数据', icon: Document, path: '/data' },
    { key: 'bi', label: '洞察', icon: TrendCharts, path: '/bi' },
    { key: 'chat', label: '对话', icon: ChatDotRound, path: '/chat' }
  ]
  if (userStore.isAdmin) {
    base.push({ key: 'admin', label: '管理', icon: Setting, path: '/admin' })
  }
  return base
})

const currentModule = computed(() => {
  const p = route.path
  if (p.startsWith('/bi')) return 'bi'
  if (p.startsWith('/chat')) return 'chat'
  if (p.startsWith('/admin')) return 'admin'
  return 'data'
})

const hideSidebar = computed(() => {
  return (
    route.path.startsWith('/chat') ||
    route.path.startsWith('/data') ||
    route.path.startsWith('/bi')
  )
})

const navMap: Record<string, any> = {
  data: DataNav,
  bi: BINav,
  chat: null,
  admin: AdminNav
}

const currentNav = computed(() => navMap[currentModule.value] || DataNav)

const avatarText = computed(() => {
  const n = userStore.displayName || userStore.username || '?'
  return Array.from(n)[0] || '?'
})

function goModule(tab: { key: string; path: string }) {
  if (currentModule.value !== tab.key) {
    router.push(tab.path)
  }
}

function onSpaceChanged(space: any) {
  const newId = space?.id || ''

  // 首次加载时仅记录，不触发 reload
  if (previousSpaceId.value === null) {
    previousSpaceId.value = newId
    window.dispatchEvent(new CustomEvent('space-changed', { detail: space }))
    return
  }

  // 用户主动切换空间 -> 显示 loading 并刷新页面
  if (newId && newId !== previousSpaceId.value) {
    showGlobalLoading.value = true
    requestAnimationFrame(() => {
      setTimeout(() => {
        window.location.reload()
      }, 2000)
    })
  }
}

function handleUserCommand(cmd: string) {
  if (cmd === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      userStore.logout()
      router.push('/login')
    }).catch(() => {})
  }
}
</script>

<style scoped>
.layout {
  --header-height: 52px;
  --aside-width: 220px;
  --accent: #D97757;
  --accent-hover: #C6613F;
  --accent-soft: rgba(217, 119, 87, 0.12);
  --surface: #FAF8F5;
  --surface-elevated: #FFFFFF;
  --border: #E5E0D8;
  --text: #1C1917;
  --muted: #736C64;
  --faint: #A39E96;
  --page-bg: #F5F2EB;

  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--page-bg);
}

/* ========== Header ========== */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  min-width: 140px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  margin: 0;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s var(--ease-out);
}

.brand:hover {
  background: rgba(28, 25, 23, 0.05);
}

/* Module Tabs */
.header-center {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
}

.module-tabs {
  display: flex;
  align-items: center;
  background: var(--page-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 3px;
}

.module-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: none;
  background: transparent;
  border-radius: 8px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
  white-space: nowrap;
}

.module-tab:hover:not(.active) {
  color: var(--text);
}

.module-tab.active {
  background: var(--surface-elevated);
  color: var(--accent);
  box-shadow: 0 1px 2px rgba(28, 25, 23, 0.06);
}

.tab-icon {
  font-size: 15px;
}

.header-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  min-width: 140px;
}

.user-avatar-wrap {
  cursor: pointer;
  padding: 2px;
  border-radius: 50%;
  border: 1px solid transparent;
  transition: border-color 0.15s var(--ease-out), background 0.15s var(--ease-out);
}

.user-avatar-wrap:hover {
  background: rgba(28, 25, 23, 0.05);
  border-color: var(--border);
}

.user-avatar {
  background: var(--accent-soft) !important;
  color: var(--accent) !important;
  font-weight: 600;
  font-size: 13px;
}

/* ========== Body ========== */
.body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ========== Sidebar - 毛玻璃 ========== */
.aside {
  width: var(--aside-width);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(16px) saturate(160%);
  -webkit-backdrop-filter: blur(16px) saturate(160%);
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  overflow-y: auto;
  flex-shrink: 0;
}

/* ========== Main ========== */
.main {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-2xl);
}

.main--flush {
  padding: 10px 12px;
  overflow: hidden;
  background: var(--page-bg);
}

/* ========== Page Transition ========== */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s var(--ease-out), transform 0.2s var(--ease-out);
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.user-menu-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
</style>

<style>
.user-popper.el-popper {
  border: 1px solid #E5E0D8 !important;
  border-radius: 12px !important;
  padding: 6px !important;
  background: #FFFFFF !important;
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.04),
    0 8px 28px rgba(28, 25, 23, 0.1) !important;
}

.user-popper .el-dropdown-menu {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

.user-popper .el-dropdown-menu__item {
  margin: 0;
  padding: 8px 12px !important;
  border-radius: 8px;
  font-size: 13px;
}

.user-popper .el-dropdown-menu__item:hover,
.user-popper .user-menu-item--danger:hover {
  background: rgba(255, 59, 48, 0.08) !important;
  color: #C94A42 !important;
}
</style>
