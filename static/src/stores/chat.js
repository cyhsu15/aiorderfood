import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([
    {
      role: 'assistant',
      content: '你好！我是錦霞樓的推薦助理，要幫你找辣的、清淡的，還是招牌菜呢？'
    }
  ])

  function addMessage(role, content, recommendations = [], isLoading = false) {
    messages.value.push({ role, content, recommendations, isLoading })
  }

  function clearChat() {
    messages.value = [
      {
        role: 'assistant',
        content: '你好！我是錦霞樓的推薦助理，要幫你重新推薦餐點嗎？'
      }
    ]
  }

  // ✅ 清空 + 強制刷新
  function resetAndReload() {
    clearChat()
    // 立刻刷新畫面
    window.location.reload()
  }

  return { messages, addMessage, clearChat, resetAndReload }
})
