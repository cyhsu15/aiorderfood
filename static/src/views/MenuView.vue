<template>
  <div class="min-h-screen bg-gray-50 text-gray-800 flex flex-col items-center">

    <div
      class="relative w-full"
    >
      <img
        src="/images/banner.png"
        alt="錦霞樓 Banner"
        class="w-full h-48 sm:h-60 lg:h-72 object-cover"
      />
      <div class="absolute inset-0 bg-black/30 flex items-center justify-center">
        <h1 class="text-white text-3xl sm:text-4xl lg:text-5xl font-bold tracking-wide">
          錦霞樓點餐系統
        </h1>
      </div>
    </div>

    <div class="w-full max-w-md flex flex-col flex-1 bg-white shadow-sm relative">

      <!-- 🧭 分類列 -->
      <nav ref="navRef" class="sticky top-0 bg-white border-b px-3 py-2 z-50">
        <div class="flex items-center justify-between">
          
          <!-- 🔹 左側：可橫向滑動所有分類 -->
          <div
            class="flex flex-nowrap space-x-2 overflow-x-auto scrollbar-hide px-1 w-[calc(100%-2.5rem)]"
            @wheel.prevent="handleWheelScroll"
            @touchstart.stop
            @mousedown.stop
          >
            <template v-if="!showDropdown">
              <button
                v-for="section in filteredSections"
                :key="section.id"
                @click.stop="scrollTo(section.id)"
                data-testid="category-tab"
                class="px-3 py-1 border rounded-full text-sm whitespace-nowrap transition flex-shrink-0"
                :class="activeId === section.id
                  ? 'bg-orange-100 text-orange-600 border-orange-300 font-semibold'
                  : 'bg-gray-50 text-gray-700 border-gray-200 hover:bg-orange-50 hover:text-orange-500'"
              >
                {{ section.title }}
              </button>
            </template>

            <!-- 展開時：顯示文字 -->
            <template v-else>
              <div class="flex-1 text-center font-semibold text-gray-700">
                全部分類
              </div>
            </template>
          </div>

          <!-- 🔹 右側按鈕 -->
          <div class="flex items-center space-x-2 flex-shrink-0">
            <button
              @click.stop="toggleDropdown"
              class="w-7 h-7 flex items-center justify-center rounded-full border border-gray-300 text-gray-600 hover:border-orange-400 hover:text-orange-500"
            >
              <span v-if="!showDropdown">▼</span>
              <span v-else>▲</span>
            </button>
          </div>
        </div>

        <!-- 🔽 下拉分類 -->
        <transition name="fade">
          <div
            v-if="showDropdown"
            ref="dropdownRef"
            class="absolute left-0 right-0 top-full bg-white border-b shadow z-40"
          >
            <div class="grid grid-cols-2 gap-2 p-3">
              <button
                v-for="section in filteredSections"
                :key="section.id"
                @click.stop="scrollTo(section.id)"
                class="py-2 px-3 text-sm rounded-full border border-gray-200 text-gray-700 hover:bg-orange-50 hover:text-orange-600 transition"
              >
                {{ section.title }}
              </button>
            </div>
          </div>
        </transition>
      </nav>

      <!-- 🧾 菜單內容 -->
      <div class="p-4 space-y-10 flex-1 overflow-y-auto">
        <section
          v-for="section in sections"
          :key="section.id"
          :id="section.id"
          class="scroll-mt-24"
        >
          <template v-if="!isBlocked(section.title)">
            <h2 class="text-lg font-bold mb-3 border-l-4 border-orange-500 pl-2">
              {{ section.title }}
            </h2>

            <div class="grid grid-cols-2 gap-4">
              <div
                v-for="item in section.items"
                :key="item.id"
                @click="openDish(item)"
                data-testid="dish-card"
                class="bg-white rounded-xl shadow hover:shadow-lg transition p-3 cursor-pointer"
              >
                <LazyImage
                  :src="item.image_url || '/images/default.png'"
                  :alt="item.name"
                  fallback="/images/default.png"
                  img-class="w-full h-32 object-cover rounded-lg"
                  threshold="100px"
                  data-testid="dish-image"
                />
                <div class="mt-2">
                  <p data-testid="dish-name" class="font-semibold text-gray-900 line-clamp-1">{{ item.name }}</p>
                  <p data-testid="dish-description" class="text-xs text-gray-500 line-clamp-2">{{ item.description }}</p>
                  <p data-testid="dish-price" class="text-sm font-semibold text-orange-600 mt-1">
                    {{ item.price_display }}
                  </p>
                </div>
              </div>
            </div>
          </template>
        </section>
      </div>

      <!-- 🍽 詳情浮窗 -->
      <DishModal
        :show="showDishModal"
        :dish="selectedDish"
        @close="closeDish"
      />

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import axios from 'axios'

