/**
 * Session Store - 管理共享桌號的 Session 資訊
 *
 * 負責：
 * - 從 URL 參數讀取 sessionid 和 tableid
 * - 儲存到 localStorage 持久化
 * - 提供給其他組件使用
 */

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useSessionStore = defineStore('session', () => {
  // 狀態
  const sessionId = ref(null)
  const tableId = ref(null)
  const initialized = ref(false)

  // Getters
  const hasSession = computed(() => !!sessionId.value)
  const hasTableId = computed(() => !!tableId.value)
  const isSharedTable = computed(() => hasSession.value && hasTableId.value)

  /**
   * 初始化 Session（從 URL 或 localStorage 讀取）
   */
  function initialize() {
    if (initialized.value) return

    // 1. 嘗試從 URL 讀取
    const urlParams = new URLSearchParams(window.location.search)
    const urlSessionId = urlParams.get('sessionid')
    const urlTableId = urlParams.get('tableid')

    if (urlSessionId) {
      sessionId.value = urlSessionId
      tableId.value = urlTableId || null

      // 儲存到 localStorage
      localStorage.setItem('shared_session_id', urlSessionId)
      if (urlTableId) {
        localStorage.setItem('shared_table_id', urlTableId)
      }

      console.log('[Session] Initialized from URL:', {
        sessionId: urlSessionId,
        tableId: urlTableId,
      })

      // 清除 URL 參數（保持 URL 乾淨）
      const cleanUrl = window.location.origin + window.location.pathname
      window.history.replaceState({}, document.title, cleanUrl)
    } else {
      // 2. 從 localStorage 讀取
      const storedSessionId = localStorage.getItem('shared_session_id')
      const storedTableId = localStorage.getItem('shared_table_id')

      if (storedSessionId) {
        sessionId.value = storedSessionId
        tableId.value = storedTableId || null

        console.log('[Session] Restored from localStorage:', {
          sessionId: storedSessionId,
          tableId: storedTableId,
        })
      }
    }

    initialized.value = true
  }

  /**
   * 設定 Session 資訊
   */
  function setSession(newSessionId, newTableId = null) {
    sessionId.value = newSessionId
    tableId.value = newTableId

    // 持久化到 localStorage
    localStorage.setItem('shared_session_id', newSessionId)
    if (newTableId) {
      localStorage.setItem('shared_table_id', newTableId)
    } else {
      localStorage.removeItem('shared_table_id')
    }

    console.log('[Session] Updated:', { sessionId: newSessionId, tableId: newTableId })
  }

  /**
   * 清除 Session 資訊
   */
  function clearSession() {
    sessionId.value = null
    tableId.value = null

    localStorage.removeItem('shared_session_id')
    localStorage.removeItem('shared_table_id')

    console.log('[Session] Cleared')
  }

  /**
   * 取得顯示用的桌號文字
   */
  function getDisplayText() {
    if (!hasTableId.value) return ''
    return `🍽️ ${tableId.value} 桌`
  }

  return {
    // 狀態
    sessionId,
    tableId,
    initialized,

    // Getters
    hasSession,
    hasTableId,
    isSharedTable,

    // Actions
    initialize,
    setSession,
    clearSession,
    getDisplayText,
  }
})
