<template>
  <div class="admin-view">
    <!-- 配置列表 -->
    <section class="panel panel--table">
      <div class="panel-header">
        <h2 class="panel-title">模型配置</h2>
        <button type="button" class="btn-primary" @click="openCreate">新增配置</button>
      </div>

      <div v-if="loading" class="table-loading">加载中…</div>
      <div v-else-if="configs.length === 0" class="table-empty">暂无配置</div>
      <div v-else class="table-scroll">
        <table class="config-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>API 地址</th>
              <th>主模型</th>
              <th>备用模型</th>
              <th class="col-center">状态</th>
              <th class="col-center col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in configs" :key="c.id" :class="{ 'row-active': c.is_active }">
              <td>
                <span class="name-cell">{{ c.name }}</span>
                <span v-if="c.is_active" class="active-tag">当前启用</span>
              </td>
              <td class="col-mono">{{ c.api_base }}</td>
              <td>{{ c.primary_model }}</td>
              <td>{{ c.alt_model || '—' }}</td>
              <td class="col-center">
                <span class="status-badge" :class="c.is_active ? 'status--active' : 'status--inactive'">
                  {{ c.is_active ? '启用' : '未启用' }}
                </span>
              </td>
              <td class="col-center col-actions">
                <div class="action-group">
                  <button
                    v-if="!c.is_active"
                    type="button"
                    class="btn-action btn-action--primary"
                    @click="handleActivate(c)"
                  >
                    启用
                  </button>
                  <button type="button" class="btn-action" @click="openEdit(c)">编辑</button>
                  <button
                    type="button"
                    class="btn-action btn-action--danger"
                    :disabled="c.is_active"
                    @click="handleDelete(c)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 新增/编辑弹窗 -->
    <div v-if="dialog.open" class="modal-backdrop" @click.self="closeDialog">
      <section class="builder-modal">
        <header class="builder-modal__header">
          <h3>{{ dialog.isEdit ? '编辑配置' : '新增配置' }}</h3>
          <button type="button" class="modal-close" @click="closeDialog">×</button>
        </header>
        <div class="builder-modal__body">
          <div class="form-stack">
            <label class="form-field">
              <span class="field-label">配置名称</span>
              <input v-model="dialog.form.name" class="field-input" placeholder="如：默认" />
            </label>
            <label class="form-field">
              <span class="field-label">API 地址</span>
              <input v-model="dialog.form.api_base" class="field-input" placeholder="https://api.example.com" />
            </label>
            <label class="form-field">
              <span class="field-label">API Key</span>
              <div class="input-with-toggle">
                <input
                  v-model="dialog.form.api_key"
                  class="field-input"
                  :type="showKey ? 'text' : 'password'"
                  placeholder="sk-..."
                />
                <button type="button" class="btn-toggle" @click="showKey = !showKey">
                  {{ showKey ? '隐藏' : '显示' }}
                </button>
              </div>
            </label>
            <label class="form-field">
              <span class="field-label">主模型</span>
              <input v-model="dialog.form.primary_model" class="field-input" placeholder="如：deepseek-v4-pro" />
            </label>
            <label class="form-field">
              <span class="field-label">备用模型</span>
              <input v-model="dialog.form.alt_model" class="field-input" placeholder="必填，可与主模型相同" />
            </label>
            <label class="form-field form-field--row">
              <input v-model="dialog.form.is_active" type="checkbox" />
              <span>创建后立即启用</span>
            </label>
          </div>
        </div>
        <footer class="builder-modal__footer">
          <button type="button" class="builder-action" @click="closeDialog">取消</button>
          <button
            type="button"
            class="builder-action builder-action--primary"
            :disabled="testing || saving"
            @click="handleTest"
          >
            {{ testing ? '测试中…' : '测试连接' }}
          </button>
          <button
            type="button"
            class="builder-action builder-action--primary"
            :disabled="saving"
            @click="handleSave"
          >
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </footer>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listLLMConfigs,
  createLLMConfig,
  updateLLMConfig,
  deleteLLMConfig,
  activateLLMConfig,
  testLLMConfig,
  type LLMConfigItem,
} from '../api/admin'

const configs = ref<LLMConfigItem[]>([])
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const showKey = ref(false)

const dialog = reactive({
  open: false,
  isEdit: false,
  editingId: '',
  form: {
    name: '',
    api_base: '',
    api_key: '',
    primary_model: '',
    alt_model: '',
    is_active: false,
  },
})

function resetForm() {
  dialog.form = {
    name: '',
    api_base: '',
    api_key: '',
    primary_model: '',
    alt_model: '',
    is_active: false,
  }
}

