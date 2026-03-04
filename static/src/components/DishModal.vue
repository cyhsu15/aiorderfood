<template>
  <div
    v-if="show"
    data-testid="dish-detail-modal"
    class="fixed inset-0 bg-black/40 z-50 flex flex-col justify-end"
  >
    <!-- 點擊背景關閉 -->
    <div class="flex-1" @click="close"></div>

    <div
      class="bg-[#FFFDF8] rounded-t-3xl w-full max-w-md mx-auto shadow-2xl relative animate-slideUp flex flex-col max-h-[85vh] border-t-4"
    >
      <div class="overflow-y-auto px-5 pt-5 pb-5 text-[#2B1B0F]">
        <button
          @click="close"
          data-testid="close-detail-btn"
          class="absolute top-3 right-4 text-[#8B5E3C] text-xl hover:text-[#B22E00] transition"
        >
          ✕
        </button>

        <!-- 圖片 -->
        <img
          :src="dishImageUrl"
          alt=""
          class="w-full h-40 object-cover rounded-xl mb-4 shadow"
          @error="handleImageError"
        />

        <div class="space-y-5">
          <!-- 名稱與價格 -->
          <div class="flex justify-between items-center">
            <div>
              <h3 class="text-lg font-bold text-[#B22E00]">{{ dish?.name }}</h3>
              <p class="text-sm text-[#8B5E3C]">
                {{ dish?.description || '精選料理' }}
              </p>
              <div v-if="dish?.is_set && dish?.set_items?.length" class="mt-2">
                <h4 class="font-semibold mb-1 text-[#8B5E3C]">套餐內容</h4>
                <ul class="text-sm text-[#8B5E3C] list-disc list-inside space-y-0.5">
                  <li v-for="si in dish.set_items" :key="si.item_id">
                    x{{ si.quantity || 1 }} {{ si.name }}
                  </li>
                </ul>
              </div>
            </div>
            <p class="text-[#B22E00] font-extrabold text-xl">
              NT${{ (currentPrice * quantity).toFixed(0) }}
            </p>
          </div>

          <!-- 份量 -->
          <div
            v-if="dish?.prices?.length > 1 || dish?.prices?.some(p => ['小','中','大'].includes(p.label))"
          >
            <h4 class="font-semibold mb-2 text-[#8B5E3C]">份量</h4>
            <div class="space-y-2">
              <label
                v-for="p in dish.prices"
                :key="p.label"
                class="flex items-center justify-between p-2 border rounded-lg cursor-pointer hover:bg-[#F5E1C0]/50 transition"
              >
                <span>{{ p.label }}（NT${{ p.price }}）</span>
                <input
                  type="radio"
                  name="size"
                  :value="p"
                  v-model="selectedSize"
                  class="text-[#B22E00] focus:ring-[#B22E00]"
                />
              </label>
            </div>
          </div>

          <!-- 備註 -->
          <div>
            <h4 class="font-semibold mb-2 text-[#8B5E3C]">備註</h4>
            <textarea
              v-model="note"
              placeholder="例如：少鹽、飯多一點"
              class="w-full border rounded-lg p-2 text-sm focus:ring-2 focus:ring-[#B22E00]/60 resize-none bg-[#FFFDF8]"
              rows="2"
            ></textarea>
          </div>

          <!-- 數量控制 -->
          <div class="flex items-center space-x-3">
            <button
              @click="changeQty(-1)"
              data-testid="modal-decrease-quantity"
              class="w-8 h-8 rounded-full border border-[#B22E00]/40 text-[#B22E00] text-lg leading-none hover:bg-[#B22E00] hover:text-white transition"
            >−</button>
            <span data-testid="modal-quantity" class="font-semibold text-lg">{{ quantity }}</span>
            <button
              @click="changeQty(1)"
              data-testid="modal-increase-quantity"
              class="w-8 h-8 rounded-full border border-[#B22E00]/40 text-[#B22E00] text-lg leading-none hover:bg-[#B22E00] hover:text-white transition"
            >＋</button>
          </div>
        </div>
      </div>

      <!-- 流式底部購物車按鈕 -->
      <div class="p-4 border-t border-[#F0D9B5] bg-[#FFFDF8] rounded-b-3xl">
        <button
          @click="addToCart"
          data-testid="add-to-cart-btn"
          class="w-full bg-[#B22E00] hover:bg-[#8E2400] text-white py-3 rounded-xl font-semibold transition shadow-md"
        >
          加入購物車 (NT${{ (currentPrice * quantity).toFixed(0) }})
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useCartStore } from '../stores/cart'
import { toWebP } from '../utils/imageUtils'

const props = defineProps({
  show: Boolean,
  dish: Object // 可以是新菜品或購物車項目
})
const emit = defineEmits(['close'])

const cartStore = useCartStore()

const quantity = ref(1)
const note = ref('')
const selectedSize = ref(null)
const imageError = ref(false)
const triedOriginal = ref(false)

// 🧠 加入「是否編輯模式」
const isEditing = ref(false)

// 🖼️ 圖片 URL（自動轉換為 WebP）
const dishImageUrl = computed(() => {
  const url = props.dish?.image_url || '/images/default.png'
  return imageError.value ? '/images/default.png' : toWebP(url)
})

// 🖼️ 處理圖片載入錯誤
function handleImageError(e) {
  // 第一次錯誤：嘗試原始格式
  if (!triedOriginal.value && e.target.src.endsWith('.webp')) {
    triedOriginal.value = true
    e.target.src = props.dish?.image_url || '/images/default.png'
    return
  }

  // 第二次錯誤：使用 fallback
  if (e.target.src !== '/images/default.png') {
    imageError.value = true
  }
}

// 🧮 計算目前價格
const currentPrice = computed(() => {
  if (selectedSize.value?.price) return Number(selectedSize.value.price)
  return Number(props.dish?.price || 0)
})

// ✅ 初始化邏輯
watch(
  () => props.dish,
  (dish) => {
    if (dish) {
      document.body.style.overflow = 'hidden'

      // 判斷是否為編輯模式
      isEditing.value = !!dish.qty

      quantity.value = dish.qty || 1
      note.value = dish.note || ''
      // 若菜單有多個份量選項，優先顯示目前 size
      if (dish.size && dish.prices) {
        selectedSize.value = dish.prices.find(p => p.label === dish.size) || dish.prices[0]
      } else {
        selectedSize.value = dish.prices?.[0] || null
      }
    } else {
      document.body.style.overflow = ''
    }
  },
  { immediate: true }
)

function changeQty(delta) {
  quantity.value = Math.max(1, quantity.value + delta)
}

// ✅ 新增或更新購物車
function addToCart() {
  if (!props.dish) return

  const itemData = {
    ...props.dish,
    qty: quantity.value,
    size: selectedSize.value?.label || null,
    note: note.value,
    price: currentPrice.value
  }

  if (isEditing.value) {
    // ✨ 更新既有品項
    const diff = quantity.value - props.dish.qty
    cartStore.updateQty(props.dish.id, diff, props.dish.size, props.dish.note, props.dish.price)

    // 若備註或份量改變，也要覆蓋舊資料
    cartStore.removeItem(props.dish.id, props.dish.size, props.dish.note, props.dish.price)
    cartStore.addItem(itemData)
  } else {
    // 新增新項目
    cartStore.addItem(itemData)
  }

  close()
}

function close() {
  emit('close')
  document.body.style.overflow = ''
}
</script>

