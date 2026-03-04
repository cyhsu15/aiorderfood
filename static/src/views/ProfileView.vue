<template>
  <div class="min-h-screen flex flex-col items-center bg-[#FFFDF8] text-[#2B1B0F]">
    <!-- 🔹 頁面容器 -->
    <div class="w-full max-w-md bg-white rounded-t-2xl shadow-md mt-4 mb-24 p-6 border-t-4 border-[#B22E00]"
    style="
        height: calc(100vh - 70px);   /* 🚀 一開始就固定高度 */
        max-height: calc(100vh - 70px); /* ⚙️ 框高度不超過螢幕（預留底部導覽列） */
      ">

      <!-- 🧧 顧客資料區 -->
      <div class="flex flex-col items-center space-y-3 mb-8">
        <div class="relative">
          <img
            :src="profile.avatar || '/images/logo.png'"
            alt="頭像"
            class="w-24 h-24 rounded-full object-cover border-4 border-[#F0D9B5] shadow-md"
          />
        </div>

        <h2 class="text-xl font-bold text-[#B22E00]">{{ profile.nickname || '訪客' }}</h2>
      </div>

      <!-- 📜 歷史訂單 -->
      <div>
        <h3 class="font-semibold text-lg mb-3 text-[#8B5E3C] border-b border-[#F0D9B5] pb-1">
          歷史訂單
        </h3>

        <div v-if="orders.length" class="space-y-3">
          <div
            v-for="order in orders"
            :key="order.order_id"
            class="border border-[#F0D9B5] rounded-xl p-4 bg-[#FFFDF8] shadow-sm hover:bg-[#F5E1C0]/40 transition"
          >
            <div class="flex justify-between items-center mb-1">
              <p class="font-semibold text-[#2B1B0F]">訂單編號：{{ order.order_id }}</p>
              <span class="text-sm text-[#8B5E3C]">{{ formatDate(order.created_at) }}</span>
            </div>

            <p class="text-sm text-[#8B5E3C]">
              共 {{ order.items.length }} 項餐點　|　總金額 <span class="font-bold text-[#B22E00]">NT${{ order.total_amount.toFixed(0) }}</span>
            </p>

            <ul class="mt-2 text-sm list-disc list-inside text-[#2B1B0F]">
              <li v-for="(dish, i) in order.items" :key="i">{{ dish.name }} × {{ dish.quantity }}</li>
            </ul>
          </div>
        </div>

        <p v-else class="text-center text-[#8B5E3C] italic mt-6">
          尚無歷史訂單 📭
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

// 🧑‍🍳 使用者資料
const profile = ref({
  avatar: '',
  nickname: '',
})

// 📜 歷史訂單資料
const orders = ref([])

// 格式化日期時間（精確到秒）
function formatDate(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`
}

// 載入訂單資料
async function loadOrders() {
  try {
    const res = await axios.get('/api/orders')
    orders.value = res.data
  } catch (err) {
    console.error('無法載入訂單資料:', err)
  }
}

// ✅ 在頁面載入時從 URL 拿 Flask 傳來的資料，並載入訂單
onMounted(async () => {
  const query = route.query

  // Flask 會傳 line_uid、nickname、avatar
  if (query.nickname) {
    profile.value = {
      avatar: query.avatar || '/images/customer-avatar.png',
      nickname: query.nickname || '訪客',
    }

    console.log('✅ 成功取得 Flask 登入資料:', profile.value)

    // （可選）儲存到 localStorage，之後頁面可用
    localStorage.setItem('user', JSON.stringify(profile.value))
  } else {
    // 沒登入過就試著從 localStorage 拿資料
    const saved = localStorage.getItem('user')
    if (saved) profile.value = JSON.parse(saved)
  }

  // 載入訂單資料
  await loadOrders()
})
</script>

<style scoped>
/* 加一點柔和動畫感 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
