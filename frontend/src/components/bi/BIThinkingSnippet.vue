<template>
  <div class="bi-think-snippet" :class="{ 'bi-think-snippet--compact': compact }">
    <div v-if="showHeader" class="bi-think-snippet__head">
      <span class="bi-think-snippet__pulse" />
      <span class="bi-think-snippet__label">{{ label }}</span>
    </div>
    <div class="bi-think-snippet__scroll" role="region" :aria-label="label">
      <p class="bi-think-snippet__text">
        <span>{{ displayText }}</span>
        <span v-if="typing" class="bi-think-snippet__cursor" />
      </p>
    </div>
    <p v-if="hint" class="bi-think-snippet__hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    text?: string
    label?: string
    hint?: string
    typing?: boolean
    compact?: boolean
    showHeader?: boolean
  }>(),
  {
    text: '',
    label: '分析中',
    hint: '',
    typing: false,
    compact: false,
    showHeader: true,
  }
)

const displayText = computed(() => props.text || '…')
</script>

<style scoped>
.bi-think-snippet {
  text-align: left;
  padding: 12px 14px;
  border: 1px solid #E8E1D8;
  border-radius: 8px;
  background: #FDFCFA;
}

.bi-think-snippet--compact {
  padding: 10px 12px;
}

.bi-think-snippet__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.bi-think-snippet__pulse {
  width: 8px;
  height: 8px;
  border-radius: 4px;
  background: #C6613F;
  box-shadow: 0 0 0 0 rgba(198, 97, 63, 0.45);
  animation: bi-think-pulse 1.8s ease-out infinite;
}

@keyframes bi-think-pulse {
  0% { box-shadow: 0 0 0 0 rgba(198, 97, 63, 0.45); }
  70% { box-shadow: 0 0 0 10px rgba(198, 97, 63, 0); }
  100% { box-shadow: 0 0 0 0 rgba(198, 97, 63, 0); }
}

.bi-think-snippet__label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #8B7355;
  text-transform: uppercase;
}

.bi-think-snippet__scroll {
  max-height: calc(1.55em * 3);
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
}

.bi-think-snippet__scroll::-webkit-scrollbar {
  width: 4px;
}

.bi-think-snippet__scroll::-webkit-scrollbar-thumb {
  background: #D4CEC6;
  border-radius: 2px;
}

.bi-think-snippet__text {
  margin: 0;
  font-size: 14px;
  line-height: 1.55;
  color: #3D3835;
  white-space: pre-wrap;
  word-break: break-word;
}

.bi-think-snippet__cursor {
  display: inline-block;
  width: 2px;
  height: 1.1em;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: #C6613F;
  animation: bi-think-cursor 0.9s step-end infinite;
}

@keyframes bi-think-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.bi-think-snippet__hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #A39E96;
  line-height: 1.45;
}
</style>
