<template>
  <TransitionGroup name="msg" tag="div" class="msg-list">
    <div
      v-for="(msg, i) in messages"
      :key="i"
      :class="['message', msg.role]"
    >
      <div class="message-avatar">{{ msg.role === 'user' ? '我' : '析' }}</div>
      <div class="message-bubble">
        <div class="message-content" :class="{ 'message-content--pending': msg.pending }">
          <span v-if="msg.pending" class="thinking-dot" aria-hidden="true"></span>
          {{ msg.content }}
        </div>
        <div v-if="msg.blocks?.length" class="builder-blocks">
          <template v-for="(block, bi) in msg.blocks" :key="bi">
            <div v-if="block.type === 'intent_confirmation'" class="agent-card agent-card--intent" :class="{ 'agent-card--running': block.auto_execute && !block.resolved }">
              <div class="agent-card__eyebrow">{{ block.requires_confirmation ? '需要你确认' : '已识别意图，正在执行' }}</div>
              <div class="agent-card__title">{{ block.mode_label }} · 置信度 {{ Math.round((block.confidence || 0) * 100) }}%</div>
              <p class="agent-card__desc">{{ block.requires_confirmation ? block.confirm_question : block.execution_note }}</p>
              <div v-if="block.evidence?.length" class="agent-evidence">
                <span v-for="item in block.evidence" :key="item">{{ item }}</span>
              </div>
              <div v-if="block.warnings?.length" class="agent-warnings">
                <span v-for="item in block.warnings" :key="item">{{ item }}</span>
              </div>
              <div v-if="block.plan_steps?.length" class="agent-steps">
                <span v-for="(step, si) in block.plan_steps" :key="step">
                  <b>{{ Number(si) + 1 }}</b>{{ step }}
                </span>
              </div>
              <div v-if="block.requires_confirmation" class="builder-actions">
                <button
                  v-for="action in block.actions"
                  :key="action.type"
                  type="button"
                  class="builder-action"
                  :class="{ 'builder-action--primary': action.variant === 'primary' }"
                  :disabled="sending || block.resolved"
                  @click="$emit('intent-action', action, block)"
                >
                  {{ action.label }}
                </button>
              </div>
              <div v-if="block.resolved" class="agent-card__status">{{ block.resolved_label || '已处理' }}</div>
            </div>

            <div v-else-if="block.type === 'agent_steps'" class="agent-card">
              <div class="agent-card__eyebrow">智能体执行轨迹</div>
              <div class="agent-steps agent-steps--vertical">
                <span v-for="step in block.items" :key="step.name">
                  <b>✓</b>{{ step.name }}<small>{{ step.detail }}</small>
                </span>
              </div>
            </div>

            <div v-else-if="block.type === 'markdown'" class="builder-markdown" v-html="renderMarkdown(block.content)" />

            <div v-else-if="block.type === 'data_table'" class="builder-card builder-card--preview">
              <div class="builder-card__title">{{ block.title || '查询结果' }}</div>
              <div v-if="block.rows?.length" class="preview-table-wrap">
                <table class="preview-table">
                  <thead>
                    <tr>
                      <th v-for="col in block.columns" :key="col">{{ col }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, ri) in block.rows.slice(0, 8)" :key="ri">
                      <td v-for="col in block.columns" :key="col">{{ row[col] }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="builder-card__meta">暂无可展示数据。</div>
            </div>

            <div v-else-if="block.type === 'chart_summary'" class="builder-card">
              <div class="builder-card__title">{{ block.title }}</div>
              <div class="builder-card__meta">
                {{ block.category_name || block.category_id || '未分类' }} · {{ block.chart_type || 'chart' }}
              </div>
              <div v-if="block.reason" class="builder-card__reason">{{ block.reason }}</div>
            </div>

            <div v-else-if="block.type === 'chart_preview'" class="builder-card builder-card--preview">
              <div class="builder-card__title">图表预览</div>
              <div v-if="block.preview?.rows?.length" class="preview-table-wrap">
                <table class="preview-table">
                  <thead>
                    <tr>
                      <th v-for="col in block.preview.columns" :key="col">{{ col }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, ri) in block.preview.rows.slice(0, 5)" :key="ri">
                      <td v-for="col in block.preview.columns" :key="col">{{ row[col] }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="builder-card__meta">可点击“去查看”在 BI 页面查看完整图表。</div>
            </div>

            <div v-else-if="block.type === 'questionnaire'" class="builder-card">
              <div class="builder-card__title">必填信息</div>
              <label v-for="q in block.questions" :key="q.field" class="builder-field">
                <span>{{ q.label }}</span>
                <select v-model="formValues[q.field]">
                  <option value="">请选择</option>
                  <option v-for="opt in q.options" :key="optionValue(opt)" :value="optionValue(opt)">
                    {{ optionLabel(opt) }}
                  </option>
                </select>
              </label>
              <button type="button" class="builder-action builder-action--primary" @click="submitQuestionnaire(block)">
                {{ block.submit_label || '确认并继续' }}
              </button>
            </div>

            <details v-else-if="block.type === 'advanced_panel'" class="builder-card builder-details">
              <summary>高级设置</summary>
              <div class="builder-card__meta">可选项，默认可跳过。</div>
            </details>

            <div v-else-if="block.type === 'analysis_directions'" class="builder-card">
              <div class="builder-card__title">推荐分析方向</div>
              <button
                v-for="item in block.items"
                :key="item.title"
                type="button"
                class="builder-action"
                @click="$emit('send-message', item.prompt, { type: 'user_message', payload: { force_create: true } })"
              >
                {{ item.title }}
              </button>
            </div>

            <div v-else-if="block.type === 'knowledge_cards'" class="builder-card">
              <div v-for="card in block.items" :key="card.title" class="knowledge-card">
                <div class="builder-card__title">{{ card.title }}</div>
                <div class="builder-card__meta">这类业务知识会通过弹窗确认后保存到对应 Sheet 的表理解中。</div>
                <div class="builder-actions">
                  <button type="button" class="builder-action builder-action--primary" @click="$emit('open-knowledge', card)">
                    打开确认弹窗
                  </button>
                  <button type="button" class="builder-action" @click="$emit('action', { type: card.card_type === 'user_preference' ? 'confirm_preference' : 'confirm_knowledge', payload: { accepted: false, card } })">
                    不保存
                  </button>
                </div>
              </div>
            </div>

            <div v-else-if="block.type === 'sales_chart_plan'" class="builder-card">
              <div class="builder-card__title">将创建这些销售报表</div>
              <div class="sales-plan-list">
                <div v-for="item in block.items" :key="item.client_chart_id" class="sales-plan-item">
                  <strong>{{ item.title }}</strong>
                  <span>{{ item.business_type }} · {{ item.metric }} · 按 {{ item.dimension }} 看</span>
                  <small>{{ item.chart_type_label }} · {{ item.category_name }}</small>
                </div>
              </div>
              <button type="button" class="builder-action" @click="$emit('open-chart-editor', block)">
                调整报表方案
              </button>
            </div>

            <div v-else-if="block.type === 'companion_suggestions'" class="builder-card">
              <div class="builder-card__title">建议顺手补充</div>
              <div class="builder-card__meta">这些报表已经按当前语境准备好，点击即可创建。</div>
              <div class="builder-actions builder-actions--stack">
                <button
                  v-for="item in block.items"
                  :key="item.title"
                  type="button"
                  class="builder-action"
                  @click="$emit('action', { type: 'create_companion_chart', label: item.title, payload: { chart: item.chart } })"
                >
                  {{ item.title }}
                </button>
              </div>
            </div>

            <div v-else-if="block.type === 'completion_summary'" class="builder-card">
              <div class="builder-card__title">本轮上下文已保存</div>
              <div class="builder-card__meta">{{ block.summary?.business_context }}</div>
            </div>

            <div v-else-if="block.type === 'actions'" class="builder-actions">
              <button
                v-for="action in block.items"
                :key="action.label"
                type="button"
                class="builder-action"
                :class="{ 'builder-action--primary': action.type === 'confirm_generate' }"
                @click="$emit('action', action)"
              >
                {{ action.label }}
              </button>
            </div>
          </template>
        </div>
      </div>
    </div>
    <!-- 统一思考状态（非 builder 模式专属） -->
    <div v-if="sending && !messages.some(m => m.pending)" key="thinking" class="message assistant">
      <div class="message-avatar">析</div>
      <div class="message-bubble">
        <div class="message-content message-content--thinking">
          <span class="thinking-pulse" aria-hidden="true" />
          <span class="thinking-text">{{ thinkingTexts[thinkingIndex] }}</span>
        </div>
      </div>
    </div>
  </TransitionGroup>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { renderMarkdown } from '../../utils/chat'

type ChatMessage = { role: string; content: string; blocks?: any[]; pending?: boolean }

defineProps<{
  messages: ChatMessage[]
  sending: boolean
  thinkingIndex: number
  thinkingTexts: string[]
}>()

const emit = defineEmits<{
  'intent-action': [action: any, block: any]
  action: [action: any]
  'send-message': [text: string, event: any]
  'open-knowledge': [card: any]
  'open-chart-editor': [block: any]
  'submit-questionnaire': [block: any, values: Record<string, any>]
}>()

const formValues = ref<Record<string, any>>({})

function optionLabel(opt: any) {
  return typeof opt === 'string' ? opt : opt.label
}

function optionValue(opt: any) {
  return typeof opt === 'string' ? opt : opt.value
}

function submitQuestionnaire(block: any) {
  const values: Record<string, any> = {}
  for (const q of block.questions || []) {
    if (formValues.value[q.field]) values[q.field] = formValues.value[q.field]
  }
  emit('submit-questionnaire', block, values)
}
</script>

<style scoped>
.msg-list {
  display: flex;
  flex-direction: column;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 85%;
}

.message.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  background: rgba(217, 119, 87, 0.1);
  color: var(--chat-accent);
}

.message.assistant .message-avatar {
  background: rgba(28, 25, 23, 0.06);
  color: var(--chat-muted);
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.65;
}

.message.user .message-bubble {
  background: var(--chat-accent);
  color: #fff;
}

.message.assistant .message-bubble {
  background: var(--chat-surface);
  border: 1px solid var(--chat-border);
}

.builder-blocks {
  display: grid;
  gap: 10px;
  margin-top: 10px;
}

.builder-card {
  padding: 12px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: rgba(255, 252, 250, 0.78);
}

.agent-card {
  display: grid;
  gap: 10px;
  padding: 13px;
  border: 1px solid rgba(65, 93, 138, 0.18);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(246, 249, 252, 0.94));
}