import DishModal from '../components/DishModal.vue'
import LazyImage from '../components/LazyImage.vue'
import { toWebP } from '../utils/imageUtils'


const sections = ref([])
const blocked = ['2025年菜','2025年菜桌菜附餐']
const isBlocked = (name) => name && blocked.some(k => String(name).includes(k))
const filteredSections = computed(() => sections.value.filter(s => !isBlocked(s.title)))
const showDropdown = ref(false)
const showDishModal = ref(false)
const selectedDish = ref(null)
const activeId = ref(null)
const navRef = ref(null)
const dropdownRef = ref(null)

function toggleDropdown() {
  showDropdown.value = !showDropdown.value
}

function handleOutsideClick(e) {
  if (
    showDropdown.value &&
    dropdownRef.value &&
    !dropdownRef.value.contains(e.target) &&
    !navRef.value.contains(e.target)
  ) {
    showDropdown.value = false
  }
}

function scrollTo(id) {
  showDropdown.value = false
  nextTick(() => {
    const target = document.getElementById(id)
    if (target) {
      const y = target.getBoundingClientRect().top + window.scrollY - 70
      window.scrollTo({ top: y, behavior: 'smooth' })
      activeId.value = id
    }
  })
}

function openDish(item) {
  selectedDish.value = item
  showDishModal.value = true
}

function closeDish() {
  showDishModal.value = false
  document.body.style.overflow = ''
}

async function loadMenu() {
  const res = await axios.get('/api/menu')

  // console.log('📦 API Response:', JSON.stringify(res.data, null, 2))

  sections.value = res.data.map(cat => ({
    id: `section-${cat.category_id}`,
    title: cat.category_name,
    items: cat.dishes.map(dish => {
      const prices = dish.prices || []
      let displayPrice = ''

      if (!prices.length) {
        // ✅ 沒價格資料（可能是時價）
        displayPrice = '時價'
      } 
      else if (prices.some(p => (p.label || '').trim() === '時價')) {
        // ✅ 有標註時價
        displayPrice = '時價'
      } 
      else if (prices.some(p => (p.label || '').trim() === '小')) {
        // ✅ 顯示「小」價
        const small = prices.find(p => (p.label || '').trim() === '小')
        displayPrice = small?.price ? `NT$${Number(small.price)}` : '時價'
      } 
      else {
        // ✅ 沒有標籤的（單一價格）
        const first = prices[0]
        displayPrice = first?.price ? `NT$${Number(first.price)}` : '時價'
      }

      return {
        id: dish.dish_id,
        name: dish.name,
        description: dish.description,
        is_set: !!dish.is_set,
        set_items: (dish.set_items || []).map(si => ({ item_id: si.item_id, name: si.name, quantity: si.quantity })) ,
        prices, // ✅ 加上這行！
        price_display: displayPrice,
        price: Number(prices[0]?.price) || 0,
        image_url: toWebP(dish.image_url || `/images/dish/${dish.dish_id}.png`)
      }
    })
  }))
}

function handleWheelScroll(event) {
  const el = event.currentTarget
  if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
    el.scrollLeft += event.deltaY
  }
}

onMounted(() => {
  loadMenu()
  document.addEventListener('click', handleOutsideClick)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', handleOutsideClick)
})
</script>

<style>
@keyframes slideUp {
  from {
    transform: translateY(100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
.animate-slideUp {
  animation: slideUp 0.3s ease-out;
}

/* 隱藏彈窗滾動條 */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-thumb {
  background-color: #ccc;
  border-radius: 3px;
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.9); }
  to { opacity: 1; transform: scale(1); }
}
.animate-fadeIn {
  animation: fadeIn 0.2s ease-out;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
