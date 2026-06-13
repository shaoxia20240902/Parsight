<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
        <div class="modal-panel reimport-modal">
          <div class="modal-header">
            <h3 class="modal-title">选择更新方式</h3>
            <button class="modal-close" @click="$emit('close')">
              <el-icon><Close /></el-icon>
            </button>
          </div>
          <p class="reimport-file-name">
            <el-icon><Document /></el-icon>
            {{ file?.name }}
          </p>
          <div class="reimport-mode-list">
            <label class="reimport-mode-item" :class="{ active: innerMode === 'overwrite' }">
              <input v-model="innerMode" type="radio" value="overwrite" />
              <div class="mode-body">
                <span class="mode-title">全量覆盖</span>
                <span class="mode-desc">清空各表现有数据，用新文件内容完整替换</span>
              </div>
            </label>
            <label class="reimport-mode-item" :class="{ active: innerMode === 'insert' }">
              <input v-model="innerMode" type="radio" value="insert" />
              <div class="mode-body">
                <span class="mode-title">全量插入</span>
                <span class="mode-desc">保留现有数据，将新文件全部行追加到表尾</span>
              </div>
            </label>
          </div>
          <div v-if="warnings.length" class="reimport-warnings">
            <p v-for="(w, i) in warnings" :key="i">{{ w.message }}</p>
          </div>
          <div class="modal-footer">
            <button class="btn-secondary" @click="$emit('close')">取消</button>
            <button class="btn-primary" :disabled="reimporting" @click="confirm">
              {{ reimporting ? '更新中…' : '开始更新' }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Document, Close } from '@element-plus/icons-vue'
import type { ReimportValidationIssue } from '../../api/data'

const props = defineProps<{
  visible: boolean
  file: File | null
  warnings: ReimportValidationIssue[]
  mode: 'overwrite' | 'insert'
  reimporting: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [mode: 'overwrite' | 'insert']
}>()

const innerMode = ref<'overwrite' | 'insert'>('overwrite')

watch(() => props.visible, (visible) => {
  if (visible) innerMode.value = props.mode
})

watch(() => props.mode, (mode) => {
  innerMode.value = mode
})

function confirm() {
  emit('confirm', innerMode.value)
}
</script>

<style scoped>
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
