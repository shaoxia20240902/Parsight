<template>
  <div v-if="open" class="modal-backdrop" @click.self="$emit('close')">
    <section class="builder-modal">
      <header class="builder-modal__header">
        <h3>确认业务知识</h3>
        <button type="button" class="modal-close" @click="$emit('close')">×</button>
      </header>
      <div class="builder-modal__body">
        <label class="builder-field">
          <span>业务表达</span>
          <input :value="term" @input="updateTerm" />
        </label>
        <label class="builder-field">
          <span>实际含义</span>
          <input :value="canonical" @input="updateCanonical" />
        </label>
        <label class="builder-field">
          <span>保存到哪个 Sheet</span>
          <select :value="tableName" @change="updateTableName">
            <option v-for="opt in sheetOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </label>
      </div>
      <footer class="builder-modal__footer">
        <button type="button" class="builder-action" @click="$emit('close')">取消</button>
        <button type="button" class="builder-action builder-action--primary" @click="$emit('confirm')">
          确认添加
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  open: boolean
  term: string
  canonical: string
  tableName: string
  sheetOptions: Array<{ label: string; value: string }>
}>()

const emit = defineEmits<{
  close: []
  confirm: []
  'update:term': [value: string]
  'update:canonical': [value: string]
  'update:tableName': [value: string]
}>()

function updateTerm(event: Event) {
  emit('update:term', (event.target as HTMLInputElement).value)
}

function updateCanonical(event: Event) {
  emit('update:canonical', (event.target as HTMLInputElement).value)
}

function updateTableName(event: Event) {
  emit('update:tableName', (event.target as HTMLSelectElement).value)
}
</script>

<style scoped>
.modal-backdrop {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 22px;
  background: rgba(43, 40, 37, 0.24);
}

.builder-modal {
  width: min(460px, 100%);
  max-height: min(680px, 92%);
  display: flex;
  flex-direction: column;
  background: var(--chat-surface);
  border: 1px solid var(--chat-border);
  border-radius: 10px;
  box-shadow: 0 18px 44px rgba(43, 40, 37, 0.16);
  overflow: hidden;
}

.builder-modal__header,
.builder-modal__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--chat-border);
}

.builder-modal__footer {
  justify-content: flex-end;
  border-top: 1px solid var(--chat-border);
  border-bottom: 0;
}

.builder-modal__header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
}

.builder-modal__body {
  padding: 14px 16px;
  overflow-y: auto;
}

.modal-close {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--chat-muted);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}

.builder-field {
  display: grid;
  gap: 5px;
  margin: 8px 0;
  font-size: 12px;
  color: var(--chat-muted);
}

.builder-field select,
.builder-field input {
  height: 34px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: #fff;
  color: var(--chat-text);
  padding: 0 9px;
  font: inherit;
}

.builder-action {
  min-height: 30px;
  padding: 0 11px;
  border: 1px solid var(--chat-chip-border);
  border-radius: 8px;
  background: var(--chat-chip-bg);
  color: var(--chat-accent);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.builder-action--primary {
  background: var(--chat-accent);
  color: #fff;
  border-color: var(--chat-accent);
}
</style>
