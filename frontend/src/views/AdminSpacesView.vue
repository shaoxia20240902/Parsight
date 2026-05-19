<template>
  <div class="admin-view">
    <!-- 空间列表 -->
    <section class="panel panel--table">
      <div class="panel-header">
        <h2 class="panel-title">空间管理</h2>
        <button type="button" class="btn-primary" @click="openCreate">新增空间</button>
      </div>

      <div v-if="loading" class="table-loading">加载中…</div>
      <div v-else-if="spaces.length === 0" class="table-empty">暂无空间</div>
      <div v-else class="table-scroll">
        <table class="config-table">
          <thead>
            <tr>
              <th>空间名称</th>
              <th>代码</th>
              <th>描述</th>
              <th>拥有者</th>
              <th class="col-right">创建时间</th>
              <th class="col-center col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in spaces" :key="s.id">
              <td>
                <span class="name-cell">{{ s.name }}</span>
              </td>
              <td class="col-mono">{{ s.code }}</td>
              <td>{{ s.description || '—' }}</td>
              <td>{{ s.owner_name }}</td>
              <td class="col-right col-mono">{{ formatTime(s.created_at) }}</td>
              <td class="col-center col-actions">
                <div class="action-group">
                  <button type="button" class="btn-action" @click="openEdit(s)">编辑</button>
                  <button
                    type="button"
                    class="btn-action btn-action--danger"
                    :disabled="isCurrentSpace(s.id)"
                    :title="isCurrentSpace(s.id) ? '当前正在使用的空间不可删除' : ''"
                    @click="handleDelete(s)"
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
          <h3>{{ dialog.isEdit ? '编辑空间' : '新增空间' }}</h3>
          <button type="button" class="modal-close" @click="closeDialog">×</button>
        </header>
        <div class="builder-modal__body">
          <div class="form-stack">
            <label class="form-field">
              <span class="field-label">空间名称</span>
              <input v-model="dialog.form.name" class="field-input" placeholder="如：默认空间" />
            </label>
            <label v-if="!dialog.isEdit" class="form-field">
              <span class="field-label">所属用户</span>
              <select v-model="dialog.form.owner_id" class="field-input">
                <option value="">请选择用户</option>
                <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }}</option>
              </select>
            </label>
            <label class="form-field">
              <span class="field-label">描述</span>
              <input v-model="dialog.form.description" class="field-input" placeholder="可选" />
            </label>
          </div>
        </div>
        <footer class="builder-modal__footer">
          <button type="button" class="builder-action" @click="closeDialog">取消</button>
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
  listSpaces,
  createSpace,
  updateSpace,
  deleteSpace,
  listUsers,
  type AdminSpace,
  type AdminUser,
} from '../api/admin'

const spaces = ref<AdminSpace[]>([])
const users = ref<AdminUser[]>([])
const loading = ref(false)
const saving = ref(false)

const dialog = reactive({
  open: false,
  isEdit: false,
  editingId: '',
  form: {
    name: '',
    owner_id: '',
    description: '',
  },
})

function resetForm() {
  dialog.form = {
    name: '',
    owner_id: '',
    description: '',
  }
}

async function loadSpaces() {
  loading.value = true
  try {
    const res = await listSpaces()
    spaces.value = res.data.data || []
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载空间列表失败')
  } finally {
    loading.value = false
  }
}

async function loadUsers() {
  try {
    const res = await listUsers()
    users.value = res.data.data || []
  } catch (e: any) {
    console.error('加载用户列表失败', e)
  }
}

function openCreate() {
  resetForm()
  dialog.isEdit = false
  dialog.editingId = ''
  dialog.open = true
}

function openEdit(s: AdminSpace) {
  dialog.form = {
    name: s.name,
    owner_id: s.owner_id,
    description: s.description,
  }
  dialog.isEdit = true
  dialog.editingId = s.id
  dialog.open = true
}

function closeDialog() {
  dialog.open = false
}

async function handleSave() {
  if (!dialog.form.name.trim()) {
    ElMessage.warning('请输入空间名称')
    return
  }
  if (!dialog.isEdit && !dialog.form.owner_id) {
    ElMessage.warning('请选择所属用户')
    return
  }
  saving.value = true
  try {
    if (dialog.isEdit) {
      await updateSpace(dialog.editingId, {
        name: dialog.form.name.trim(),
        description: dialog.form.description.trim(),
      })
      ElMessage.success('空间已更新')
    } else {
      await createSpace({
        name: dialog.form.name.trim(),
        owner_id: dialog.form.owner_id,
        description: dialog.form.description.trim(),
      })
      ElMessage.success('空间已创建')
    }
    closeDialog()
    await loadSpaces()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(s: AdminSpace) {
  try {
    await ElMessageBox.confirm(
      `确定删除空间「${s.name}」吗？将同时删除该空间下的所有文件、数据表和聊天记录。`,
      '删除确认',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deleteSpace(s.id)
    ElMessage.success('空间已删除')
    await loadSpaces()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

function isCurrentSpace(spaceId: string): boolean {
  return spaceId === (localStorage.getItem('xlsx-bi-active-space') || '')
}

function formatTime(t: string) {
  if (!t) return '—'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  return d.toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  loadSpaces()
  loadUsers()
})
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

.col-center {
  text-align: center;
}

.col-right {
  text-align: right;
}

.col-mono {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--muted);
}

.col-actions {
  width: 140px;
}

.name-cell {
  font-weight: 500;
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
  max-height: min(680px, 92%);
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
