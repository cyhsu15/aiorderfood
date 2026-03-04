<template>
  <div class="min-h-screen flex flex-col items-center text-[#2B1B0F]">
    <div
      data-testid="cart-panel"
      class="w-full max-w-md bg-[#FFFDF8] shadow-lg rounded-t-2xl mt-4 mb-24 p-5 border-t-4 border-[#B22E00]"
    >
      <div class="flex items-center justify-between mb-5">
        <h2 class="font-bold text-lg text-[#B22E00]">
          你的餐點
        </h2>
        <button
          @click="refreshCartManually"
          :disabled="isRefreshing"
          class="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg border transition"
          :class="isRefreshing
            ? 'bg-gray-100 text-gray-400 border-gray-300 cursor-not-allowed'
            : 'bg-white text-[#B22E00] border-[#B22E00]/40 hover:bg-[#B22E00] hover:text-white'"
          title="重新整理購物車"
        >
          <svg
            class="w-4 h-4 transition-transform"
            :class="{ 'animate-spin': isRefreshing }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span v-if="!isRefreshing">重新整理</span>
          <span v-else>載入中...</span>
        </button>
      </div>

      <transition-group
        name="fade-slide"
        tag="div"
        class="space-y-3"
        :css="true"
        move-class="none"
      >
        <div
          v-for="item in cart"
          :key="item.uuid"
          @click="openDish(item)"
          data-testid="cart-item"
          class="flex items-start justify-between border border-[#F0D9B5] rounded-xl p-3 shadow-sm bg-[#F5E1C0]/40 transition"
        >
          <div class="flex items-start space-x-3 flex-1">
            <div class="w-24 h-24 flex-shrink-0">
              <img
                :src="toWebP(item.image_url || '/images/default.png')"
                alt=""
                class="w-full h-full object-cover rounded-xl shadow"
                @error="handleImageError"
              />
            </div>

            <div class="flex flex-col flex-1">
              <p data-testid="cart-item-name" class="font-semibold text-base sm:text-lg line-clamp-2 text-[#2B1B0F]">
                {{ item.name }}
              </p>

              <p
                v-if="item.size && item.size !== '市價'"
                class="text-sm text-[#8B5E3C] mt-1"
              >
                份量：{{ item.size }}
              </p>

              <p v-if="item.note" class="text-sm text-[#8B5E3C] mt-1">
                備註：{{ item.note }}
              </p>
            </div>
          </div>

          <div class="flex flex-col items-end space-y-2">
            <div class="flex items-center space-x-2">
              <button
                @click.stop="changeQty(item, -1)"
                data-testid="decrease-quantity-btn"
                class="w-7 h-7 border border-[#B22E00]/40 rounded-full text-[#B22E00] text-base leading-none hover:bg-[#B22E00] hover:text-white transition"
              >-</button>
              <span data-testid="cart-item-quantity" class="text-base font-medium text-[#2B1B0F]">{{ item.qty }}</span>
              <button
                @click.stop="changeQty(item, 1)"
                data-testid="increase-quantity-btn"
                class="w-7 h-7 border border-[#B22E00]/40 rounded-full text-[#B22E00] text-base leading-none hover:bg-[#B22E00] hover:text-white transition"
              >+</button>
            </div>

            <div class="flex items-center space-x-2">
              <p data-testid="cart-item-price" class="text-[#B22E00] font-bold text-base">
                NT${{ (item.price * item.qty).toFixed(0) }}
              </p>
              <button
                @click.stop="removeItem(item)"
                data-testid="remove-item-btn"
                class="text-[#8B5E3C] hover:text-[#B22E00] text-xl transition-transform hover:scale-110"
                title="移除"
              >
                ✕
              </button>
            </div>
          </div>
        </div>

        <p
          v-if="!cart.length"
          key="empty"
          data-testid="empty-cart-message"
          class="text-center text-[#8B5E3C] mt-10 italic"
        >
          購物車是空的，趕快挑幾道好料吧！
        </p>
      </transition-group>

      <div v-if="cart.length" class="mt-6">
        <h3 class="font-semibold text-base mb-2 text-[#8B5E3C]">備註</h3>
        <textarea
          v-model="globalNote"
          placeholder="例如：不要辣、飲料去冰、餐具改成木筷"
          class="w-full border border-[#F0D9B5] rounded-lg p-2 text-sm focus:ring-2 focus:ring-[#B22E00]/50 resize-none bg-[#FFFDF8] text-[#2B1B0F]"
          rows="2"
        ></textarea>
      </div>

      <div class="mt-6">
        <button
          v-if="cart.length"
          @click="placeOrder"
          :disabled="isSubmitting"
          data-testid="checkout-btn"
          class="w-full bg-[#B22E00] hover:bg-[#8E2400] text-white py-3 rounded-xl font-semibold transition shadow-md"
          :class="{ 'opacity-70 cursor-not-allowed': isSubmitting }"
        >
          送出訂單 (<span data-testid="total-amount">NT${{ totalPrice.toFixed(0) }}</span>)
        </button>
        <button
          v-else
          class="w-full bg-[#E6D8C2] text-[#8B5E3C] py-3 rounded-xl font-semibold cursor-not-allowed"
          disabled
        >
          還沒有選擇餐點
        </button>
      </div>
    </div>
  </div>

  <DishModal
    :show="showDishModal"
    :dish="selectedDish"
    @close="showDishModal = false"
  />
