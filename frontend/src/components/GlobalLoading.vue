<template>
  <Teleport to="body">
    <transition name="loading-fade">
      <div v-if="visible" class="global-loading-overlay">
        <div class="loading-content">
          <!-- 多层旋转环 -->
          <div class="ring-stage">
            <!-- 外层轨道环 -->
            <svg class="ring-layer ring-layer--outer" viewBox="0 0 120 120">
              <defs>
                <linearGradient id="ring-grad-outer" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#D97757" />
                  <stop offset="40%" stop-color="#E8A87C" />
                  <stop offset="70%" stop-color="#D97757" />
                  <stop offset="100%" stop-color="#C6613F" />
                </linearGradient>
              </defs>
              <circle
                class="ring-track"
                cx="60" cy="60" r="50"
                fill="none"
                stroke="rgba(217,119,87,0.1)"
                stroke-width="2"
              />
              <circle
                class="ring-arc ring-arc--outer"
                cx="60" cy="60" r="50"
                fill="none"
                stroke="url(#ring-grad-outer)"
                stroke-width="2"
                stroke-linecap="round"
                stroke-dasharray="160 240"
              />
            </svg>

            <!-- 中层轨道环（反向旋转） -->
            <svg class="ring-layer ring-layer--middle" viewBox="0 0 100 100">
              <circle
                class="ring-arc ring-arc--middle"
                cx="50" cy="50" r="38"
                fill="none"
                stroke="rgba(217,119,87,0.35)"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-dasharray="100 180"
              />
            </svg>

            <!-- 内层实心环 -->
            <svg class="ring-layer ring-layer--inner" viewBox="0 0 80 80">
              <circle
                class="ring-arc ring-arc--inner"
                cx="40" cy="40" r="28"
                fill="none"
                stroke="rgba(217,119,87,0.5)"
                stroke-width="1"
                stroke-linecap="round"
                stroke-dasharray="60 120"
              />
            </svg>

            <!-- 中心光晕 -->
            <div class="core-glow">
              <div class="core-dot" />
            </div>
          </div>

          <!-- 文字 -->
          <p class="loading-text">{{ text }}</p>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  visible: boolean
  text?: string
}>(), {
  text: '正在切换工作空间...'
})
</script>

<style scoped>
/* ============================================
   Overlay
   ============================================ */
.global-loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(16px) saturate(150%);
  -webkit-backdrop-filter: blur(16px) saturate(150%);
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 28px;
}

/* ============================================
   Ring Stage
   ============================================ */
.ring-stage {
  position: relative;
  width: 120px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ring-layer {
  position: absolute;
  overflow: visible;
}

.ring-layer--outer {
  width: 120px;
  height: 120px;
}

.ring-layer--middle {
  width: 100px;
  height: 100px;
}

.ring-layer--inner {
  width: 80px;
  height: 80px;
}

.ring-track {
  opacity: 0.5;
}

/* ============================================
   Arc Animations
   ============================================ */

/* 外层：顺时针，2s 一圈 */
.ring-arc--outer {
  transform-origin: 60px 60px;
  animation: arc-spin-cw 2s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
}

/* 中层：逆时针，2.8s 一圈 */
.ring-arc--middle {
  transform-origin: 50px 50px;
  animation: arc-spin-ccw 2.8s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
}

/* 内层：顺时针，3.6s 一圈 */
.ring-arc--inner {
  transform-origin: 40px 40px;
  animation: arc-spin-cw 3.6s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
}

/* ============================================
   Core Glow
   ============================================ */
.core-glow {
  position: absolute;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(217, 119, 87, 0.35) 0%, rgba(217, 119, 87, 0.08) 50%, transparent 70%);
  animation: core-breathe 1.8s ease-in-out infinite;
}

.core-dot {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(217, 119, 87, 0.8) 0%, rgba(217, 119, 87, 0.2) 40%, transparent 60%);
  animation: core-spark 1.8s ease-in-out infinite;
}

/* ============================================
   Text
   ============================================ */
.loading-text {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'PingFang SC', sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
  letter-spacing: 0.03em;
  animation: text-breathe 2s ease-in-out infinite;
}

/* ============================================
   Keyframes
   ============================================ */
@keyframes arc-spin-cw {
  0% {
    transform: rotate(0deg);
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dashoffset: -60;
  }
  100% {
    transform: rotate(360deg);
    stroke-dashoffset: 0;
  }
}

@keyframes arc-spin-ccw {
  0% {
    transform: rotate(0deg);
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dashoffset: 40;
  }
  100% {
    transform: rotate(-360deg);
    stroke-dashoffset: 0;
  }
}

@keyframes core-breathe {
  0%, 100% {
    opacity: 0.5;
    transform: scale(0.8);
  }
  50% {
    opacity: 1;
    transform: scale(1.3);
  }
}

@keyframes core-spark {
  0%, 100% {
    opacity: 0.4;
    transform: scale(0.6);
  }
  50% {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes text-breathe {
  0%, 100% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
}

/* ============================================
   Transition
   ============================================ */
.loading-fade-enter-active {
  transition: opacity 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.loading-fade-leave-active {
  transition: opacity 0.3s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.loading-fade-enter-from,
.loading-fade-leave-to {
  opacity: 0;
}
</style>
