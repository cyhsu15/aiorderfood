import { createRouter, createWebHistory } from 'vue-router'
import MenuView from '../views/MenuView.vue'
import CartView from '../views/CartView.vue'
import RecommendView from '../views/RecommendView.vue'
import ProfileView from '../views/ProfileView.vue'
import AdminMenuView from '../views/AdminMenuView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'menu', component: MenuView },
    { path: '/cart', name: 'cart', component: CartView },
    { path: '/recommend', component: RecommendView },
    { path: '/profile', component: ProfileView },
    { path: '/admin/menu', name: 'admin-menu', component: AdminMenuView }
  ],
})

export default router
