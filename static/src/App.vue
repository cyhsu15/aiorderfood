<template>
  <div class="flex flex-col min-h-screen bg-gray-50">
    <!-- 🔹 全域通知（置頂顯示） -->
    <GlobalNotification />

    <!-- 🔹 桌號標籤（左側固定，僅在共享桌號模式下顯示） -->
    <Transition name="slide-in">
      <div
        v-if="sessionStore.isSharedTable"
        class="fixed left-0 top-20 z-40"
      >
        <!-- 收合狀態：小標籤 -->
        <button
          v-if="!showSessionInfo"
          @click="showSessionInfo = true"
          class="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white px-3 py-2 rounded-r-lg shadow-lg hover:shadow-xl transition-all hover:px-4"
        >
          <span class="font-bold text-lg">{{ sessionStore.tableId }}</span>
          <!-- 連線狀態燈號 -->
          <span
            class="w-3 h-3 rounded-full"
            :class="cartStore.sseConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'"
            :title="cartStore.sseConnected ? '已連線' : '未連線'"
          ></span>
        </button>

        <!-- 展開狀態：詳細資訊面板 -->
        <Transition name="expand">
          <div
            v-if="showSessionInfo"
            class="bg-white/95 backdrop-blur-lg rounded-r-2xl shadow-2xl border-r-4 border-purple-500 min-w-[280px] max-w-[320px]"
          >
            <!-- 標題列 -->
            <div class="bg-gradient-to-r from-purple-600 to-indigo-600 text-white px-4 py-3 rounded-tr-2xl flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-xl font-bold">{{ sessionStore.tableId }}</span>
                <span
                  class="w-3 h-3 rounded-full"
                  :class="cartStore.sseConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'"
                ></span>
              </div>
              <button
                @click="showSessionInfo = false"
                class="w-6 h-6 flex items-center justify-center rounded-full hover:bg-white/20 transition"
              >
                <span class="text-xl">×</span>
              </button>
            </div>

            <!-- 內容區 -->
            <div class="p-4 space-y-3 text-sm text-gray-700">
              <div>
                <p class="text-xs text-gray-500 font-semibold mb-1">模式</p>
                <p class="flex items-center gap-2">
                  <span>👥</span>
                  <span class="font-medium">多人點餐模式</span>
                </p>
              </div>

              <div>
                <p class="text-xs text-gray-500 font-semibold mb-1">連線狀態</p>
                <p class="flex items-center gap-2">
                  <span v-if="cartStore.sseConnected" class="text-green-600">✓ 即時同步中</span>
                  <span v-else class="text-red-600">✗ 未連線</span>
                </p>
              </div>

              <div>
                <p class="text-xs text-gray-500 font-semibold mb-1">Session ID</p>
                <p class="text-xs font-mono bg-gray-100 px-2 py-1 rounded break-all">
                  {{ sessionStore.sessionId }}
                </p>
              </div>

              <!-- SSE 診斷區域 -->
              <div v-if="sseConnectionStatus" class="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs">
                <p class="font-semibold text-blue-900 mb-2">🔍 連線診斷</p>
                <p><strong>ReadyState:</strong> {{ sseConnectionStatus.readyState }}</p>
                <p class="text-xs text-gray-600 mb-1">{{ sseConnectionStatus.readyStateText }}</p>
                <p class="mt-2" :class="sseConnectionStatus.isHealthy ? 'text-green-600' : 'text-red-600'">
                  {{ sseConnectionStatus.isHealthy ? '✅ 連線正常' : '❌ 連線異常' }}
                </p>
              </div>

              <button
                @click="diagnoseSseConnection"
                class="w-full px-3 py-2 bg-purple-100 hover:bg-purple-200 text-purple-700 rounded-lg text-xs font-medium transition"
              >
                🔍 診斷 SSE 連線
              </button>

              <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-800">
                💡 同桌的人掃描相同 QR Code 進入，購物車會即時同步
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>

    <!-- 🔹 主內容 -->
    <main class="flex-1">
      <router-view />
    </main>

    <!-- 🔹 底部導航 -->
    <BottomBar />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import BottomBar from './components/BottomBar.vue'
