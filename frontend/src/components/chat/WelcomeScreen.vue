<template>
  <div class="chat-welcome">
    <div class="welcome-stage">
      <div class="welcome-hero-layer" aria-hidden="true">
        <img
          v-for="mode in chatModes"
          :key="mode.id"
          :src="mode.avatar"
          :alt="mode.label"
          class="welcome-hero"
          :class="{ 'welcome-hero--visible': contentMode === mode.id }"
          decoding="async"
        />
      </div>

      <div class="welcome-content" :class="{ 'welcome-content--fading': contentFading }">
        <h2 class="welcome-title">{{ displayModeConfig.welcomeTitle }}</h2>
        <p class="welcome-desc">{{ displayModeConfig.description }}</p>

        <div
          v-show="contentMode === 'insight'"
          class="prompt-layout prompt-layout--grid"
        >
          <div
            v-for="group in insightGroups"
            :key="group.title"
            class="prompt-card"
          >
            <h3 class="prompt-card__title">{{ group.title }}</h3>
            <div class="prompt-card__list">
              <button
                v-for="(q, qi) in group.questions"
                :key="qi"
                type="button"
                class="prompt-chip"
                @click="$emit('prompt-click', q)"
              >
                {{ q }}
              </button>
            </div>
          </div>
        </div>

        <div v-show="contentMode === 'deep'" class="prompt-layout">
          <div class="prompt-card prompt-card--single">
            <h3 class="prompt-card__title">推荐深度分析问题</h3>
            <div class="prompt-card__list">
              <button
                v-for="(q, i) in deepPrompts"
                :key="i"
                type="button"
                class="prompt-chip prompt-chip--long"
                @click="$emit('prompt-click', q)"
              >
                {{ q }}
              </button>
            </div>
          </div>
        </div>

        <div v-show="contentMode === 'builder'" class="prompt-layout">
          <div class="prompt-card prompt-card--single">
            <h3 class="prompt-card__title">描述你想看的销售报表</h3>
            <div class="prompt-card__list">
              <button
                v-for="(q, i) in builderPrompts"
                :key="i"
                type="button"
                class="prompt-chip prompt-chip--long"
                @click="$emit('prompt-click', q)"
              >
                {{ q }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChatModeId } from '../../constants/chatModes'

defineProps<{
  chatModes: Array<{ id: ChatModeId; label: string; avatar: string }>
  contentMode: ChatModeId
  contentFading: boolean
  displayModeConfig: { welcomeTitle: string; description: string }
  insightGroups: Array<{ title: string; questions: string[] }>
  deepPrompts: string[]
  builderPrompts: string[]
}>()

defineEmits<{
  'prompt-click': [text: string]
}>()
</script>

<style scoped>
.chat-welcome {
  flex: 1;
  min-height: 0;
  width: 100%;
  max-width: 920px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.welcome-stage {
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  isolation: isolate;
  overflow: hidden;
}

.welcome-hero-layer {
  position: absolute;
  left: 50%;
  top: 26%;
  z-index: 0;
  width: min(460px, 88vw);
  height: min(400px, 46vh);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.welcome-hero {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center bottom;
  opacity: 0;
  transition: opacity 0.32s ease;
  will-change: opacity;
}

.welcome-hero--visible {
  opacity: 1;
}

.welcome-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding-top: 148px;
  transition: opacity 0.22s ease;
}

.welcome-content--fading {
  opacity: 0.35;
  pointer-events: none;
}

.welcome-title {
  margin: 0 0 10px;
  font-size: 26px;
  font-weight: 500;
  letter-spacing: -0.03em;
  color: var(--chat-text);
  line-height: 1.25;
}

.welcome-desc {
  margin: 0 0 20px;
  font-size: 15px;
  color: var(--chat-muted);
  line-height: 1.55;
  max-width: 520px;
  font-weight: 400;
}

.prompt-layout {
  width: 100%;
  max-width: 720px;
}

.prompt-layout--grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.prompt-card {
  text-align: left;
  background: var(--chat-card-bg);
  border: 1.5px solid var(--chat-card-border);
  border-radius: 14px;
  padding: 14px 12px 12px;
  box-shadow: 0 1px 4px rgba(198, 97, 63, 0.05);
}

.prompt-card--single {
  max-width: 680px;
  margin: 0 auto;
  width: 100%;
  padding: 16px 14px 14px;
}

.prompt-card__title {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--chat-orange-soft);
  letter-spacing: 0;
}

.prompt-card__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prompt-chip {
  width: 100%;
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.5;
  font-family: inherit;
  text-align: left;
  color: var(--chat-orange);
  background: var(--chat-chip-bg);
  border: 1.5px solid var(--chat-chip-border);
  border-radius: 12px;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(198, 97, 63, 0.06);
  transition:
    background 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    color 0.18s ease;
}

.prompt-chip:hover {
  color: #A8522F;
  background: var(--chat-chip-hover);
  border-color: var(--chat-chip-border-hover);
  box-shadow: 0 2px 10px rgba(198, 97, 63, 0.1);
}

.prompt-chip--long {
  line-height: 1.6;
  padding: 16px 18px;
}

@media (max-width: 960px) {
  .prompt-layout--grid {
    grid-template-columns: 1fr;
  }
}
</style>
