<template>
  <div v-if="open" class="modal-backdrop" @click.self="$emit('close')">
    <section class="builder-modal builder-modal--wide">
      <header class="builder-modal__header">
        <h3>调整报表方案</h3>
        <button type="button" class="modal-close" @click="$emit('close')">×</button>
      </header>
      <div class="builder-modal__body chart-editor">
        <div v-for="chart in editableItems" :key="chart.client_chart_id" class="chart-edit-row">
          <label class="builder-field">
            <span>报表名称</span>
            <input v-model="chart.title" />
          </label>
          <label class="builder-field">
            <span>看什么指标</span>
            <select v-model="chart.metric.field">
              <option v-for="opt in fields.metrics" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </label>
          <label class="builder-field">
            <span>按什么看</span>
            <select v-model="chart.dimension">
              <option v-for="opt in fields.dimensions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </label>
          <label class="builder-field">
            <span>报表样式</span>
            <select v-model="chart.chart_type">
              <option value="kpi_group">核心指标卡</option>
              <option value="ranking">排名榜</option>
              <option value="bar">对比图</option>
              <option value="line">趋势图</option>
              <option value="pie">占比图</option>
              <option value="combo">目标达成图</option>
              <option value="table">汇总表</option>
              <option value="detail_table">明细清单</option>
            </select>
          </label>
          <label class="builder-field">
            <span>放到哪里</span>
            <select v-model="chart.target_category_id">
              <option v-for="opt in categories" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </label>
        </div>
      </div>
      <footer class="builder-modal__footer">
        <button type="button" class="builder-action" @click="$emit('close')">取消</button>
        <button type="button" class="builder-action builder-action--primary" @click="submit">
          保存方案
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  open: boolean
  items: any[]
  categories: Array<{ label: string; value: string }>
  fields: { metrics: any[]; dimensions: any[]; times: any[] }
}>()

const emit = defineEmits<{
  close: []
  submit: [items: any[]]
}>()

const editableItems = ref<any[]>([])

watch(() => props.open, (open) => {
  if (open) {
    editableItems.value = props.items.map((chart) => ({
      ...chart,
      metric: { ...(chart.metric || { field: '' }) },
      dimension: (chart.dimensions || [])[0] || ''
    }))
  }
})

function submit() {
  emit('submit', editableItems.value)
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

.builder-modal--wide {
  width: min(860px, 100%);
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

.chart-editor {
  display: grid;
  gap: 12px;
}

.chart-edit-row {
  display: grid;
  grid-template-columns: 1.3fr 1fr 1fr 1fr 1fr;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: rgba(255, 252, 250, 0.78);
}

.builder-field {
  display: grid;
  gap: 5px;
  margin: 0;
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
