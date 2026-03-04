$(function () {
  const state = {
    categories: [],
    activeCategoryId: null,
    dishes: [],
    editingCategoryId: null,
    editingDishId: null,
  }

  const $categoryList = $('#categoryList')
  const $dishTableBody = $('#dishTableBody')
  const $currentCategory = $('#currentCategory')
  const $btnNewDish = $('#btnNewDish')

  const categoryModal = new bootstrap.Modal(document.getElementById('categoryModal'))
  const dishModal = new bootstrap.Modal(document.getElementById('dishModal'))

  const $categoryNameZh = $('#categoryNameZh')
  const $categoryNameEn = $('#categoryNameEn')
  const $categorySort = $('#categorySortOrder')
  const $categoryModalTitle = $('#categoryModalTitle')

  const $dishCategory = $('#dishCategory')
  const $dishNameZh = $('#dishNameZh')
  const $dishIsSet = $('#dishIsSet')
  const $dishSortOrder = $('#dishSortOrder')
  const $dishImageUrl = $('#dishImageUrl')
  const $dishTags = $('#dishTags')
  const $dishDescription = $('#dishDescription')
  const $dishModalTitle = $('#dishModalTitle')
  const $priceList = $('#priceList')

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      ...options,
    })
    if (!res.ok) {
      const err = new Error('request_failed')
      err.status = res.status
      err.response = res
      throw err
    }
    if (res.status === 204) return null
    return res.json()
  }

  function firstPrice(dish) {
    const price = dish.prices?.[0]
    if (!price) return '—'
    return price.price != null ? `NT$${Number(price.price)}` : '—'
  }

  function renderCategories() {
    $categoryList.empty()
    if (!state.categories.length) {
      $categoryList.append('<li class="list-group-item text-secondary text-center py-4">尚無資料</li>')
      return
    }

    const sorted = [...state.categories].sort(
      (a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.category_id - b.category_id,
    )

    sorted.forEach((cat) => {
      const active = cat.category_id === state.activeCategoryId
      const $item = $(`
        <li class="list-group-item d-flex justify-content-between align-items-center ${active ? 'active text-white' : ''}">
          <div class="d-flex flex-column">
            <strong>${cat.name_zh || '(未命名)'}</strong>
            <small class="${active ? 'text-white-50' : 'text-secondary'}">
              排序：${cat.sort_order ?? 0}${cat.name_en ? ` · ${cat.name_en}` : ''}
            </small>
          </div>
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-${active ? 'light' : 'secondary'} btn-select">查看</button>
            <button class="btn btn-outline-${active ? 'light' : 'secondary'} btn-edit">編輯</button>
            <button class="btn btn-outline-${active ? 'light' : 'danger'} btn-delete">刪除</button>
          </div>
        </li>
      `)
      $item.find('.btn-select').on('click', () => selectCategory(cat.category_id))
      $item.find('.btn-edit').on('click', () => openCategoryModal(cat))
      $item.find('.btn-delete').on('click', () => removeCategory(cat))
      $categoryList.append($item)
    })
  }

  function renderDishes() {
    $dishTableBody.empty()
    const activeCategory = state.categories.find((c) => c.category_id === state.activeCategoryId)
    $currentCategory.text(activeCategory ? `（${activeCategory.name_zh}）` : '')
    $btnNewDish.prop('disabled', !activeCategory)

    if (!state.dishes.length) {
      $dishTableBody.append('<tr><td colspan="4" class="text-center text-secondary py-4">此類別尚無菜色</td></tr>')
      return
    }

    state.dishes.forEach((dish) => {
      const $row = $(`
        <tr>
          <td>
            <div class="fw-semibold">${dish.name_zh || dish.name || ''}</div>
            ${dish.is_set ? '<span class="badge text-bg-warning-subtle text-warning-emphasis">套餐</span>' : ''}
          </td>
          <td>${firstPrice(dish)}</td>
          <td>${dish.sort_order ?? 0}</td>
          <td class="text-end">
            <div class="btn-group btn-group-sm">
              <button class="btn btn-outline-secondary btn-edit-dish" data-id="${dish.dish_id}">編輯</button>
              <button class="btn btn-outline-danger btn-delete-dish" data-id="${dish.dish_id}">刪除</button>
            </div>
          </td>
        </tr>
      `)
      $dishTableBody.append($row)
    })
  }

  async function loadCategories() {
    state.categories = await api('/api/admin/categories')
    if (!state.activeCategoryId && state.categories.length) {
      state.activeCategoryId = state.categories[0].category_id
    }
    renderCategories()
  }

  async function loadDishes() {
    if (!state.activeCategoryId) {
      state.dishes = []
      renderDishes()
      return
    }
    state.dishes = await api(`/api/admin/categories/${state.activeCategoryId}/dishes`)
    renderDishes()
  }

  function populateCategorySelect(selectedId) {
    $dishCategory.empty()
    state.categories.forEach((cat) => {
      $('<option>')
        .val(String(cat.category_id))
        .text(cat.name_zh || '(未命名)')
        .appendTo($dishCategory)
    })
    if (selectedId) {
      $dishCategory.val(String(selectedId))
    }
  }

  function openCategoryModal(category = null) {
    state.editingCategoryId = category?.category_id ?? null
    $categoryModalTitle.text(category ? '編輯類別' : '新增類別')
    $categoryNameZh.val(category?.name_zh ?? '')
    $categoryNameEn.val(category?.name_en ?? '')
    $categorySort.val(category?.sort_order ?? 0)
    categoryModal.show()
  }

  function gatherPrices() {
    const prices = []
    $priceList.children('.price-item').each(function () {
      const $row = $(this)
      const label = $row.find('.price-label').val()?.toString().trim() || null
      const rawPrice = $row.find('.price-value').val()
      const price = rawPrice === '' ? null : Number(rawPrice)
      prices.push({ label, price })
    })
    return prices
  }

  function addPriceRow(label = '', price = '') {
    const $row = $(`
      <div class="price-item border rounded-3 p-3">
        <div class="row g-2 align-items-center">
          <div class="col-md-5">
            <label class="form-label mb-1">標籤</label>
            <input type="text" class="form-control price-label" placeholder="例：小 / 中 / 大" value="${label || ''}" />
          </div>
          <div class="col-md-5">
            <label class="form-label mb-1">價格</label>
            <input type="number" step="0.01" class="form-control price-value" placeholder="售價" value="${price ?? ''}" />
          </div>
          <div class="col-md-2 d-grid">
            <label class="form-label mb-1 invisible">操作</label>
            <button type="button" class="btn btn-outline-danger btn-remove-price">移除</button>
          </div>
        </div>
      </div>
    `)
    $row.find('.btn-remove-price').on('click', () => $row.remove())
    $priceList.append($row)
  }

  function openDishModal(dish = null) {
    state.editingDishId = dish?.dish_id ?? null
    $dishModalTitle.text(dish ? '編輯菜色' : '新增菜色')
    populateCategorySelect(dish?.category_id ?? state.activeCategoryId)
    $dishNameZh.val(dish?.name_zh ?? '')
    $dishIsSet.prop('checked', !!dish?.is_set)
    $dishSortOrder.val(dish?.sort_order ?? 0)
    $dishImageUrl.val(dish?.detail?.image_url ?? '')
    $dishTags.val(dish?.detail?.tags ?? '')
    $dishDescription.val(dish?.detail?.description ?? '')
    $priceList.empty()
    ;(dish?.prices ?? []).forEach((price) => addPriceRow(price.label || '', price.price ?? ''))
    if ($priceList.children().length === 0) addPriceRow()
    dishModal.show()
  }

  async function selectCategory(categoryId) {
    state.activeCategoryId = categoryId
    await loadCategories()
    await loadDishes()
  }

  async function saveCategory() {
    const payload = {
      name_zh: $categoryNameZh.val()?.toString().trim(),
      name_en: $categoryNameEn.val()?.toString().trim() || null,
      sort_order: Number($categorySort.val() || 0),
    }
    if (!payload.name_zh) {
      alert('請輸入中文名稱')
      return
    }
    if (state.editingCategoryId) {
      await api(`/api/admin/categories/${state.editingCategoryId}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
    } else {
      await api('/api/admin/categories', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    }
    categoryModal.hide()
    await loadCategories()
    await loadDishes()
  }

  async function removeCategory(category) {
    if (!confirm(`確定刪除類別「${category.name_zh}」嗎？`)) return
    try {
      await api(`/api/admin/categories/${category.category_id}`, { method: 'DELETE' })
      if (state.activeCategoryId === category.category_id) {
        state.activeCategoryId = null
      }
      await loadCategories()
      await loadDishes()
    } catch (err) {
      if (err.status === 409) {
        alert('此類別仍有菜色，請先移除菜色後再刪除。')
      } else if (err.status === 404) {
        alert('找不到該類別。')
      } else {
        alert('刪除失敗，請稍後再試。')
      }
    }
  }

  async function saveDish() {
    if (!state.categories.length) {
      alert('請先建立類別')
      return
    }
    const payload = {
      category_id: Number($dishCategory.val()),
      name_zh: $dishNameZh.val()?.toString().trim(),
      is_set: $dishIsSet.prop('checked'),
      sort_order: Number($dishSortOrder.val() || 0),
      prices: gatherPrices(),
      detail: {
        image_url: $dishImageUrl.val()?.toString().trim() || null,
        tags: $dishTags.val()?.toString().trim() || null,
        description: $dishDescription.val()?.toString().trim() || null,
      },
    }
    if (!payload.name_zh) {
      alert('請輸入菜色名稱')
      return
    }
    if (state.editingDishId) {
      await api(`/api/admin/dishes/${state.editingDishId}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
    } else {
      await api('/api/admin/dishes', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    }
    dishModal.hide()
    await loadDishes()
  }

  async function removeDish(dish) {
    if (!confirm(`確定刪除菜色「${dish.name_zh || dish.name}」嗎？`)) return
    try {
      await api(`/api/admin/dishes/${dish.dish_id}`, { method: 'DELETE' })
      await loadDishes()
    } catch (err) {
      if (err.status === 409) {
        alert('此菜色已被套餐使用，請先於套餐管理中移除。')
      } else if (err.status === 404) {
        alert('找不到該菜色，可能已被刪除。')
      } else {
        alert('刪除失敗，請稍後再試。')
      }
    }
  }

  function bindEvents() {
    $('#btnNewCategory').on('click', () => openCategoryModal())
    $('#btnSaveCategory').on('click', saveCategory)
    $('#btnNewDish').on('click', () => openDishModal())
    $('#btnSaveDish').on('click', saveDish)
    $('#btnAddPrice').on('click', () => addPriceRow())

    $dishTableBody.on('click', '.btn-edit-dish', function () {
      const id = Number($(this).data('id'))
      const dish = state.dishes.find((d) => d.dish_id === id)
      if (dish) openDishModal(dish)
    })

    $dishTableBody.on('click', '.btn-delete-dish', function () {
      const id = Number($(this).data('id'))
      const dish = state.dishes.find((d) => d.dish_id === id)
      if (dish) removeDish(dish)
    })
  }

  async function init() {
    bindEvents()
    addPriceRow()
    await loadCategories()
    await loadDishes()
  }

  init()
})
