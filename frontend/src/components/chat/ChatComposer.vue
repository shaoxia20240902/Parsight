<template>
  <footer class="chat-composer">
    <div class="composer-box">
      <textarea
        :value="modelValue"
        class="composer-input"
        rows="1"
        :disabled="sending"
        :placeholder="placeholder"
        @keydown.enter.prevent="send"
        @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
      />
      <button
        type="button"
        class="composer-send"
        :disabled="sending || !modelValue.trim()"
        aria-label="发送"
        @click="send"
      >
        <el-icon><Promotion /></el-icon>
      </button>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { Promotion } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: string
  sending: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
}>()

function send() {
  if (!props.modelValue.trim()) return
  emit('send')
}
</script>

<style scoped>
.chat-composer {
  flex-shrink: 0;
  padding: 12px 24px 16px;
  border-top: 1px solid var(--chat-border);
  background: rgba(250, 248, 245, 0.92);
}

.composer-box {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  max-width: 720px;
  margin: 0 auto;
  padding: 10px 12px 10px 16px;
  background: var(--chat-surface);
  border: 1px solid var(--chat-border);
  border-radius: 16px;
  opacity: 0.75;
}

.composer-input {
  flex: 1;
  min-height: 24px;
  padding: 4px 0;
  font-size: 14px;
  font-family: inherit;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--chat-text);
}

.composer-input:disabled {
  cursor: not-allowed;
}

.composer-input::placeholder {
  color: var(--chat-faint);
}

.composer-send {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
  background: var(--chat-border);
  color: var(--chat-faint);
  cursor: not-allowed;
}

.composer-send:not(:disabled) {
  background: var(--chat-accent);
  color: #fff;
  cursor: pointer;
}
</style>
