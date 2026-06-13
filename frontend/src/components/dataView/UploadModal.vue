<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
        <div class="modal-panel upload-modal">
          <div class="modal-header">
            <h3 class="modal-title">上传 XLSX 文件</h3>
            <button class="modal-close" @click="$emit('close')">
              <el-icon><Close /></el-icon>
            </button>
          </div>

          <el-upload
            class="upload-area"
            drag
            :auto-upload="false"
            :on-change="handleFileChange"
            :show-file-list="false"
            accept=".xlsx,.xls"
          >
            <div class="upload-inner">
              <div class="upload-icon-wrap">
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
              </div>
              <div class="upload-text">
                将文件拖到此处，或<span class="upload-link">点击上传</span>
              </div>
              <div class="upload-tip">支持 .xlsx / .xls 格式，最多 5 个 Sheet</div>
            </div>
          </el-upload>

          <div v-if="selectedFile" class="selected-file">
            <el-icon><Document /></el-icon>
            <span>{{ selectedFile.name }}</span>
          </div>

          <div class="modal-footer">
            <button class="btn-secondary" @click="$emit('close')">取消</button>
            <button class="btn-primary" :disabled="!selectedFile || uploading" @click="confirm">
              {{ uploading ? '上传中…' : '确认上传' }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { UploadFilled, Document, Close } from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
  uploading?: boolean
}>()

const emit = defineEmits<{
  close: []
  confirm: [file: File]
}>()

const selectedFile = ref<File | null>(null)

watch(() => props.visible, (visible) => {
  if (visible) selectedFile.value = null
})

function handleFileChange(file: any) {
  selectedFile.value = file.raw
}

function confirm() {
  if (selectedFile.value) {
    emit('confirm', selectedFile.value)
  }
}
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

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-lg);
}

.modal-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--color-text-primary);
}

.modal-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: all 0.15s;
}

.modal-close:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--color-text-primary);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-xl);
}

.upload-modal .upload-area :deep(.el-upload-dragger) {
  background: var(--color-bg);
  border: 2px dashed rgba(0, 0, 0, 0.08);
  border-radius: var(--radius-lg);
  padding: 32px 20px;
}

.upload-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.upload-icon-wrap {
  margin-bottom: var(--spacing-base);
}

.upload-icon {
  font-size: 40px;
  color: var(--color-text-tertiary);
  opacity: 0.5;
}

.upload-text {
  color: var(--color-text-secondary);
  font-size: var(--text-base);
}

.upload-link {
  color: var(--dv-accent);
  cursor: pointer;
}

.upload-tip {
  color: var(--color-text-tertiary);
  font-size: var(--text-sm);
  margin-top: var(--spacing-sm);
}

.selected-file {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-base);
  padding: var(--spacing-sm) var(--spacing-base);
  background: rgba(52, 199, 89, 0.06);
  border-radius: var(--radius-base);
  color: var(--color-success);
  font-size: var(--text-base);
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
