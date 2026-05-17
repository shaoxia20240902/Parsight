<template>
  <div class="space-switcher">
    <el-dropdown
      trigger="click"
      placement="bottom-end"
      :show-arrow="false"
      :popper-options="{ modifiers: [{ name: 'offset', options: { offset: [0, 6] } }] }"
      popper-class="space-popper"
      @command="handleCommand"
    >
      <div class="space-trigger">
        <svg class="space-icon-svg" width="14" height="14" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.9"/>
          <rect x="14" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.65"/>
          <rect x="3" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.65"/>
          <rect x="14" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.9"/>
        </svg>
        <span class="space-name">{{ currentSpace?.name || '默认空间' }}</span>
        <svg class="arrow-icon-svg" width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M2.5 3.75L5 6.25L7.5 3.75" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <template #dropdown>
        <el-dropdown-menu class="space-dropdown">
          <div class="space-dropdown-header">工作空间</div>
          <el-dropdown-item
            v-for="space in spaces"
            :key="space.id"
            :command="space.id"
            class="space-menu-item"
            :class="{ 'is-current': space.id === currentSpace?.id }"
          >
            <div class="space-item">
              <span class="space-item-name">{{ space.name }}</span>
              <span v-if="space.id === currentSpace?.id" class="active-check" aria-hidden="true">✓</span>
            </div>
          </el-dropdown-item>
          <div class="space-divider"></div>
          <el-dropdown-item command="__create__" class="space-menu-item space-menu-item--action">
            <span class="action-row">
              <el-icon class="action-icon"><Plus /></el-icon>
              创建新空间
            </span>
          </el-dropdown-item>
          <el-dropdown-item
            v-if="currentSpace && spaces.length > 1"
            command="__delete__"
            class="space-menu-item space-menu-item--danger"
          >
            <span class="action-row">
              <el-icon class="action-icon"><Delete /></el-icon>
              删除当前空间
            </span>
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <!-- 创建空间对话框 -->
    <el-dialog
      v-model="showCreate"
      title="创建新空间"
      width="440px"
      :close-on-click-modal="false"
      destroy-on-close
      append-to-body
    >
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="空间名称" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入空间名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="空间编码" prop="code">
          <el-input v-model="createForm.code" placeholder="英文、数字、下划线" maxlength="50" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" placeholder="可选" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import * as spaceApi from '../api/space'
import type { Space } from '../api/space'

const SPACE_KEY = 'xlsx-bi-active-space'

const spaces = ref<Space[]>([])
const currentSpace = ref<Space | null>(null)
const showCreate = ref(false)
const creating = ref(false)
const createFormRef = ref()

const createForm = reactive({
  name: '',
  code: '',
  description: ''
})

const createRules = {
  name: [{ required: true, message: '请输入空间名称', trigger: 'blur' }],
  code: [
    { required: true, message: '请输入空间编码', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '编码只能包含字母、数字和下划线', trigger: 'blur' }
  ]
}

const emit = defineEmits<{
  (e: 'spaceChanged', space: Space | null): void
}>()

async function loadSpaces() {
  try {
    const res = await spaceApi.getSpaces()
    spaces.value = res.data.data || []
    const savedId = localStorage.getItem(SPACE_KEY)
    if (savedId) {
      const found = spaces.value.find(s => s.id === savedId)
      if (found) {
        currentSpace.value = found
        emit('spaceChanged', found)
        return
      }
    }
    const active = spaces.value.find(s => s.is_active)
    if (active) {
      currentSpace.value = active
      localStorage.setItem(SPACE_KEY, active.id)
      emit('spaceChanged', active)
    } else if (spaces.value.length > 0) {
      currentSpace.value = spaces.value[0]
      localStorage.setItem(SPACE_KEY, spaces.value[0].id)
      emit('spaceChanged', spaces.value[0])
    }
  } catch (e) {
    console.error('加载空间失败', e)
  }
}

