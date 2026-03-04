<template>
  <div class="min-h-screen bg-gray-50 text-gray-800 p-4">
    <h1 class="text-2xl font-semibold mb-4">菜單管理</h1>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- Categories -->
      <div class="bg-white rounded shadow p-4">
        <div class="flex items-center justify-between mb-3">
          <h2 class="font-semibold">類別</h2>
          <button @click="openNewCategory" class="px-2 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">新增</button>
        </div>
        <ul class="divide-y">
          <li v-for="c in categories" :key="c.category_id" class="py-2 flex items-center justify-between">
            <button class="text-left flex-1" @click="selectCategory(c)">
              <span :class="activeCategory?.category_id === c.category_id ? 'font-semibold text-blue-600' : ''">
                {{ c.name_zh }}
              </span>
            </button>
            <div class="space-x-2">
              <button class="text-sm text-gray-600 hover:text-blue-600" @click.stop="editCategory(c)">編輯</button>
              <button class="text-sm text-red-600 hover:underline" @click.stop="removeCategory(c)">刪除</button>
            </div>
          </li>
        </ul>
      </div>

      <!-- Dishes -->
      <div class="md:col-span-2 bg-white rounded shadow p-4">
        <div class="flex items-center justify-between mb-3">
          <h2 class="font-semibold">菜色<span v-if="activeCategory">（{{ activeCategory.name_zh }}）</span></h2>
          <button @click="openNewDish" :disabled="!activeCategory" class="px-2 py-1 text-sm rounded text-white" :class="activeCategory ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-gray-400 cursor-not-allowed'">新增</button>
        </div>
        <div v-if="!activeCategory" class="text-gray-500">請先選擇類別。</div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="text-left border-b">
              <th class="py-2 pr-2">名稱</th>
              <th class="py-2 pr-2">售價</th>
              <th class="py-2 pr-2">排序</th>
              <th class="py-2">動作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in dishes" :key="d.dish_id" class="border-b">
              <td class="py-2 pr-2">{{ d.name_zh }}</td>
              <td class="py-2 pr-2">{{ firstPrice(d) }}</td>
              <td class="py-2 pr-2">{{ d.sort_order }}</td>
              <td class="py-2 space-x-2">
                <button class="text-blue-600" @click="editDish(d)">編輯</button>
                <button class="text-red-600" @click="removeDish(d)">刪除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Category Modal -->
    <div v-if="showCategoryModal" class="fixed inset-0 bg-black/40 flex items-center justify-center">
      <div class="bg-white w-full max-w-sm rounded shadow p-4">
        <h3 class="font-semibold mb-3">{{ categoryForm.id ? '編輯類別' : '新增類別' }}</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-sm text-gray-600 mb-1">中文名稱</label>
            <input v-model="categoryForm.name_zh" class="w-full border rounded px-2 py-1" />
          </div>
          <div>
            <label class="block text-sm text-gray-600 mb-1">英文名稱</label>
            <input v-model="categoryForm.name_en" class="w-full border rounded px-2 py-1" />
          </div>
          <div class="flex justify-end space-x-2">
            <button class="px-3 py-1" @click="closeCategoryModal">取消</button>
            <button class="px-3 py-1 bg-blue-600 text-white rounded" @click="saveCategory">儲存</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Dish Modal -->
    <div v-if="showDishModal" class="fixed inset-0 bg-black/40 flex items-center justify-center">
      <div class="bg-white w-full max-w-lg rounded shadow p-4">
        <h3 class="font-semibold mb-3">{{ dishForm.id ? '編輯菜色' : '新增菜色' }}</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label class="block text-sm text-gray-600 mb-1">菜名</label>
            <input v-model="dishForm.name_zh" class="w-full border rounded px-2 py-1" />
          </div>
          <div>
            <label class="block text-sm text-gray-600 mb-1">排序</label>
            <input type="number" v-model.number="dishForm.sort_order" class="w-full border rounded px-2 py-1" />
          </div>
          <div class="flex items-center space-x-2">
            <input id="is_set" type="checkbox" v-model="dishForm.is_set" />
            <label for="is_set" class="text-sm text-gray-700">套餐</label>
          </div>
        </div>
        <div class="mt-3">
          <div class="flex items-center justify-between mb-1">
            <span class="text-sm text-gray-600">價格</span>
            <button class="text-sm text-emerald-700" @click="addPrice">新增價格</button>
          </div>
          <div v-for="(p, idx) in dishForm.prices" :key="idx" class="flex items-center space-x-2 mb-2">
            <input v-model="p.label" placeholder="標籤(可空)" class="border rounded px-2 py-1 flex-1" />
            <input type="number" step="0.01" v-model.number="p.price" placeholder="金額" class="border rounded px-2 py-1 w-40" />
            <button class="text-red-600" @click="dishForm.prices.splice(idx,1)">移除</button>
          </div>
        </div>
        <div class="flex justify-end space-x-2 mt-4">
          <button class="px-3 py-1" @click="closeDishModal">取消</button>
          <button class="px-3 py-1 bg-emerald-600 text-white rounded" @click="saveDish">儲存</button>
        </div>
      </div>
    </div>
  </div>
  
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'

