<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="visible" class="modal-overlay">
        <div class="modal-panel understanding-prompt-modal">
          <h3 class="modal-title">数据已更新</h3>
          <p class="understanding-prompt-lead">是否重新生成各表的「理解内容」？</p>
          <div class="understanding-prompt-tips">
            <p><strong>通常无需重新生成</strong>：若本次仅为行数增减、数值刷新，字段含义与表结构未变，现有理解仍可继续使用。</p>
            <p><strong>建议重新生成</strong>：若调整了表头含义、业务口径变化较大，或覆盖后数据语义已与原理解明显不符。</p>
          </div>
          <div class="modal-footer">
            <button class="btn-secondary" :disabled="regenerating" @click="$emit('skip')">
              暂不生成
            </button>
            <button class="btn-primary" :disabled="regenerating" @click="$emit('confirm')">
              {{ regenerating ? '生成中…' : '重新生成理解' }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  regenerating: boolean
}>()

defineEmits<{
  skip: []
  confirm: []
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

.modal-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-sm);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-xl);
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
.btn-secondary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

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