async function handleCommand(command: string) {
  if (command === '__create__') {
    if (spaces.value.length >= 5) {
      ElMessage.warning('最多创建 5 个空间')
      return
    }
    createForm.name = ''
    createForm.code = ''
    createForm.description = ''
    showCreate.value = true
    await nextTick()
    createFormRef.value?.resetFields()
  } else if (command === '__delete__') {
    if (!currentSpace.value) return
    try {
      await ElMessageBox.confirm(
        `确定要删除空间「${currentSpace.value.name}」吗？该空间下的文件也将被删除。`,
        '删除确认',
        { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
      )
      await spaceApi.deleteSpace(currentSpace.value.id)
      ElMessage.success('空间已删除')
      localStorage.removeItem(SPACE_KEY)
      currentSpace.value = null
      await loadSpaces()
    } catch (e: any) {
      if (e !== 'cancel') {
        ElMessage.error('删除失败：' + (e.message || '未知错误'))
      }
    }
  } else {
    const target = spaces.value.find(s => s.id === command)
    if (target && target.id !== currentSpace.value?.id) {
      currentSpace.value = target
      localStorage.setItem(SPACE_KEY, target.id)
      emit('spaceChanged', target)
      ElMessage.success(`已切换到「${target.name}」`)
    }
  }
}

async function handleCreate() {
  if (!createFormRef.value) {
    ElMessage.error('表单未就绪，请稍后重试')
    return
  }
  try {
    await createFormRef.value.validate()
  } catch {
    ElMessage.warning('请正确填写空间名称和编码')
    return
  }

  creating.value = true
  try {
    const res = await spaceApi.createSpace({
      name: createForm.name,
      code: createForm.code,
      description: createForm.description
    })
    ElMessage.success('空间创建成功')
    showCreate.value = false
    const newSpace = res.data.data
    spaces.value.push(newSpace)
    currentSpace.value = newSpace
    localStorage.setItem(SPACE_KEY, newSpace.id)
    emit('spaceChanged', newSpace)
  } catch (e: any) {
    ElMessage.error('创建失败：' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

onMounted(loadSpaces)

defineExpose({ currentSpace, spaces, loadSpaces })
</script>

<style scoped>
.space-switcher {
  display: flex;
  align-items: center;
}

.space-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 10px;
  background: #FFFFFF;
  border: 1px solid #E5E0D8;
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.15s var(--ease-out), background 0.15s var(--ease-out);
}

.space-trigger:hover {
  background: #FAF8F5;
  border-color: #D4CEC4;
}

.space-icon-svg {
  color: #D97757;
  flex-shrink: 0;
}

.space-name {
  font-size: 13px;
  font-weight: 500;
  color: #1C1917;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arrow-icon-svg {
  color: #A39E96;
  flex-shrink: 0;
  transition: transform 0.15s var(--ease-out);
}

.space-dropdown {
  min-width: 220px;
}

.space-dropdown-header {
  padding: 10px 12px 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #A39E96;
}

.space-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
}

.space-item-name {
  font-size: 13px;
  color: #1C1917;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.active-check {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: #D97757;
  line-height: 1;
}

.action-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.action-icon {
  font-size: 14px;
}

.space-divider {
  height: 1px;
  background: #E5E0D8;
  margin: 6px 8px;
}
</style>

<!-- 下拉浮层挂载在 body，需全局样式覆盖 Element Plus 默认蓝底 -->
<style>
.space-popper.el-popper {
  border: 1px solid #E5E0D8 !important;
  border-radius: 12px !important;
  padding: 6px !important;
  background: #FFFFFF !important;
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.04),
    0 8px 28px rgba(28, 25, 23, 0.1) !important;
}

.space-popper .el-popper__arrow::before {
  border-color: #E5E0D8 !important;
  background: #FFFFFF !important;
}

.space-popper .el-dropdown-menu {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

.space-popper .el-dropdown-menu__item {
  margin: 2px 0;
  padding: 8px 12px !important;
  border-radius: 8px;
  line-height: normal;
}

.space-popper .el-dropdown-menu__item:not(.is-disabled):focus {
  background: transparent !important;
  color: inherit;
}

.space-popper .el-dropdown-menu__item:hover {
  background: rgba(28, 25, 23, 0.05) !important;
  color: #1C1917 !important;
}

.space-popper .space-menu-item.is-current,
.space-popper .space-menu-item.is-current:hover {
  background: rgba(217, 119, 87, 0.1) !important;
}

.space-popper .space-menu-item.is-current .space-item-name {
  color: #D97757;
  font-weight: 600;
}

.space-popper .space-menu-item--action,
.space-popper .space-menu-item--action:hover {
  color: #736C64 !important;
}

.space-popper .space-menu-item--danger,
.space-popper .space-menu-item--danger:hover {
  color: #C94A42 !important;
}

.space-popper .space-menu-item--danger:hover {
  background: rgba(255, 59, 48, 0.08) !important;
}
</style>