.agent-card--intent {
  border-color: rgba(198, 97, 63, 0.24);
  background: #fffdfb;
}

.agent-card--running {
  border-color: rgba(67, 116, 90, 0.22);
  background: linear-gradient(180deg, #fff, #f7fbf8);
}

.agent-card__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--chat-accent);
}

.agent-card__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--chat-text);
}

.agent-card__desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--chat-muted);
}

.agent-card__status {
  width: fit-content;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(67, 116, 90, 0.1);
  color: #43745a;
  font-size: 11px;
  font-weight: 700;
}

.agent-evidence,
.agent-warnings {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.agent-evidence span,
.agent-warnings span {
  padding: 5px 8px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 1.3;
  background: #fff;
  border: 1px solid var(--chat-border);
  color: var(--chat-muted);
}

.agent-warnings span {
  color: #8A4B16;
  border-color: rgba(202, 138, 4, 0.28);
  background: #FFF9EB;
}

.agent-steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
  gap: 7px;
}

.agent-steps span {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--chat-border);
  font-size: 12px;
  color: var(--chat-text);
}

.agent-steps b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: var(--chat-accent);
  color: #fff;
  font-size: 10px;
  flex-shrink: 0;
}

.agent-steps--vertical {
  grid-template-columns: 1fr;
}