</template>

<script setup>
import axios from 'axios'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useCartStore } from '../stores/cart'
import DishModal from '../components/DishModal.vue'
import { ref, computed, onMounted } from 'vue'
import { toWebP } from '../utils/imageUtils'

const showDishModal = ref(false)
const selectedDish = ref(null)
const isSubmitting = ref(false)
const isRefreshing = ref(false)

const cartStore = useCartStore()
const { cart, totalPrice, note } = storeToRefs(cartStore)
const router = useRouter()

const globalNote = computed({
  get: () => note.value,
  set: value => cartStore.setNote(value)
})

onMounted(() => {
  cartStore.ensureLoaded()
})

// ==================== 購物車操作函數 ====================

/**
 * 手動重新整理購物車
 */
async function refreshCartManually() {
  if (isRefreshing.value) return

  isRefreshing.value = true
  console.log('[CartView] 手動重新整理購物車...')

  try {
    await cartStore.refreshCart()
    console.log('[CartView] 購物車重新整理完成')

    // 顯示成功通知
    cartStore.showNotification('success', '✅ 購物車已更新', 2000)
  } catch (err) {
    console.error('[CartView] 重新整理購物車失敗:', err)
    cartStore.showNotification('error', '❌ 更新失敗，請稍後再試', 3000)
  } finally {
    isRefreshing.value = false
  }
}

function handleImageError(e) {
  // 第一次錯誤：嘗試原始格式
  if (e.target.src.endsWith('.webp')) {
    e.target.src = e.target.src.replace(/\.webp$/, '.png')
    return
  }

  // 第二次錯誤：使用 fallback
  if (e.target.src !== '/images/default.png') {
    e.target.src = '/images/default.png'
  }
}

function openDish(item) {
  selectedDish.value = { ...item }
  showDishModal.value = true
}

function changeQty(item, delta) {
  cartStore.updateQty(item.id, delta, item.size, item.note, item.price)
}

function removeItem(item) {
  cartStore.removeItem(item.id, item.size, item.note, item.price)
}

async function placeOrder() {
  if (!cart.value.length || isSubmitting.value) return
  isSubmitting.value = true
  try {
    await cartStore.ensureLoaded()
    const res = await axios.post('/api/orders', {
      note: globalNote.value || null
    })
    const orderId = res.data?.order_id
    alert(`已送出訂單${orderId ? `（編號: ${orderId}）` : ''}！`)
    await cartStore.refreshCart()
    router.push('/')
  } catch (err) {
    const errorDetail = err?.response?.data?.detail

    if (errorDetail === 'cart_empty') {
      alert('購物車已為空，請重新選購。')
    } else if (errorDetail === 'cannot_submit_empty_cart_after_order') {
      // 新的錯誤碼：已有訂單後不允許送出空購物車
      alert('此桌已送出訂單，無法送出空白訂單。\n請先新增商品到購物車。')

      // 重新載入購物車以確保同步
      await cartStore.refreshCart()
    } else {
      console.error('下單失敗', err)
      alert('送出訂單失敗，請稍後再試。')
    }
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.35s ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
.none {
  transition: none !important;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
