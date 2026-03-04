<template>
  <div class="w-full flex justify-center fixed bottom-0 left-0 z-40 bg-gray-50 border-t">
    <nav class="w-full max-w-md flex justify-around py-2 text-gray-600 bg-white">

      <router-link
        :to="getRouteWithQuery('/recommend')"
        class="flex flex-col items-center text-sm hover:text-orange-500"
        :class="{ 'text-orange-500 font-semibold': $route.path === '/recommend' }"
      >
        <span>🌟</span>
        <span>推薦</span>
      </router-link>

      <router-link
        :to="getRouteWithQuery('/')"
        class="flex flex-col items-center text-sm hover:text-orange-500"
        :class="{ 'text-orange-500 font-semibold': $route.path === '/' }"
      >
        <span>📋</span>
        <span>菜單</span>
      </router-link>

      <router-link
        :to="getRouteWithQuery('/cart')"
        data-testid="cart-icon"
        class="relative flex flex-col items-center text-sm hover:text-orange-500"
        :class="{ 'text-orange-500 font-semibold': $route.path === '/cart' }"
      >
        <span>🛒</span>
        <span>購物車</span>
        <span
          v-if="cartStore.itemCount > 0"
          data-testid="cart-badge"
          class="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center"
        >
          {{ cartStore.itemCount > 99 ? '99+' : cartStore.itemCount }}
        </span>
      </router-link>

      <router-link
        :to="getRouteWithQuery('/profile')"
        class="flex flex-col items-center text-sm hover:text-orange-500"
        :class="{ 'text-orange-500 font-semibold': $route.path === '/profile' }"
      >
        <span>👤</span>
        <span>我的</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
import { useCartStore } from '../stores/cart'
import { useSessionStore } from '../stores/session'

const route = useRoute()
const cartStore = useCartStore()
const sessionStore = useSessionStore()

/**
 * 取得包含當前 query parameters 的路由物件
 * 保留 sessionid 和 tableid（如果存在）
 */
function getRouteWithQuery(path) {
  const query = {}

  // 保留 sessionid 和 tableid
  if (sessionStore.sessionId) {
    query.sessionid = sessionStore.sessionId
  }
  if (sessionStore.tableId) {
    query.tableid = sessionStore.tableId
  }

  // 如果沒有任何 query，返回純路徑字串
  if (Object.keys(query).length === 0) {
    return path
  }

  // 返回包含 query 的路由物件
  return {
    path,
    query
  }
}
</script>

<style scoped>
/* 購物車圖示位置調整（為徽章留空間） */
.router-link-active {
  position: relative;
}
</style>
