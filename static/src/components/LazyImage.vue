<template>
  <div class="lazy-image-wrapper" :class="wrapperClass">
    <!-- 載入中佔位符 -->
    <div
      v-if="loading"
      class="skeleton-loader"
      :style="{ width: '100%', height: '100%' }"
    ></div>

    <!-- 實際圖片 -->
    <img
      :data-src="src"
      :alt="alt"
      :class="[imgClass, { 'is-loaded': !loading }]"
      ref="imgRef"
      @load="onLoad"
      @error="onError"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
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
  },
  wrapperClass: {
    type: String,
    default: ''
  },
  // 提前多少像素開始載入（rootMargin）
  threshold: {
    type: String,
    default: '50px'
  }
})

const imgRef = ref(null)
const loading = ref(true)
const observer = ref(null)
const triedOriginal = ref(false)

// 圖片載入完成
function onLoad() {
  loading.value = false
}

// 圖片載入失敗，使用備用圖片
function onError(e) {
  // 第一次錯誤：嘗試原始格式
  if (!triedOriginal.value && e.target.src.endsWith('.webp')) {
    triedOriginal.value = true
    e.target.src = props.src
    return
  }

  // 第二次錯誤：使用 fallback
  if (e.target.src !== props.fallback) {
    e.target.src = props.fallback
  }
  loading.value = false
}

// 初始化 Intersection Observer
function initObserver() {
  if (!imgRef.value) return

  // 檢查瀏覽器是否支援 IntersectionObserver
  if (!('IntersectionObserver' in window)) {
    // 不支援則直接載入圖片
    loadImage()
    return
  }

  observer.value = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        // 當圖片進入可視區域
        if (entry.isIntersecting) {
          loadImage()
          // 載入後停止觀察
          if (observer.value && imgRef.value) {
            observer.value.unobserve(imgRef.value)
          }
        }
      })
    },
    {
      rootMargin: props.threshold, // 提前載入
      threshold: 0.01 // 只要有 1% 進入視窗就觸發
    }
  )

  observer.value.observe(imgRef.value)
}

// 載入圖片
function loadImage() {
  if (!imgRef.value) return
  const dataSrc = imgRef.value.getAttribute('data-src')
  if (dataSrc) {
    imgRef.value.src = toWebP(dataSrc)
  }
}

onMounted(() => {
  // 使用 nextTick 確保 DOM 已經渲染
  nextTick(() => {
    initObserver()
  })
})

onBeforeUnmount(() => {
  if (observer.value && imgRef.value) {
    observer.value.unobserve(imgRef.value)
  }
})
</script>

<style scoped>
.lazy-image-wrapper {
  position: relative;
  overflow: hidden;
  min-height: 100px; /* 確保骨架屏有最小高度 */
}

/* 骨架屏動畫 */
.skeleton-loader {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    #f0f0f0 25%,
    #e0e0e0 50%,
    #f0f0f0 75%
  );
  background-size: 200% 100%;
  animation: loading 1.5s infinite;
  z-index: 1;
}

@keyframes loading {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

/* 圖片淡入效果 */
img {
  opacity: 0;
  transition: opacity 0.3s ease-in;
  display: block;
}

/* 圖片載入完成後顯示 */
img.is-loaded {
  opacity: 1;
}
</style>
