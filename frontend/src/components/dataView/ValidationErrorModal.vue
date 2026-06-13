<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
        <div class="modal-panel validation-modal">
          <div class="modal-header">
            <h3 class="modal-title">无法更新：表结构不一致</h3>
            <button class="modal-close" @click="$emit('close')">
              <el-icon><Close /></el-icon>
            </button>
          </div>
          <p class="validation-intro">
            请修正 Excel 后重新选择文件。各 Sheet 须与当前已导入表<strong>字段名及顺序完全一致</strong>。
          </p>
          <ul class="validation-list">
            <li v-for="(issue, i) in issues" :key="i">
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
            <button class="btn-primary" @click="$emit('close')">我知道了</button>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { Close } from '@element-plus/icons-vue'
import type { ReimportValidationIssue } from '../../api/data'

defineProps<{
  visible: boolean
  issues: ReimportValidationIssue[]
}>()

defineEmits<{
  close: []
}>()
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
