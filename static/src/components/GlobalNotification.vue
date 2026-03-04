<template>
  <!-- 全域通知組件 - 浮動視窗（Toast） -->
  <Transition name="toast">
    <div
      v-if="notification"
      @click="handleClose"
      class="fixed top-4 left-1/2 -translate-x-1/2 z-[9999] cursor-pointer max-w-md w-[90%] pointer-events-auto"
    >
      <div
        class="rounded-2xl shadow-2xl backdrop-blur-lg border px-4 py-3 flex items-start gap-3"
        :class="notificationClasses"
      >
        <!-- 圖示 -->
        <span class="text-2xl flex-shrink-0 animate-bounce-subtle">{{ notificationIcon }}</span>

        <!-- 訊息內容 -->
        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold break-words leading-tight">{{ notification.message }}</p>
        </div>

        <!-- 關閉按鈕 -->
        <button
          @click.stop="handleClose"
          class="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full hover:bg-black/10 transition"
          aria-label="關閉"
        >
          <span class="text-xl font-light">×</span>
        </button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useCartStore } from '../stores/cart'

const cartStore = useCartStore()

// 取得通知物件
const notification = computed(() => cartStore.conflictNotification)

// 根據通知類型決定樣式
const notificationClasses = computed(() => {
  if (!notification.value) return ''

  const typeStyles = {
    success: 'bg-green-500/85 border-green-400/50 text-white',
    info: 'bg-blue-500/85 border-blue-400/50 text-white',
    warning: 'bg-yellow-500/85 border-yellow-400/50 text-gray-900',
    error: 'bg-red-500/85 border-red-400/50 text-white'
  }

  return typeStyles[notification.value.type] || 'bg-gray-800/85 border-gray-600/50 text-white'
})

// 根據通知類型決定圖示
const notificationIcon = computed(() => {
  if (!notification.value) return ''

  const typeIcons = {
    success: '✅',
    info: '🔔',
    warning: '⚠️',
    error: '❌'
  }

  return typeIcons[notification.value.type] || 'ℹ️'
})

// 關閉通知
function handleClose() {
  cartStore.clearNotification()
}

// 監聽通知變化，自動在 3 秒後消失
watch(notification, (newVal) => {
  if (newVal) {
    console.log('[GlobalNotification] 顯示通知:', newVal.message)

    // 3 秒後自動關閉
    setTimeout(() => {
      if (cartStore.conflictNotification?.timestamp === newVal.timestamp) {
        handleClose()
      }
    }, 3000)
  }
})
</script>

<style scoped>
/* Toast 動畫 - 從上方滑入並帶有彈性效果 */
.toast-enter-active {
  animation: toastIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.toast-leave-active {
  animation: toastOut 0.3s ease-in;
}

@keyframes toastIn {
  from {
    transform: translate(-50%, -150%);
    opacity: 0;
    scale: 0.8;
  }
  to {
    transform: translate(-50%, 0);
    opacity: 1;
    scale: 1;
  }
}

@keyframes toastOut {
  from {
    transform: translate(-50%, 0);
    opacity: 1;
    scale: 1;
  }
  to {
    transform: translate(-50%, -150%);
    opacity: 0;
    scale: 0.9;
  }
}

/* 圖示微彈跳動畫 */
@keyframes bounce-subtle {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-3px);
  }
}

.animate-bounce-subtle {
  animation: bounce-subtle 0.6s ease-in-out;
}
</style>