import GlobalNotification from './components/GlobalNotification.vue'
import { useSessionStore } from './stores/session'
import { useCartStore } from './stores/cart'

const sessionStore = useSessionStore()
const cartStore = useCartStore()
const showSessionInfo = ref(false)
const sseConnectionStatus = ref(null)

/**
 * 診斷 SSE 連線狀態
 */
function diagnoseSseConnection() {
  console.log('[App] 執行 SSE 連線診斷...')

  const connection = cartStore.sseConnection

  if (!connection) {
    sseConnectionStatus.value = {
      readyState: -1,
      readyStateText: '無連線物件',
      url: 'N/A',
      isHealthy: false
    }
    console.error('[App] ❌ 沒有 SSE 連線物件')
    return
  }

  const readyState = connection.readyState
  const readyStateMap = {
    0: 'CONNECTING（連線中）',
    1: 'OPEN（已開啟）✅',
    2: 'CLOSED（已關閉）❌'
  }

  sseConnectionStatus.value = {
    readyState,
    readyStateText: readyStateMap[readyState] || 'UNKNOWN',
    url: connection.url,
    isHealthy: readyState === 1
  }

  console.log('[App] SSE 診斷結果:', sseConnectionStatus.value)

  // 測試事件接收（如果連線正常）
  if (readyState === 1) {
    console.log('[App] ✅ SSE 連線正常，添加測試監聽器...')

    // 添加臨時測試監聽器
    const testListener = (e) => {
      console.log('🧪 [測試] 收到 cart_updated 事件:', e.data)
      alert('✅ SSE 測試成功！收到 cart_updated 事件\n請查看 Console 日誌')
      // 移除測試監聽器
      connection.removeEventListener('cart_updated', testListener)
    }

    connection.addEventListener('cart_updated', testListener)
    console.log('[App] 測試監聽器已添加，請在其他分頁操作購物車')

    // 5 秒後自動移除測試監聽器
    setTimeout(() => {
      connection.removeEventListener('cart_updated', testListener)
      console.log('[App] 測試監聽器已自動移除')
    }, 5000)
  } else {
    console.error('[App] ❌ SSE 連線狀態異常:', readyStateMap[readyState])
    alert('❌ SSE 連線異常\nreadyState: ' + readyState + '\n' + readyStateMap[readyState])
  }
}

// 應用程式啟動時初始化
onMounted(() => {
  // 1. 初始化 Session（讀取 URL 參數或 localStorage）
  sessionStore.initialize()

  // 2. 如果是共享桌號模式，初始化購物車並建立 SSE 連線
  if (sessionStore.hasSession) {
    console.log('[App] Shared session detected, initializing cart with SSE...')

    // 確保購物車已載入
    cartStore.ensureLoaded().then(() => {
      // 建立 SSE 連線
      cartStore.connectSSE(sessionStore.sessionId)
    })
  }
})
</script>

<style scoped>
/* 桌號標籤滑入動畫 */
.slide-in-enter-active {
  transition: all 0.4s ease-out;
}

.slide-in-leave-active {
  transition: all 0.3s ease-in;
}

.slide-in-enter-from {
  transform: translateX(-100%);
  opacity: 0;
}

.slide-in-leave-to {
  transform: translateX(-100%);
  opacity: 0;
}

/* 面板展開動畫 */
.expand-enter-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.expand-leave-active {
  transition: all 0.25s ease-in;
}

.expand-enter-from {
  transform: translateX(-20px);
  opacity: 0;
  scale: 0.95;
}

.expand-leave-to {
  transform: translateX(-20px);
  opacity: 0;
  scale: 0.95;
}
</style>
