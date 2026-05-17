<template>
  <div class="login-page">
    <div class="bg-decoration" aria-hidden="true">
      <div class="bg-glow bg-glow--1"></div>
      <div class="bg-glow bg-glow--2"></div>
      <div class="bg-grid"></div>
    </div>

    <div class="login-card">
      <div class="login-header">
        <BrandLogo variant="full" :show-text="false" block />
        <p class="login-subtitle">{{ BRAND_TAGLINE }}</p>
        <p class="login-desc">上传 Excel · AI 理解 · 洞察看板</p>
      </div>

      <div class="login-form">
        <div class="form-group">
          <label class="form-label">账号</label>
          <input
            v-model="form.username"
            type="text"
            class="login-input"
            placeholder="请输入账号"
            autocomplete="username"
            @keyup.enter="focusPassword"
          />
        </div>

        <div class="form-group">
          <label class="form-label">密码</label>
          <input
            ref="passwordRef"
            v-model="form.password"
            type="password"
            class="login-input"
            placeholder="请输入密码"
            autocomplete="current-password"
            @keyup.enter="handleLogin"
          />
        </div>

        <button
          type="button"
          class="btn-login"
          :disabled="loading"
          @click="handleLogin"
        >
          <span v-if="!loading">登 录</span>
          <span v-else class="loading-text">登录中…</span>
        </button>
      </div>

      <transition name="error-fade">
        <div v-if="errorMsg" class="login-error">
          {{ errorMsg }}
        </div>
      </transition>
    </div>

    <div class="footer-credits">
      <p class="credits-title">制作人</p>
      <p class="credits-team">神州数码AI加速器 第二期第四组</p>
      <p class="credits-members">
        <span>李潇然</span>
        <span class="credits-dot"></span>
        <span>李安琪</span>
        <span class="credits-dot"></span>
        <span>宋玉坡</span>
        <span class="credits-dot"></span>
        <span>王加凯</span>
        <span class="credits-dot"></span>
        <span>张智家</span>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../api'
import { useUserStore } from '../stores/user'
import { BRAND_TAGLINE } from '../constants/brand'
import BrandLogo from '../components/brand/BrandLogo.vue'

const router = useRouter()
const userStore = useUserStore()

const passwordRef = ref<HTMLInputElement>()
const loading = ref(false)
const errorMsg = ref('')

const form = reactive({
  username: '',
  password: ''
})

function focusPassword() {
  passwordRef.value?.focus()
}

const handleLogin = async () => {
  errorMsg.value = ''

  if (!form.username || !form.password) {
    errorMsg.value = '请输入账号和密码'
    return
  }

  loading.value = true
  try {
    const res = await login(form.username, form.password)
    const data = res.data
    userStore.setToken(data.token)
    userStore.setUser(data.username, data.display_name, data.is_admin || false)
    router.push('/')
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || '登录失败，请检查网络连接'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  --accent: #D97757;
  --accent-hover: #C6613F;
  --accent-soft: rgba(217, 119, 87, 0.14);
  --page-bg: #F5F2EB;
  --surface: #FFFFFF;
  --border: #E5E0D8;
  --text: #1C1917;
  --muted: #736C64;
  --faint: #A39E96;

  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--page-bg);
  overflow: hidden;
  font-family: var(--font-family);
}

.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
}

.bg-glow--1 {
  width: 480px;
  height: 480px;
  background: rgba(217, 119, 87, 0.14);
  top: -160px;
  right: -120px;
}

.bg-glow--2 {
  width: 360px;
  height: 360px;
  background: rgba(193, 95, 60, 0.08);
  bottom: -80px;
  left: -80px;
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(28, 25, 23, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(28, 25, 23, 0.03) 1px, transparent 1px);
  background-size: 48px 48px;
  opacity: 0.6;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  max-width: calc(100vw - 32px);
  padding: 40px 32px 32px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.04),
    0 12px 40px rgba(28, 25, 23, 0.06);
  animation: scaleIn 0.35s var(--ease-out);
}

@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.97) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.login-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-bottom: 32px;
}

.login-header :deep(.brand-logo--block) {
  align-items: center;
  margin-bottom: 8px;
}

.login-subtitle {
  font-size: 14px;
  font-weight: 500;
  color: var(--muted);
  margin: 0 0 4px;
  letter-spacing: 0.04em;
}

.login-desc {
  font-size: 12px;
  color: var(--faint);
  margin: 0;
}

.login-form {
  width: 100%;
}

.form-group {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--muted);
}

.login-input {
  width: 100%;
  height: 44px;
  padding: 0 14px;
  background: #FAF8F5;
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  border: 1px solid var(--border);
  border-radius: 10px;
  outline: none;
  transition: border-color 0.15s var(--ease-out), box-shadow 0.15s var(--ease-out);
  box-sizing: border-box;
}

.login-input::placeholder {
  color: var(--faint);
}

.login-input:focus {
  background: var(--surface);
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.btn-login {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 44px;
  margin-top: 8px;
  padding: 0 20px;
  background: var(--accent);
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  font-family: inherit;
  letter-spacing: 0.08em;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s var(--ease-out), transform 0.15s var(--ease-out);
}

.btn-login:hover {
  background: var(--accent-hover);
}

.btn-login:active {
  transform: scale(0.98);
}

.btn-login:disabled {
  background: var(--faint);
  cursor: not-allowed;
  transform: none;
}

.login-error {
  margin-top: 12px;
  padding: 10px 12px;
  background: rgba(255, 59, 48, 0.08);
  color: #FF3B30;
  font-size: 13px;
  border-radius: 8px;
  text-align: center;
}

.error-fade-enter-active,
.error-fade-leave-active {
  transition: opacity 0.2s var(--ease-out), transform 0.2s var(--ease-out);
}

.error-fade-enter-from,
.error-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.footer-credits {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 10;
  text-align: right;
  opacity: 0.4;
  transition: opacity 0.25s var(--ease-out);
}

.footer-credits:hover {
  opacity: 0.75;
}

.credits-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  margin: 0 0 4px;
  letter-spacing: 0.06em;
}

.credits-team {
  font-size: 12px;
  font-weight: 500;
  color: var(--text);
  margin: 0 0 4px;
}

.credits-members {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 11px;
  color: var(--faint);
  margin: 0;
}

.credits-dot {
  display: inline-block;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--faint);
  opacity: 0.5;
}
</style>
