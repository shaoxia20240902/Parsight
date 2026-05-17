<template>
  <component
    :is="tag"
    class="brand-logo"
    :class="[`brand-logo--${variant}`, { 'brand-logo--block': block }]"
    :aria-label="ariaLabel"
  >
    <img
      v-if="variant === 'full'"
      class="brand-logo__img brand-logo__img--full"
      src="/logo-full.svg"
      alt=""
      draggable="false"
    />
    <img
      v-else
      class="brand-logo__img brand-logo__img--icon"
      src="/logo-icon.svg"
      alt=""
      draggable="false"
    />
    <span v-if="showText" class="brand-logo__text">
      <span class="brand-logo__cn">{{ BRAND_NAME }}</span>
      <span v-if="showEn" class="brand-logo__en">{{ BRAND_NAME_EN }}</span>
    </span>
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BRAND_NAME, BRAND_NAME_EN } from '../../constants/brand'

const props = withDefaults(
  defineProps<{
    /** icon：仅图形；full：完整横版 SVG；compact：图形 + 中文 */
    variant?: 'icon' | 'full' | 'compact'
    /** 是否显示中文/英文文案（full 变体自带文字，此项无效） */
    showText?: boolean
    showEn?: boolean
    block?: boolean
    tag?: string
  }>(),
  {
    variant: 'compact',
    showText: true,
    showEn: false,
    block: false,
    tag: 'span'
  }
)

const ariaLabel = computed(() =>
  props.variant === 'full' ? `${BRAND_NAME} ${BRAND_NAME_EN}` : BRAND_NAME
)
</script>

<style scoped>
.brand-logo {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  line-height: 1;
}

.brand-logo--block {
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}

.brand-logo__img {
  display: block;
  flex-shrink: 0;
  user-select: none;
}

.brand-logo__img--icon {
  height: 28px;
  width: auto;
}

.brand-logo--compact .brand-logo__img--icon {
  height: 26px;
}

.brand-logo__img--full {
  height: 48px;
  width: auto;
}

.brand-logo--full .brand-logo__img--full {
  height: 56px;
  max-width: min(280px, 88vw);
}

.brand-logo__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-logo__cn {
  font-size: 15px;
  font-weight: 600;
  color: #101D3B;
  letter-spacing: -0.02em;
}

.brand-logo__en {
  font-size: 11px;
  font-weight: 600;
  color: #736C64;
  letter-spacing: 0.04em;
}

.brand-logo__en::after {
  content: none;
}
</style>
