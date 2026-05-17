<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="visible" class="upload-progress-overlay">
        <div class="upload-progress-panel">
          <div class="progress-header">
            <h3 class="progress-title">{{ mode === 'reimport' ? '正在更新数据' : '正在导入数据' }}</h3>
            <p class="progress-filename">{{ filename }}</p>
          </div>

          <div class="progress-steps">
            <div
              v-for="step in steps"
              :key="step.key"
              class="progress-step"
              :class="{
                'step--active': step.status === 'processing',
                'step--completed': step.status === 'completed',
                'step--error': step.status === 'error'
              }"
            >
              <div class="step-indicator">
                <el-icon v-if="step.status === 'completed'" class="step-icon"><Check /></el-icon>
                <el-icon v-else-if="step.status === 'error'" class="step-icon"><Close /></el-icon>
                <div v-else-if="step.status === 'processing'" class="step-spinner"></div>
                <div v-else class="step-dot"></div>
              </div>
              <div class="step-content">
                <div class="step-label">{{ step.label }}</div>
                <div v-if="step.message" class="step-message">{{ step.message }}</div>
              </div>
            </div>
          </div>

          <div class="progress-bar-track">
            <div class="progress-bar-fill" :style="{ width: progressPct + '%' }"></div>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Check, Close } from '@element-plus/icons-vue'

const props = withDefaults(
  defineProps<{
    visible: boolean
    filename: string
    currentStep: string
    stepStatus: Record<string, string>
    stepMessages: Record<string, string>
    progress: number
    mode?: 'upload' | 'reimport'
  }>(),
  { mode: 'upload' }
)

interface StepDef {
  key: string
  label: string
  status: string
  message: string
}

const steps = computed<StepDef[]>(() => {
  const defs =
    props.mode === 'reimport'
      ? [
          { key: 'saving', label: '保存文件' },
          { key: 'parsing', label: '解析并校验' },
          { key: 'importing', label: '写入数据' },
          { key: 'done', label: '完成' }
        ]
      : [
          { key: 'saving', label: '保存文件' },
          { key: 'parsing', label: '解析文件结构' },
          { key: 'creating_tables', label: '创建数据表' },
          { key: 'inserting_data', label: '导入数据' },
          { key: 'analyzing', label: '生成数据洞察与BI配置' },
          { key: 'done', label: '完成' }
        ]

  return defs.map(d => ({
    key: d.key,
    label: d.label,
    status: props.stepStatus[d.key] || 'pending',
    message: props.stepMessages[d.key] || ''
  }))
})

const progressPct = computed(() => props.progress)
</script>

<style scoped>
/* ========== Overlay ========== */
.upload-progress-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.upload-progress-panel {
  background: var(--color-white);
  border-radius: var(--radius-xl);
  padding: var(--spacing-2xl);
  width: 420px;
  max-width: 90vw;
  box-shadow: var(--shadow-modal);
}

/* ========== Header ========== */
.progress-header {
  margin-bottom: var(--spacing-xl);
}

.progress-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.progress-filename {
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
}

/* ========== Steps ========== */
.progress-steps {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: var(--spacing-lg);
}

.progress-step {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  padding: var(--spacing-sm) 0;
}

.step-indicator {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-separator);
}

.step-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-separator);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

.step-icon {
  font-size: 16px;
}

.step--active .step-icon,
.step--active { color: var(--color-primary); }
.step--completed .step-icon { color: var(--color-success); }
.step--error .step-icon { color: var(--color-danger); }

.step-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-secondary);
  transition: color 0.2s;
}

.step--active .step-label { color: var(--color-text-primary); }
.step--completed .step-label { color: var(--color-text-primary); }
.step--error .step-label { color: var(--color-danger); }

.step-message {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
}

.step-content {
  min-width: 0;
}

/* ========== Progress Bar ========== */
.progress-bar-track {
  height: 4px;
  background: var(--color-bg);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 2px;
  transition: width 0.4s var(--ease-out);
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

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