const categories = ref([])
const activeCategory = ref(null)
const dishes = ref([])

const showCategoryModal = ref(false)
const categoryForm = ref({ id: null, name_zh: '', name_en: '' })

const showDishModal = ref(false)
const dishForm = ref({ id: null, name_zh: '', is_set: false, sort_order: 0, prices: [] })

const firstPrice = (d) => {
  const p = (d.prices && d.prices[0]) || null
  if (!p) return '—'
  return p.price != null ? `NT$${Number(p.price)}` : '—'
}

function selectCategory(c) {
  activeCategory.value = c
  loadDishes()
}

async function loadCategories() {
  const res = await axios.get('/api/admin/categories')
  categories.value = res.data
  if (!activeCategory.value && categories.value.length) {
    activeCategory.value = categories.value[0]
  }
}

async function loadDishes() {
  if (!activeCategory.value) { dishes.value = []; return }
  const res = await axios.get('/api/menu')
  const cat = res.data.find(c => c.category_id === activeCategory.value.category_id)
  dishes.value = (cat?.dishes || []).map(d => ({
    dish_id: d.dish_id,
    name_zh: d.name,
    is_set: !!d.is_set,
    sort_order: 0, // 後端未含此欄位於查詢結果，維持 0 顯示
    prices: d.prices || []
  }))
}

function openNewCategory() {
  categoryForm.value = { id: null, name_zh: '', name_en: '' }
  showCategoryModal.value = true
}
function editCategory(c) {
  categoryForm.value = { id: c.category_id, name_zh: c.name_zh || '', name_en: c.name_en || '' }
  showCategoryModal.value = true
}
function closeCategoryModal() { showCategoryModal.value = false }

async function saveCategory() {
  const payload = { name_zh: categoryForm.value.name_zh, name_en: categoryForm.value.name_en || null }
  if (!categoryForm.value.id) {
    await axios.post('/api/admin/categories', payload)
  } else {
    await axios.patch(`/api/admin/categories/${categoryForm.value.id}`, payload)
  }
  showCategoryModal.value = false
  await loadCategories()
}
async function removeCategory(c) {
  if (!confirm(`刪除類別「${c.name_zh}」？`)) return
  try {
    await axios.delete(`/api/admin/categories/${c.category_id}`)
    if (activeCategory.value?.category_id === c.category_id) activeCategory.value = null
    await loadCategories()
    await loadDishes()
  } catch (e) {
    const status = e?.response?.status
    if (status === 409) alert('此類別仍有菜色，無法刪除')
    else if (status === 404) alert('類別不存在')
    else alert('刪除失敗')
  }
}

function openNewDish() {
  dishForm.value = { id: null, name_zh: '', is_set: false, sort_order: 0, prices: [] }
  showDishModal.value = true
}
function editDish(d) {
  dishForm.value = {
    id: d.dish_id,
    name_zh: d.name_zh,
    is_set: !!d.is_set,
    sort_order: d.sort_order || 0,
    prices: (d.prices || []).map(p => ({ label: p.label || null, price: p.price }))
  }
  showDishModal.value = true
}
function closeDishModal() { showDishModal.value = false }
function addPrice() { dishForm.value.prices.push({ label: null, price: null }) }

async function saveDish() {
  if (!activeCategory.value) return
  const payload = {
    category_id: activeCategory.value.category_id,
    name_zh: dishForm.value.name_zh,
    is_set: !!dishForm.value.is_set,
    sort_order: dishForm.value.sort_order || 0,
    prices: dishForm.value.prices
  }
  if (!dishForm.value.id) {
    await axios.post('/api/admin/dishes', payload)
  } else {
    await axios.patch(`/api/admin/dishes/${dishForm.value.id}`, payload)
  }
  showDishModal.value = false
  await loadDishes()
}

async function removeDish(d) {
  if (!confirm(`刪除菜色「${d.name_zh}」？`)) return
  await axios.delete(`/api/admin/dishes/${d.dish_id}`)
  await loadDishes()
}

onMounted(async () => {
  await loadCategories()
  await loadDishes()
})
</script>

