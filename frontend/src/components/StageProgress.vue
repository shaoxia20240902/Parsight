<template>
  <div class="stage-progress">
    <div class="stage-progress-head">
      <span class="stage-progress-title">{{ title }}</span>
      <span class="stage-progress-desc">{{ desc }}</span>
    </div>
    <div class="stage-progress-track">
      <div
        v-for="(stage, index) in stages"
        :key="stage.title"
        class="stage-progress-item"
        :class="{
          active: index === activeIndex,
          complete: index < activeIndex,
          pending: index > activeIndex,
        }"
      >
        <span class="stage-progress-dot">
          <el-icon v-if="index === activeIndex" class="stage-progress-spinner is-loading">
            <Loading />
          </el-icon>
          <span v-else class="stage-progress-index">{{ index + 1 }}</span>
        </span>
        <span class="stage-progress-label">{{ stage.title }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
export interface Stage {
  title: string
}

interface Props {
  title: string
  desc: string
  stages: Stage[]
  activeIndex: number
}

defineProps<Props>()
</script>

<style scoped>
.stage-progress {
  --stage-bg-top: var(--color-accent-warm-bg-top, #FFFCF7);
  --stage-bg-bottom: var(--color-accent-warm-bg-bottom, #F7F1E8);
  --stage-border: var(--color-accent-warm-border, #E3D8CA);
  --stage-text: var(--color-accent-warm-text, #2B211B);
  --stage-muted: var(--color-accent-warm-muted, #7B6F65);
  --stage-faint: var(--color-accent-warm-faint, #A69A90);
  --stage-line: var(--color-accent-warm-line, #E7DCCF);
  --stage-accent: var(--color-accent-warm, #D97757);
  --stage-accent-strong: var(--color-accent-warm-strong, #B85F43);
  padding: 24px 28px 22px;
  margin-bottom: 28px;
  font-family: var(--font-family);
  background: linear-gradient(180deg, var(--stage-bg-top) 0%, var(--stage-bg-bottom) 100%);
  border: 1px solid var(--stage-border);
  border-radius: 16px;
  box-shadow: 0 12px 34px rgba(66, 45, 31, 0.08);
}

.stage-progress-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.stage-progress-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--stage-text);
  letter-spacing: 0;
  white-space: nowrap;
}

.stage-progress-desc {
  min-width: 0;
  font-size: 16px;
  line-height: 1.4;
  color: var(--stage-muted);
  text-align: right;
}

.stage-progress-track {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  column-gap: 18px;
}

.stage-progress-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.stage-progress-item:not(:last-child)::after {
  content: "";
  position: absolute;
  left: 34px;
  right: calc(-100% + 18px);
  top: 14px;
  height: 4px;
  background: var(--stage-line);
  border-radius: 999px;
}

.stage-progress-item.complete:not(:last-child)::after {
  background: var(--stage-accent);
}

.stage-progress-dot {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 50%;
  background: var(--stage-line);
  border: 4px solid var(--stage-bg-top);
  box-shadow: 0 3px 10px rgba(66, 45, 31, 0.14);
}

.stage-progress-item.complete .stage-progress-dot,
.stage-progress-item.active .stage-progress-dot {
  background: var(--stage-accent);
}

.stage-progress-item.active .stage-progress-dot {
  box-shadow: 0 0 0 6px rgba(217, 119, 87, 0.14), 0 6px 16px rgba(184, 95, 67, 0.22);
}

.stage-progress-spinner {
  font-size: 17px;
  color: #fff;
}

.stage-progress-index {
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  color: #fff;
}

.stage-progress-item.pending .stage-progress-index {
  color: var(--stage-muted);
}

.stage-progress-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
  font-weight: 700;
  color: var(--stage-faint);
}

.stage-progress-item.complete .stage-progress-label,
.stage-progress-item.active .stage-progress-label {
  color: var(--stage-text);
}

.stage-progress-item.active .stage-progress-label {
  color: var(--stage-accent-strong);
}
</style>