async function loadConfigs() {
  loading.value = true
  try {
    const res = await listLLMConfigs()
    configs.value = res.data.data || []
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载配置失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  dialog.isEdit = false
  dialog.editingId = ''
  dialog.open = true
}

function openEdit(c: LLMConfigItem) {
  dialog.form = {
    name: c.name,
    api_base: c.api_base,
    api_key: '',
    primary_model: c.primary_model,
    alt_model: c.alt_model,
    is_active: c.is_active,
  }
  dialog.isEdit = true
  dialog.editingId = c.id
  dialog.open = true
}

function closeDialog() {
  dialog.open = false
  showKey.value = false
}

async function handleTest() {
  if (!dialog.form.api_base || !dialog.form.api_key || !dialog.form.primary_model || !dialog.form.alt_model?.trim()) {
    ElMessage.warning('请填写 API 地址、Key、主模型和备用模型')
    return
  }
  testing.value = true
  try {
    const res = await testLLMConfig({
      api_base: dialog.form.api_base,
      api_key: dialog.form.api_key,
      primary_model: dialog.form.primary_model,
    })
    const data = res.data.data
    if (data.success) {
      ElMessage.success(`连接成功，模型：${data.model || dialog.form.primary_model}`)
    } else {
      ElMessage.error(`连接失败：${data.error || '未知错误'}`)
    }
  } catch (e: any) {
    ElMessage.error(e.message || '测试失败')
  } finally {
    testing.value = false
  }
}

async function handleSave() {
  if (!dialog.form.name || !dialog.form.api_base || !dialog.form.api_key || !dialog.form.primary_model || !dialog.form.alt_model?.trim()) {
    ElMessage.warning('请填写名称、API 地址、Key、主模型和备用模型')
    return
  }
  saving.value = true
  try {
    if (dialog.isEdit) {
      await updateLLMConfig(dialog.editingId, { ...dialog.form })
      ElMessage.success('配置已更新')
    } else {
      await createLLMConfig({ ...dialog.form })
      ElMessage.success('配置已创建')
    }
    closeDialog()
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleActivate(c: LLMConfigItem) {
  try {
    await activateLLMConfig(c.id)
    ElMessage.success(`已启用「${c.name}」`)
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '启用失败')
  }
}

async function handleDelete(c: LLMConfigItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除配置「${c.name}」吗？`,
      '删除确认',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deleteLLMConfig(c.id)
    ElMessage.success('配置已删除')
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(loadConfigs)
</script>

<style scoped>
.admin-view {
  --accent: #D97757;
  --accent-hover: #C6613F;
  --accent-soft: rgba(217, 119, 87, 0.12);
  --surface: #FFFFFF;
  --border: #E5E0D8;
  --text: #1C1917;
  --muted: #736C64;
  --faint: #A39E96;
  --hover: rgba(28, 25, 23, 0.05);
  --danger: #C94A42;
  --danger-soft: rgba(255, 59, 48, 0.1);

  width: 100%;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-sizing: border-box;
  color: var(--text);
}

.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
}

.panel--table {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 16px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  padding: 0 18px;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s var(--ease-out), transform 0.15s var(--ease-out);
  white-space: nowrap;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-primary:active:not(:disabled) {
  transform: scale(0.98);
}

.btn-primary:disabled {
  background: var(--faint);
  cursor: not-allowed;
}

.table-scroll {
  flex: 1;
  overflow: auto;
  border-radius: 10px;
  border: 1px solid var(--border);
}

.table-loading,
.table-empty {
  padding: 48px 16px;
  text-align: center;
  font-size: 14px;
  color: var(--faint);
}

.config-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.config-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #FAF8F5;
  color: var(--muted);
  font-weight: 500;
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 10px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.config-table tbody td {
  padding: 12px 14px;
  color: var(--text);
  border-bottom: 1px solid #F0EDE8;
  vertical-align: middle;
}

.config-table tbody tr:nth-child(even) {
  background: rgba(0, 0, 0, 0.012);
}

.config-table tbody tr:hover {
  background: var(--accent-soft);
}

.config-table tbody tr:last-child td {
  border-bottom: none;
}

.row-active {
  background: rgba(217, 119, 87, 0.04) !important;
}

.col-center {
  text-align: center;
}

.col-mono {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--muted);
}

.col-actions {
  width: 200px;
}

.name-cell {
  font-weight: 500;
}

.active-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 500;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 4px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.status--active {
  background: rgba(30, 160, 90, 0.12);
  color: #1EA05A;
}

.status--inactive {
  background: rgba(28, 25, 23, 0.06);
  color: var(--faint);
}

.action-group {
  display: flex;
  gap: 6px;
  justify-content: center;
}

.btn-action {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  color: var(--muted);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
}

.btn-action:hover:not(:disabled) {
  background: var(--hover);
  border-color: #D4CEC4;
}

.btn-action--primary {
  color: var(--accent);
  border-color: rgba(217, 119, 87, 0.35);
  background: rgba(217, 119, 87, 0.06);
}

.btn-action--primary:hover:not(:disabled) {
  background: var(--accent-soft);
  border-color: rgba(217, 119, 87, 0.5);
}

.btn-action--danger {
  color: var(--danger);
  border-color: rgba(201, 74, 66, 0.35);
}

.btn-action--danger:hover:not(:disabled) {
  background: var(--danger-soft);
  border-color: rgba(201, 74, 66, 0.5);
}

.btn-action:disabled {
  color: var(--faint);
  border-color: var(--border);
  cursor: not-allowed;
  opacity: 0.6;
}

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 22px;
  background: rgba(43, 40, 37, 0.24);
}

.builder-modal {
  width: min(480px, 100%);
  max-height: min(760px, 92%);
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: 0 18px 44px rgba(43, 40, 37, 0.16);
  overflow: hidden;
}

.builder-modal__header,
.builder-modal__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.builder-modal__footer {
  justify-content: flex-end;
  border-top: 1px solid var(--border);
  border-bottom: 0;
}

.builder-modal__header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.builder-modal__body {
  padding: 20px;
  overflow-y: auto;
}

.modal-close {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s ease;
}

.modal-close:hover {
  background: var(--hover);
}

/* Form */
.form-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field--row {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--muted);
}

.field-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--muted);
}

.field-input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
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

.field-input:focus {
  background: var(--surface);
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.input-with-toggle {
  display: flex;
  gap: 8px;
}

.input-with-toggle .field-input {
  flex: 1;
}

.btn-toggle {
  height: 40px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  color: var(--accent);
  background: transparent;
  border: 1px solid rgba(217, 119, 87, 0.35);
  border-radius: 10px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-toggle:hover {
  background: var(--accent-soft);
}

.builder-action {
  min-height: 36px;
  padding: 0 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.builder-action:hover:not(:disabled) {
  background: var(--hover);
}

.builder-action--primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.builder-action--primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.builder-action:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
