<template>
  <div
    class="min-h-screen flex flex-col items-center p-4 relative overflow-hidden"
    style="background: linear-gradient(to bottom, #B54820FF, #F0D9B5);"
  >
    <!-- 🔹 LOGO背景（固定不動） -->
    <div
      class="fixed inset-0 bg-center bg-no-repeat bg-contain pointer-events-none"
      style="
        background-image: url('/images/logo.png');
        opacity: 0.15;
        filter: drop-shadow(0 0 8px rgba(255,255,255,0.25));
        z-index: 0;
      "
    ></div>

    <!-- 🔸 主內容框 -->
    <div
      class="w-full max-w-md bg-[#FFFDF8] rounded-2xl shadow-lg flex flex-col"
      style="
        height: calc(100vh - 80px);
        max-height: calc(100vh - 80px);
      "
    >
      <!-- 標題區 -->
      <div class="flex justify-between items-center bg-[#B22E00] text-white px-4 py-3 rounded-t-2xl shadow-md">
        <h2 class="font-bold text-lg tracking-wide">錦霞樓推薦助理</h2>
        <button
          @click="resetChat"
          class="text-sm bg-white/20 hover:bg-white/30 px-2 py-1 rounded transition"
        >
          🔄 重新開始
        </button>
      </div>

      <!-- 💬 聊天內容 -->
      <div
        ref="chatContainer"
        class="flex-1 overflow-y-auto p-4 space-y-4 pb-28"
        style="scroll-behavior: smooth;"
      >
        <transition-group name="fade" tag="div">
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="flex mb-2"
            :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              :class="[ 
                'px-4 py-3 rounded-2xl max-w-[85%] leading-relaxed shadow-sm',
                msg.role === 'user'
                  ? 'bg-[#F5E1C0] text-[#2B1B0F] rounded-br-none backdrop-blur-sm'
                  : 'bg-white/80 text-[#2B1B0F] rounded-bl-none backdrop-blur-sm  border border-[#F0D9B5]'
              ]"
            >
              <!-- 訊息內容或載入動畫 -->
              <p v-if="msg.content" class="whitespace-pre-line">{{ msg.content }}</p>

              <!-- AI 思考中動畫 -->
              <div v-else-if="msg.role === 'assistant' && msg.isLoading" class="flex items-center gap-2 py-1">
                <div class="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>

              <!-- 推薦菜色卡片 -->
              <div v-if="msg.recommendations?.length" class="mt-3 space-y-3">
                <div
                  v-for="(r, j) in msg.recommendations"
                  :key="j"
                  @click="openDish(r)"
                  class="flex items-start gap-3 bg-[#FFFDF8] border border-[#F0D9B5] rounded-xl p-2 shadow-sm hover:shadow-md transition cursor-pointer"
                >
                  <img
                    :src="toWebP(r.image_url) || '/images/default.png'"
                    class="w-16 h-16 rounded-lg object-cover"
                    @error="(e) => e.target.src = '/images/default.png'"
                  />
                  <div class="flex-1">
                    <p class="font-bold text-[#B22E00]">{{ r.name }}</p>
                    <p class="text-sm text-[#8B5E3C]">{{ r.reason }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </transition-group>
      </div>

      <!-- 🎯 快速選取按鈕區 -->
      <div class="px-3 py-2 border-t border-[#F0D9B5] bg-[#FFFDF8]">
        <div class="flex gap-2 overflow-x-auto pb-1" style="scrollbar-width: thin;">
          <button
            v-for="(reply, index) in quickReplies"
            :key="index"
            @click="selectQuickReply(reply.text)"
            :disabled="isWaitingResponse"
            class="flex-shrink-0 inline-flex items-center gap-1 px-3 py-1.5
                   border border-[#F0D9B5] rounded-full text-sm
                   bg-white hover:bg-[#B22E00] hover:text-white hover:border-[#B22E00]
                   text-[#2B1B0F] transition-all duration-200 shadow-sm hover:shadow-md
                   whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white disabled:hover:text-[#2B1B0F]"
          >
            <span>{{ reply.icon }}</span>
            <span>{{ reply.text }}</span>
          </button>
        </div>
      </div>

      <!-- 🧡 輸入區 -->
      <div class="p-3 border-t bg-[#FFFDF8] sticky bottom-0 flex flex-col gap-2">
        <!-- 📝 輸入框 -->
        <textarea
          v-model="input"
          placeholder="想吃什麼？例如：三道肉、一湯"
          @keydown.enter.prevent="sendMessage"
          @focus="scrollToBottom"
          :disabled="isRecording || isTranscribing || isWaitingResponse"
          class="w-full resize-none border border-[#F0D9B5] rounded-lg px-3 py-2 text-[#2B1B0F]
                 focus:outline-none focus:ring-2 focus:ring-[#B22E00]/50 bg-white max-h-[80px] overflow-y-auto
                 disabled:opacity-50 disabled:cursor-not-allowed"
        ></textarea>

        <!-- 🎛 控制列 -->
        <div class="flex justify-end items-center relative mt-1">
          <!-- 🔊 波形 + 錄音時間 -->
          <div v-if="isRecording" class="absolute left-0 flex items-center gap-2 pl-1">
            <!-- 錄音時間顯示 -->
            <span class="text-white bg-black/60 text-xs px-2 py-[2px] rounded">
              {{ formatTime(getRecordingTime()) }}
            </span>

            <!-- 動態波形 -->
            <div v-if="isRecording" class="flex gap-[2px] items-center h-12 overflow-hidden">
              <div
                v-for="(bar, i) in [...waveform].reverse()"
                :key="i"
                class="w-[3px] bg-green-500 rounded"
                :style="{ height: bar + 'px', marginTop: (maxHeight - bar)/2 + 'px' }"
              ></div>
            </div>
          </div>
          
          <!-- 取消轉寫按鈕 -->
          <template v-if="isTranscribing">
            <button
              @click="abortTranscription"
              class="relative h-9 w-9 mx-2 rounded-full flex items-center justify-center bg-[#B22E00] overflow-hidden"
            >
              <!-- 流光圓圈 -->
             <span class="absolute inset-0 rounded-full border-4 border-white border-t-transparent animate-spin-slow"></span>
              
              <!-- 靜止的 X -->
              <span class="relative text-white text-xl font-bold">X</span>
            </button>
          </template>

          <!-- 🔴 錄音控制按鈕 -->
          <template v-else-if="isRecording">
            <button
              @click="cancelRecording"
              class="h-9 w-9 hover:text-red-600 text-2xl mx-2"
            >✖</button>
            <button
              :disabled="getRecordingTime() <= 0.5"
              @click="stopRecording"
              :class="[
                'h-9 w-9 l mx-2 transition',
                getRecordingTime() <= 0.5
                  ? 'text-gray-400 cursor-not-allowed'
                  : 'text-green-500 hover:text-green-600 cursor-pointer'
              ]"
            >✔</button>
          </template>

          <!-- 🎤 麥克風與發送按鈕 -->
          <template v-else>
            <!-- 麥克風 -->
            <button
              type="button"
              @click="toggleRecording"
              class="w-9 h-9 mx-2 flex items-center justify-center rounded-full hover:bg-white/30 transition text-[#B22E00] text-xl"
            >
              🎤
            </button>

            <!-- 發送按鈕 -->
            <button
              v-if="input.trim().length > 0 && !isRecording && !isTranscribing"
              type="button"
              @click="sendMessage"
              :disabled="isWaitingResponse"
              class="h-6 w-6 mx-2 flex items-center justify-center rounded-full bg-[#B22E00] hover:bg-[#8E2400] text-white text-xl shadow-md transition
                     disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-[#B22E00]"
            >
              ↑
            </button>
          </template>
        </div>
      </div>
    </div>

    <DishModal
      :show="showDishModal"
      :dish="selectedDish"
      @close="showDishModal = false"
    />
  </div>
</template>

<script setup>
import { ref, nextTick, onUnmounted } from 'vue'
import axios from 'axios'
import { useChatStore } from '../stores/chat'
import DishModal from '../components/DishModal.vue'
import { toWebP } from '../utils/imageUtils'

const chatStore = useChatStore()
const { messages } = chatStore

const input = ref('')
const language = ref('zh') // 可用於切換對話語言(提示詞調整)
const chatContainer = ref(null)
const showDishModal = ref(false)
const selectedDish = ref(null)
const isWaitingResponse = ref(false) // 等待 AI 回覆中

// 快速回覆選項資料
const quickReplies = ref([
  { category: '預算', text: '1000元的套餐', icon: '💰' },
  { category: '預算', text: '2000元內套餐', icon: '💰' },
  { category: '推薦', text: '推薦雞肉料理', icon: '⭐' },
  { category: '推薦', text: '推薦鰻魚料理', icon: '🔥' },
  { category: '類型', text: '來碗湯', icon: '🍲' },
  { category: '類型', text: '我要吃主食', icon: '🍚' },
  { category: '類型', text: '給我小菜', icon: '🥗' },
  { category: '口味', text: '我要辣的', icon: '🌶️' },
  { category: '口味', text: '清淡口味', icon: '🍃' }
])

// 錄音相關
const isRecording = ref(false) // 是否錄音中
const isTranscribing = ref(false)
const mediaRecorder = ref(null) // MediaRecorder 實體
const audioChunks = ref([]) // 暫存錄音片段
const waveform = ref(new Array(50).fill(4)) // 波形數據
const maxHeight = 12
let audioContext, analyser, dataArray, source, animationId
let abortController = null
let startTime = 0 // 錄音秒數(開始時間)

function openDish(item) {
  selectedDish.value = item
  showDishModal.value = true
}

/**
 * 快速選取按鈕：將選取的文字填入輸入框
 * @param {string} text - 要填入的文字
 */
function selectQuickReply(text) {
  input.value = text
  // 聚焦到輸入框，讓使用者可以立即編輯
  nextTick(() => {
    const textarea = document.querySelector('textarea')
    if (textarea) {
      textarea.focus()
      // 將游標移到文字末端
      textarea.setSelectionRange(text.length, text.length)
    }
  })
}

async function sendMessage() {
  if (!input.value.trim() || isWaitingResponse.value) return

  const text = input.value
  input.value = ''

  // 添加使用者訊息
  chatStore.addMessage('user', text)
  await scrollToBottom()

  // 添加載入中的 AI 訊息
  isWaitingResponse.value = true
  const loadingMessageIndex = messages.length
  chatStore.addMessage('assistant', '', [], true) // isLoading = true
  await scrollToBottom()

  try {
    const res = await axios.post('/api/chat', {
      message: text,
      sessionId: 'jinxia-user'
    })
    const { message, recommendations } = res.data

    // 更新載入訊息為真實回覆
    messages[loadingMessageIndex].content = message
    messages[loadingMessageIndex].recommendations = recommendations
    messages[loadingMessageIndex].isLoading = false
  } catch (error) {
    // 更新載入訊息為錯誤訊息
    messages[loadingMessageIndex].content = '❌ 發生錯誤，請稍後再試。'
    messages[loadingMessageIndex].isLoading = false
  } finally {
    isWaitingResponse.value = false
  }

  await scrollToBottom()
}

async function scrollToBottom() {
  await nextTick()
  const el = chatContainer.value
  if (!el) return
  const bottomOffset = document.querySelector('form')?.offsetHeight || 0
  setTimeout(() => {
    el.scrollTo({
      top: el.scrollHeight + bottomOffset,
      behavior: 'smooth'
    })
  }, 100)
}

function resetChat() {
  chatStore.resetAndReload()
}

/** 將秒數格式化為 mm:ss */
function formatTime(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0')
  const s = Math.floor(seconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

/** 開始或停止錄音 */
async function toggleRecording() {
  if (isRecording.value) {
    cancelRecording()
    return
  }
  try {
    // 取得麥克風
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : 'audio/webm'
    audioChunks.value = []
    mediaRecorder.value = new MediaRecorder(stream, { mimeType })
    mediaRecorder.value.ondataavailable = e => audioChunks.value.push(e.data)
    mediaRecorder.value.start()

    startWaveform(stream)
    startTimer()

    isRecording.value = true
  } catch (e) {
    alert('⚠️ 無法存取麥克風，請確認權限設定')
  }
}

/** 啟動錄音計時 */
function startTimer() {
  startTime = Date.now()
}

/** 停止計時 */
function stopTimer() {
  startTime = 0
}

function getRecordingTime() {
  return (Date.now() - startTime) / 1000
}

/** 取消錄音 */
function cancelRecording() {
  stopStream()
  stopTimer()
  isRecording.value = false
  audioChunks.value = []
}

/** 停止錄音並送出給 Whisper 辨識 */
async function stopRecording() {
  if (!mediaRecorder.value) return
  
  mediaRecorder.value.onstop = async () => {
    stopStream()
    isRecording.value = false
    isTranscribing.value = true

    // 等 200ms 讓資料寫入完成
    await new Promise(r => setTimeout(r, 200))
    
    const blob = new Blob(audioChunks.value, { type: 'audio/webm;codecs=opus' })
    const duration = getRecordingTime();
    if (duration <= 0.5 || blob.size < 2000) { // 小於 2KB 幾乎是空音訊
      console.log('⚠️ 錄音失敗，檔案過短或為空')
      console.log(`${duration}`)
      isTranscribing.value = false
      cancelRecording();
      return
    }

    const formData = new FormData()
    formData.append('file', blob, 'recording.webm')

    abortController = new AbortController() // 建立取消控制器
    try {
      const res = await axios.post('/api/chat/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        signal: abortController.signal
      })
      input.value = res.data.text || ''
      language.value = res.data.language || 'zh'
    } catch (e) {
      if (axios.isCancel(e)) {
        console.log('⚠️ 轉寫已取消')
      } else {
        console.log(e.response)
        console.error(e)
        // alert('⚠️ 語音辨識失敗，請再試一次')
      }
    } finally {
      isTranscribing.value = false
      abortController = null
    }
  }
  mediaRecorder.value.stop()
}

/** 取消轉寫 */
function abortTranscription() {
  if (abortController) {
    console.log('取消轉寫')
    abortController.abort()          // 取消 axios 請求
    abortController = null
    isTranscribing.value = false     // UI 回復初始狀態
  }
}

/** 啟動波形動畫 */
function startWaveform(stream) {
  audioContext = new AudioContext()
  source = audioContext.createMediaStreamSource(stream)
  analyser = audioContext.createAnalyser()
  analyser.fftSize = 64
  const bufferLength = analyser.frequencyBinCount
  dataArray = new Uint8Array(bufferLength)
  source.connect(analyser)

  const animate = () => {
    analyser.getByteFrequencyData(dataArray)
    const newHeights = Array.from(dataArray.slice(0, waveform.value.length)).map(v => v / 255 * maxHeight)
    waveform.value = newHeights
    animationId = requestAnimationFrame(animate)
  }
  animate()
}

/** 停止所有音源與動畫 */
function stopStream() {
  if (mediaRecorder.value?.state === 'recording') mediaRecorder.value.stop()
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
    waveform.value = new Array(50).fill(maxHeight/2)
  }
  if (audioContext) audioContext.close()
  stopTimer()
}

// 離開頁面時停止錄音
onUnmounted(() => {
  stopStream();
  abortController?.abort();
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s ease;
}
.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 捲軸樣式 */
::-webkit-scrollbar {
  width: 6px;
  height: 4px;
}
::-webkit-scrollbar-thumb {
  background-color: #e3c9a3;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background-color: #cfa46e;
}

/* 快速選取按鈕區域的水平捲軸 */
.overflow-x-auto::-webkit-scrollbar {
  height: 4px;
}
.overflow-x-auto::-webkit-scrollbar-track {
  background: transparent;
}
.overflow-x-auto::-webkit-scrollbar-thumb {
  background-color: #F0D9B5;
  border-radius: 2px;
}
.overflow-x-auto::-webkit-scrollbar-thumb:hover {
  background-color: #e3c9a3;
}

@keyframes spin-slow {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.animate-spin-slow {
  animation: spin-slow 1s linear infinite;
}

/* AI 思考中動畫 - 點點循環 */
.loading-dots {
  display: flex;
  gap: 4px;
  align-items: center;
  height: 20px;
}

.loading-dots span {
  display: inline-block;
  width: 4px;
  height: 4px;
  background-color: #8B5E3C;
  border-radius: 50%;
  animation: wave 1.4s ease-in-out infinite;
}

/* 為每個點設置不同的延遲,創造波浪效果 */
.loading-dots span:nth-child(1) { animation-delay: 0s; }
.loading-dots span:nth-child(2) { animation-delay: 0.1s; }
.loading-dots span:nth-child(3) { animation-delay: 0.2s; }
.loading-dots span:nth-child(4) { animation-delay: 0.3s; }
.loading-dots span:nth-child(5) { animation-delay: 0.4s; }
.loading-dots span:nth-child(6) { animation-delay: 0.5s; }
.loading-dots span:nth-child(7) { animation-delay: 0.6s; }
.loading-dots span:nth-child(8) { animation-delay: 0.7s; }
.loading-dots span:nth-child(9) { animation-delay: 0.8s; }

@keyframes wave {
  0%, 60%, 100% {
    transform: translateY(0) scale(1);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-8px) scale(1.3);
    opacity: 1;
  }
}
</style>
