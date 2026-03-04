import axios from 'axios'
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useCartStore = defineStore('cart', () => {
  const cart = ref([])
  const note = ref('')
  const isLoaded = ref(false)
  const version = ref(null) // 版本號，用於樂觀鎖定
  const conflictNotification = ref(null) // 衝突通知訊息

  // SSE 連線狀態
  const sseConnection = ref(null)
  const sseConnected = ref(false)
  const sseReconnectAttempts = ref(0)

  let loadPromise = null
  let syncTimer = null
  let sseReconnectTimer = null

  async function fetchCartFromServer() {
    const res = await axios.get('/api/cart')
    cart.value = Array.isArray(res.data?.items) ? res.data.items : []
    note.value = res.data?.note || ''
    version.value = res.data?.version || null // 儲存版本號
  }

  async function ensureLoaded() {
    if (isLoaded.value) return
    if (!loadPromise) {
      loadPromise = fetchCartFromServer()
        .catch(err => {
          console.error('無法讀取購物車', err)
        })
        .finally(() => {
          isLoaded.value = true
        })
    }
    await loadPromise
  }

  async function refreshCart() {
    try {
      await fetchCartFromServer()
    } catch (err) {
      console.error('重新載入購物車失敗', err)
    } finally {
      isLoaded.value = true
    }
  }

  function scheduleSync() {
    if (syncTimer) clearTimeout(syncTimer)
    syncTimer = setTimeout(() => {
      syncTimer = null
      syncCart()
    }, 250)
  }

  async function syncCart(retryOnConflict = true) {
    console.log('[Cart] 開始同步購物車到伺服器...')
    console.log('[Cart] 購物車商品數:', cart.value.length)
    console.log('[Cart] 當前版本號:', version.value)

    try {
      const payload = {
        items: cart.value,
        note: note.value
      }

      // 如果有版本號，加入 payload 以啟用樂觀鎖定
      if (version.value !== null) {
        payload.version = version.value
      }

      console.log('[Cart] 發送 PUT /api/cart 請求...')
      const res = await axios.put('/api/cart', payload)
      console.log('[Cart] 伺服器回應:', res.data)

      // 更新版本號
      if (res.data?.version) {
        console.log('[Cart] 版本號更新:', version.value, '->', res.data.version)
        version.value = res.data.version
      }

      console.log('[Cart] ✅ 購物車同步成功')
      return { success: true }
    } catch (err) {
      // 處理版本衝突 (409 Conflict)
      if (err.response?.status === 409 && retryOnConflict) {
        console.warn('[Cart] ⚠️ 購物車版本衝突，正在重新載入並重試...')
        return await handleConflictAndRetry()
      }

      console.error('[Cart] ❌ 同步購物車失敗:', err)
      return { success: false, error: err }
    }
  }

  async function handleConflictAndRetry() {
    try {
      // 1. 保存當前要新增的項目（尚未同步的變更）
      const pendingItems = [...cart.value]
      const pendingNote = note.value

      // 2. 重新載入伺服器端的購物車
      await fetchCartFromServer()

      // 3. 設置通知訊息（UI 可以監聽此狀態顯示提示）
      conflictNotification.value = {
        type: 'info',
        message: '購物車已被其他分頁更新，正在自動合併您的變更...',
        timestamp: Date.now()
      }
      console.info('購物車已被更新，正在合併您的變更...')

      // 4. 合併邏輯：將待處理的項目加入已重新載入的購物車
      const serverItems = [...cart.value]
      const mergedItems = mergeCartItems(serverItems, pendingItems)

      // 計算新增的項目數量（用於通知）
      const newItemsCount = mergedItems.length - serverItems.length

      cart.value = mergedItems
      note.value = pendingNote || note.value

      // 5. 重試同步（不再自動重試以避免無限循環）
      const result = await syncCart(false)

      // 6. 更新成功通知
      if (result.success) {
        conflictNotification.value = {
          type: 'success',
          message: newItemsCount > 0
            ? `已成功合併！新增了 ${newItemsCount} 個項目到購物車`
            : '購物車已更新並同步',
          timestamp: Date.now()
        }

        // 3 秒後清除通知
        setTimeout(() => {
          conflictNotification.value = null
        }, 3000)
      }

      return result
    } catch (err) {
      console.error('衝突處理失敗', err)
      conflictNotification.value = {
        type: 'error',
        message: '購物車更新失敗，請手動重新整理頁面',
        timestamp: Date.now()
      }
      return { success: false, error: err }
    }
  }

  function clearNotification() {
    conflictNotification.value = null
  }

  function mergeCartItems(serverItems, pendingItems) {
    // 建立伺服器項目的映射表（以 uuid 為鍵）
    const serverMap = new Map()
    serverItems.forEach(item => {
      if (item.uuid) {
        serverMap.set(item.uuid, item)
      }
    })

    // 合併邏輯
    const merged = [...serverItems]

    pendingItems.forEach(pendingItem => {
      if (pendingItem.uuid && serverMap.has(pendingItem.uuid)) {
        // UUID 相同：更新數量（取較大值或相加，依需求調整）
        const serverItem = serverMap.get(pendingItem.uuid)
        serverItem.qty = Math.max(serverItem.qty, pendingItem.qty)
      } else {
        // 新項目：檢查是否已存在相同的商品（id, size, note, price）
        const existingIndex = merged.findIndex(item =>
          item.id === pendingItem.id &&
          item.size === pendingItem.size &&
          item.note === pendingItem.note &&
          item.price === pendingItem.price
        )

        if (existingIndex >= 0) {
          // 存在相同商品：增加數量
          merged[existingIndex].qty += pendingItem.qty
        } else {
          // 全新項目：加入購物車
          merged.push({ ...pendingItem })
        }
      }
    })

    return merged
  }

  async function addItem(item) {
    console.log('[Cart] 加入商品:', item)

    const existing = cart.value.find(p =>
      p.id === item.id &&
      p.size === item.size &&
      p.note === item.note &&
      p.price === item.price
    )

    if (existing) {
      console.log('[Cart] 商品已存在，增加數量:', existing.qty, '->', existing.qty + item.qty)
      existing.qty += item.qty
    } else {
      const next = { ...item }
      if (!next.uuid) {
        next.uuid = (typeof crypto !== 'undefined' && crypto.randomUUID)
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random()}`
      }
      console.log('[Cart] 新增商品到購物車:', next)
      cart.value.push(next)
    }

    console.log('[Cart] 當前購物車商品數:', cart.value.length)

    // 立即同步並等待結果
    scheduleSync()

    // 可選：返回同步結果供 UI 顯示通知
    return new Promise((resolve) => {
      // 等待 scheduleSync 的延遲後檢查
      setTimeout(async () => {
        resolve({ success: true })
      }, 300)
    })
  }

  function updateQty(id, delta, size, itemNote, price) {
    const target = cart.value.find(i =>
      i.id === id &&
      i.size === size &&
      i.note === itemNote &&
      i.price === price
    )
    if (!target) return
    target.qty = Math.max(1, target.qty + delta)
    scheduleSync()
  }

  function removeItem(id, size, itemNote, price) {
    cart.value = cart.value.filter(i =>
      !(i.id === id && i.size === size && i.note === itemNote && i.price === price)
    )
    scheduleSync()
  }

  function clearCart() {
    cart.value = []
    note.value = ''
    version.value = null
    scheduleSync()
  }

  function setNote(value) {
    note.value = value || ''
    scheduleSync()
  }

  const totalPrice = computed(() =>
    cart.value.reduce((sum, i) => sum + i.price * i.qty, 0)
  )

  const itemCount = computed(() =>
    cart.value.reduce((sum, i) => sum + i.qty, 0)
  )

  // ==================== SSE 連線管理 ====================

  /**
   * 建立 SSE 連線以接收即時更新
   * @param {string} sessionId - Session UUID
   */
  function connectSSE(sessionId) {
    if (!sessionId) {
      console.warn('[Cart SSE] No sessionId provided, skipping SSE connection')
      return
    }

    // 如果已有連線，先關閉
    if (sseConnection.value) {
      disconnectSSE()
    }

    try {
      const sseUrl = `/api/sse/cart/${sessionId}`
      console.log(`[Cart SSE] Connecting to ${sseUrl}...`)

      const eventSource = new EventSource(sseUrl)
      sseConnection.value = eventSource

      // 【DEBUG】捕獲所有 SSE 訊息（包括自定義事件）
      eventSource.onmessage = (e) => {
        console.log('[Cart SSE] 📨 收到通用訊息 (onmessage):', e.data)
      }

      // 【DEBUG】監聽所有事件（使用 Proxy 或直接監聽 open）
      eventSource.onopen = () => {
        console.log('[Cart SSE] 🔌 EventSource.onopen - 連線已開啟')
      }

      // 連線成功
      eventSource.addEventListener('connected', (e) => {
        sseConnected.value = true
        sseReconnectAttempts.value = 0
        console.log('[Cart SSE] ✅ Connected successfully:', JSON.parse(e.data))

        showNotification('success', '✅ 即時同步已啟用', 2000)
      })

      // 購物車更新事件
      eventSource.addEventListener('cart_updated', async (e) => {
        console.log('[Cart SSE] 🔔 收到購物車更新事件 (cart_updated listener triggered)')
        console.log('[Cart SSE] 📋 事件原始資料:', e)
        console.log('[Cart SSE] 📋 事件 data:', e.data)

        const data = JSON.parse(e.data)
        console.log('[Cart SSE] 📦 解析後的資料:', data)
        console.log('[Cart SSE] 更新來源:', data.updated_by)
        console.log('[Cart SSE] 桌號:', data.table_id)
        console.log('[Cart SSE] 目前本地購物車商品數:', cart.value.length)

        // 🔧 版本號去重：如果版本號相同，說明是自己剛剛的更新，跳過重複載入
        const serverVersion = data.cart?.version
        if (serverVersion && serverVersion === version.value) {
          console.log('[Cart SSE] ⏭️ 跳過自己的更新（版本號相同:', serverVersion, '）')
          return
        }

        // 重新載入購物車（避免本地變更被覆蓋）
        console.log('[Cart SSE] 正在重新載入購物車...')
        await fetchCartFromServer()
        console.log('[Cart SSE] 重新載入完成，新的商品數:', cart.value.length)

        // 構建通知訊息
        let message = '🔄 購物車已更新'

        // 如果有 changes 欄位，顯示具體新增的菜品
        if (data.changes && data.changes.length > 0) {
          const itemNames = data.changes.map(change => {
            const sizeText = change.size && change.size !== '市價' ? `(${change.size})` : ''
            const qtyText = change.qty > 1 ? ` x${change.qty}` : ''
            return `${change.name}${sizeText}${qtyText}`
          })

          if (itemNames.length === 1) {
            message = `🍽️ 同桌點了 ${itemNames[0]}`
          } else if (itemNames.length === 2) {
            message = `🍽️ 同桌點了 ${itemNames.join('、')}`
          } else {
            // 超過 2 個商品，只顯示前 2 個 + 其他 N 項
            const displayItems = itemNames.slice(0, 2).join('、')
            const remaining = itemNames.length - 2
            message = `🍽️ 同桌點了 ${displayItems} 等 ${itemNames.length} 項`
          }
        }

        showNotification('info', message, 4000)
      })

      // 訂單狀態更新事件
      eventSource.addEventListener('order_status_updated', (e) => {
        const data = JSON.parse(e.data)
        console.log('[Cart SSE] Order status updated:', data)

        const statusText = {
          created: '已建立',
          confirmed: '已確認',
          preparing: '準備中',
          completed: '已完成',
          cancelled: '已取消'
        }[data.status] || data.status

        if (data.action === 'created') {
          showNotification('success', `✅ 訂單 #${data.order_id} 已送出（${statusText}）`, 5000)

          // 重新載入購物車（應該已被清空）
          refreshCart()
        } else {
          showNotification('info', `📋 訂單 #${data.order_id} 狀態更新：${statusText}`, 4000)
        }
      })

      // 版本衝突事件
      eventSource.addEventListener('version_conflict', async (e) => {
        const data = JSON.parse(e.data)
        console.warn('[Cart SSE] Version conflict:', data)

        // 重新載入購物車
        await fetchCartFromServer()

        showNotification('warning', '⚠️ 購物車版本衝突，已重新載入', 3000)
      })

      // 心跳（用於保持連線）
      eventSource.addEventListener('keepalive', (e) => {
        // 收到心跳，確認連線正常（靜默處理，不輸出日誌）
        // console.log('[Cart SSE] 💓 Keepalive received:', e.data)
      })

      // 錯誤處理
      eventSource.onerror = (error) => {
        console.error('[Cart SSE] Connection error:', error)
        sseConnected.value = false

        // EventSource 會自動重連，但我們也加入手動重連邏輯
        scheduleReconnect(sessionId)
      }

    } catch (error) {
      console.error('[Cart SSE] Failed to establish connection:', error)
      scheduleReconnect(sessionId)
    }
  }

  /**
   * 關閉 SSE 連線
   */
  function disconnectSSE() {
    if (sseConnection.value) {
      console.log('[Cart SSE] Disconnecting...')
      sseConnection.value.close()
      sseConnection.value = null
      sseConnected.value = false
    }

    if (sseReconnectTimer) {
      clearTimeout(sseReconnectTimer)
      sseReconnectTimer = null
    }
  }

  /**
   * 排程自動重連
   * @param {string} sessionId - Session UUID
   */
  function scheduleReconnect(sessionId) {
    if (sseReconnectTimer) return // 已在重連中

    const maxAttempts = 10
    if (sseReconnectAttempts.value >= maxAttempts) {
      console.warn('[Cart SSE] Max reconnection attempts reached')
      showNotification('error', '❌ 無法連線到即時同步服務，請重新整理頁面', 5000)
      return
    }

    // 指數退避：3秒、6秒、12秒...（最多 30 秒）
    const delay = Math.min(3000 * Math.pow(2, sseReconnectAttempts.value), 30000)
    sseReconnectAttempts.value++

    console.log(`[Cart SSE] Scheduling reconnect attempt #${sseReconnectAttempts.value} in ${delay}ms`)

    sseReconnectTimer = setTimeout(() => {
      sseReconnectTimer = null
      connectSSE(sessionId)
    }, delay)
  }

  /**
   * 顯示通知訊息
   * @param {string} type - 通知類型 (success, info, warning, error)
   * @param {string} message - 訊息內容
   * @param {number} duration - 顯示時長（毫秒，目前由 GlobalNotification 組件統一處理，此參數保留作為相容性）
   */
  function showNotification(type, message, duration = 3000) {
    conflictNotification.value = {
      type,
      message,
      timestamp: Date.now()
    }
    // 注意: 自動關閉邏輯已移至 GlobalNotification.vue 組件
    // 這樣可以確保在任何頁面都能看到通知並統一處理生命週期
  }

  // ==================== 清理 ====================

  // 當 store 被銷毀時，關閉 SSE 連線
  // 注意：Pinia store 在應用程式生命週期內不會被銷毀，除非明確卸載
  // 這裡主要是為了程式完整性而保留
  if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', () => {
      disconnectSSE()
    })
  }

  // ==================== 導出 ====================

  // 嘗試預先讀取購物車，但不阻塞流程
  ensureLoaded().catch(() => {})

  return {
    // 購物車資料
    cart,
    note,
    version,
    conflictNotification,
    totalPrice,
    itemCount,

    // 購物車操作
    addItem,
    updateQty,
    removeItem,
    clearCart,
    setNote,
    clearNotification,
    ensureLoaded,
    refreshCart,
    syncCart,

    // SSE 連線
    sseConnected,
    connectSSE,
    disconnectSSE,
    showNotification,
  }
})
