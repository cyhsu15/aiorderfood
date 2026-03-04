import { createApp } from 'vue'
import { createPinia } from 'pinia'
import axios from 'axios'
import App from './App.vue'
import router from './router'
import { useSessionStore } from './stores/session'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

const sessionStore = useSessionStore(pinia)

axios.interceptors.request.use((config) => {
  if (typeof window === 'undefined') {
    return config
  }

  if (!sessionStore.initialized) {
    sessionStore.initialize()
  }

  const sessionId = sessionStore.sessionId
  const tableId = sessionStore.tableId

  if (!sessionId && !tableId) {
    return config
  }

  let url
  try {
    const base = config.baseURL || window.location.origin
    url = new URL(config.url, base)
  } catch {
    return config
  }

  if (!url.pathname.startsWith('/api')) {
    return config
  }

  // 發送請求時補上 shared session 參數
  if (sessionId && !url.searchParams.has('sessionid')) {
    url.searchParams.set('sessionid', sessionId)
  }
  if (tableId && !url.searchParams.has('tableid')) {
    url.searchParams.set('tableid', tableId)
  }

  if (config.baseURL) {
    config.url = url.toString()
  } else {
    config.url = url.pathname + url.search + url.hash
  }

  return config
})

app.mount('#app')