.agent-steps--vertical span {
  align-items: flex-start;
}

.agent-steps small {
  color: var(--chat-muted);
  font-size: 11px;
  line-height: 1.35;
}

.builder-card__title {
  font-size: 13px;
  font-weight: 650;
  color: var(--chat-text);
  margin-bottom: 4px;
}

.builder-card__meta,
.builder-card__reason {
  font-size: 12px;
  color: var(--chat-muted);
  line-height: 1.45;
}

.builder-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.builder-actions--stack {
  flex-direction: column;
  align-items: flex-start;
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

.builder-action:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.builder-field {
  display: grid;
  gap: 5px;
  margin: 8px 0;
  font-size: 12px;
  color: var(--chat-muted);
}

.builder-field select {
  height: 32px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: #fff;
  color: var(--chat-text);
  padding: 0 8px;
  font: inherit;
}

.message-content--pending {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--chat-muted);
}

.thinking-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--chat-accent);
  box-shadow: 12px 0 0 rgba(198, 97, 63, 0.35), 24px 0 0 rgba(198, 97, 63, 0.2);
  animation: thinkingPulse 1s ease-in-out infinite;
}

@keyframes thinkingPulse {
  0%, 100% { opacity: 0.35; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-1px); }
}

.message-content--thinking {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--chat-muted);
  min-height: 22px;
}

.thinking-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--chat-accent);
  box-shadow: 0 0 0 0 rgba(198, 97, 63, 0.45);
  animation: pulse-ring 1.8s ease-out infinite;
  flex-shrink: 0;
}

@keyframes pulse-ring {
  0% { box-shadow: 0 0 0 0 rgba(198, 97, 63, 0.45); }
  70% { box-shadow: 0 0 0 10px rgba(198, 97, 63, 0); }
  100% { box-shadow: 0 0 0 0 rgba(198, 97, 63, 0); }
}

.thinking-text {
  font-size: 13px;
  color: #8B7355;
  font-weight: 400;
  letter-spacing: 0.01em;
}

.sales-plan-list {
  display: grid;
  gap: 8px;
  margin: 8px 0 10px;
}

.sales-plan-item {
  display: grid;
  gap: 2px;
  padding: 9px 10px;
  border: 1px solid var(--chat-border);
  border-radius: 8px;
  background: #fff;
}

.sales-plan-item strong {
  font-size: 13px;
  color: var(--chat-text);
}

.sales-plan-item span,
.sales-plan-item small {
  font-size: 12px;
  color: var(--chat-muted);
}

.preview-table-wrap,
.builder-markdown {
  overflow-x: auto;
}

:deep(.builder-md-table),
.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

:deep(.builder-md-table th),
:deep(.builder-md-table td),
.preview-table th,
.preview-table td {
  border: 1px solid var(--chat-border);
  padding: 6px 8px;
  text-align: left;
  white-space: nowrap;
}

:deep(.builder-md-table th),
.preview-table th {
  background: rgba(198, 97, 63, 0.08);
  color: var(--chat-text);
}

.builder-details summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}

.knowledge-card + .knowledge-card {
  margin-top: 10px;
}
</style>
