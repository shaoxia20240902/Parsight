<template>
  <div class="admin-view">
    <!-- 添加用户 -->
    <section class="panel">
      <h2 class="panel-title">添加用户</h2>
      <div class="add-form">
        <div class="form-field">
          <label class="field-label">用户名</label>
          <input
            v-model="form.username"
            class="field-input"
            placeholder="登录账号"
            autocomplete="off"
          />
        </div>
        <div class="form-field">
          <label class="field-label">显示名称</label>
          <input
            v-model="form.display_name"
            class="field-input"
            placeholder="可选，默认同用户名"
            autocomplete="off"
          />
        </div>
        <div class="form-field">
          <label class="field-label">密码</label>
          <input
            v-model="form.password"
            class="field-input"
            type="password"
            placeholder="登录密码"
            autocomplete="new-password"
          />
        </div>
        <div class="form-field form-field--action">
          <button type="button" class="btn-primary" :disabled="adding" @click="handleAdd">
            {{ adding ? '添加中…' : '添加用户' }}
          </button>
        </div>
      </div>
    </section>

    <!-- 用户列表 -->
    <section class="panel panel--table">
      <div class="panel-header">
        <h2 class="panel-title">用户列表</h2>
        <span class="panel-count">{{ users.length }}</span>
      </div>

      <div v-if="loading" class="table-loading">加载中…</div>
      <div v-else-if="users.length === 0" class="table-empty">暂无用户</div>
      <div v-else class="table-scroll">
        <table class="user-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>显示名称</th>
              <th class="col-center">角色</th>
              <th class="col-right">创建时间</th>
              <th class="col-center col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>
                <span class="username-cell">{{ u.username }}</span>
                <span v-if="u.id === currentUserId" class="self-tag">当前</span>
              </td>
              <td>{{ u.display_name || '—' }}</td>
              <td class="col-center">
                <span class="role-badge" :class="u.is_admin ? 'role--admin' : 'role--user'">
                  {{ u.is_admin ? '管理员' : '普通用户' }}
                </span>
              </td>
              <td class="col-right col-mono">{{ formatTime(u.created_at) }}</td>
              <td class="col-center col-actions">
                <button
                  type="button"
                  class="btn-delete"
                  :disabled="!canDelete(u)"
                  :title="deleteHint(u)"
                  @click="handleDelete(u)"
                >
                  删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../stores/user'
import { listUsers, createUser, deleteUser, type AdminUser } from '../api/admin'

const userStore = useUserStore()
const users = ref<AdminUser[]>([])
const loading = ref(false)
const adding = ref(false)

const currentUserId = computed(() => {
  const match = users.value.find((u) => u.username === userStore.username)
  return match?.id || ''
})

const form = reactive({
  username: '',
  display_name: '',
  password: ''
})

function formatTime(t: string) {
  if (!t) return '—'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  return d.toLocaleString('zh-CN', { hour12: false })
}

function canDelete(u: AdminUser) {
  if (u.is_admin) return false
  if (u.username === userStore.username) return false
  return true
}

function deleteHint(u: AdminUser) {
  if (u.is_admin) return '不能删除管理员'
  if (u.username === userStore.username) return '不能删除当前登录账号'
  return '删除用户及其全部空间与数据'
}

async function loadUsers() {
  loading.value = true
  try {
    const res = await listUsers()
    users.value = res.data.data || []
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    ElMessage.error(err.response?.data?.detail || err.message || '加载用户列表失败')
    users.value = []
  } finally {
    loading.value = false
  }
}

async function handleAdd() {
  const username = form.username.trim()
  const password = form.password.trim()
  if (!username) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!password) {
    ElMessage.warning('请输入密码')
    return
  }

  adding.value = true
  try {
    await createUser({
      username,
      password,
      display_name: form.display_name.trim() || username
    })
    ElMessage.success(`用户「${username}」创建成功，已自动创建默认空间`)
    form.username = ''
    form.display_name = ''
    form.password = ''
    await loadUsers()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    ElMessage.error(err.response?.data?.detail || err.message || '创建失败')
  } finally {
    adding.value = false
  }
}

async function handleDelete(u: AdminUser) {
  if (!canDelete(u)) return
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${u.username}」吗？将同时删除其所有空间、上传文件与数据表，且不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
  } catch {
    return
  }

  try {
    await deleteUser(u.id)
    ElMessage.success(`用户「${u.username}」已删除`)
    await loadUsers()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    ElMessage.error(err.response?.data?.detail || err.message || '删除失败')
  }
}

onMounted(loadUsers)
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
  gap: 8px;
  margin-bottom: 16px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

.panel-count {
  font-size: 12px;
  color: var(--faint);
  background: #FAF8F5;
  border: 1px solid var(--border);
  padding: 2px 8px;
  border-radius: 999px;
}

.add-form {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.form-field {
  flex: 1;
  min-width: 140px;
}

.form-field--action {
  flex: 0 0 auto;
}

.field-label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--muted);
}

.field-input {
  width: 100%;
  height: 36px;
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

.field-input::placeholder {
  color: var(--faint);
}

.field-input:focus {
  background: var(--surface);
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
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

.user-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.user-table thead th {
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

.user-table tbody td {
  padding: 12px 14px;
  color: var(--text);
  border-bottom: 1px solid #F0EDE8;
  vertical-align: middle;
}

.user-table tbody tr:nth-child(even) {
  background: rgba(0, 0, 0, 0.012);
}

.user-table tbody tr:hover {
  background: var(--accent-soft);
}

.user-table tbody tr:last-child td {
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
  width: 88px;
}

.username-cell {
  font-weight: 500;
}

.self-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 500;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 4px;
}

.role-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.role--admin {
  background: var(--danger-soft);
  color: var(--danger);
}

.role--user {
  background: var(--accent-soft);
  color: var(--accent);
}

.btn-delete {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  color: var(--danger);
  background: transparent;
  border: 1px solid rgba(201, 74, 66, 0.35);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s var(--ease-out);
}

.btn-delete:hover:not(:disabled) {
  background: var(--danger-soft);
  border-color: rgba(201, 74, 66, 0.5);
}

.btn-delete:disabled {
  color: var(--faint);
  border-color: var(--border);
  cursor: not-allowed;
  opacity: 0.6;
}
</style>
