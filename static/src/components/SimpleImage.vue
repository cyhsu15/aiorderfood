<template>
  <img
    :src="currentSrc"
    :alt="alt"
    :class="imgClass"
    @error="handleError"
  />
</template>

<script setup>
import { ref, computed } from 'vue'
import { toWebP } from '../utils/imageUtils'

const props = defineProps({
  src: {
    type: String,
    required: true
  },
  alt: {
    type: String,
    default: ''
  },
  fallback: {
    type: String,
    default: '/images/default.png'
  },
  imgClass: {
    type: String,
    default: ''
  }
})

const currentSrc = ref(toWebP(props.src))
const hasError = ref(false)
const triedOriginal = ref(false)

function handleError() {
  if (!hasError.value) {
    // 第一次錯誤：嘗試原始格式
    if (!triedOriginal.value && currentSrc.value.endsWith('.webp')) {
      triedOriginal.value = true
      currentSrc.value = props.src
      return
    }

    // 第二次錯誤：使用 fallback
    if (currentSrc.value !== props.fallback) {
      hasError.value = true
      currentSrc.value = props.fallback
    }
  }
}
</script>

<style scoped>
img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
