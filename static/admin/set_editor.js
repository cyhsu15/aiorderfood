const qs = (sel, el=document) => el.querySelector(sel)
const qsa = (sel, el=document) => Array.from(el.querySelectorAll(sel))

let state = {
  sets: [],
  categories: [],
  dishesByCategory: new Map(), // category_id -> dishes[]
  activeSetId: null,
  selected: new Map(), // item_id -> { item_id, name_zh, quantity, sort_order }
}

async function api(path, opts={}) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin', ...opts })
  if (!res.ok) throw Object.assign(new Error('request_failed'), { status: res.status, res })
  if (res.status === 204) return null
  return res.json()
}

async function loadSets() {
  state.sets = await api('/api/admin/sets')
  const sel = qs('#setSelect'); sel.innerHTML = ''
  state.sets.forEach(s => {
    const opt = document.createElement('option')
    opt.value = String(s.dish_id)
    opt.textContent = s.name_zh
    sel.appendChild(opt)
  })
  if (!state.activeSetId && state.sets.length) state.activeSetId = state.sets[0].dish_id
  sel.value = String(state.activeSetId || '')
}

async function loadCategoriesAndDishes() {
  state.categories = await api('/api/admin/categories')
  for (const c of state.categories) {
    const dishes = await api(`/api/admin/categories/${c.category_id}/dishes`)
    state.dishesByCategory.set(c.category_id, dishes)
  }
}

async function loadSetItems() {
  if (!state.activeSetId) return
  const items = await api(`/api/admin/sets/${state.activeSetId}/items`)
  state.selected.clear()
  items.forEach((it, idx) => state.selected.set(it.item_id, { ...it, sort_order: it.sort_order ?? idx }))
}

function renderCatalog() {
  const container = qs('#catalog')
  container.innerHTML = ''
  state.categories.forEach(c => {
    const h = document.createElement('div')
    h.className = 'cat-title'
    h.textContent = c.name_zh
    container.appendChild(h)
    const ul = document.createElement('ul')
    const dishes = state.dishesByCategory.get(c.category_id) || []
    dishes.forEach(d => {
      const li = document.createElement('li')
      const id = `ck-${c.category_id}-${d.dish_id}`
      const checked = state.selected.has(d.dish_id)
      li.innerHTML = `
        <label style="display:flex; align-items:center; gap:8px;">
          <input type="checkbox" id="${id}" ${checked ? 'checked' : ''} data-id="${d.dish_id}" data-name="${d.name_zh}" />
          <span>${d.name_zh}</span>
          ${d.is_set ? '<span class="pill">套餐</span>' : ''}
        </label>`
      ul.appendChild(li)
    })
    container.appendChild(ul)
  })
}

function renderSelected() {
  const ul = qs('#selectedList')
  ul.innerHTML = ''
  // sort by sort_order then id
  const items = Array.from(state.selected.values()).sort((a,b)=> (a.sort_order??0)-(b.sort_order??0) || a.item_id-b.item_id)
  items.forEach((it, idx) => {
    const li = document.createElement('li')
    li.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px;">
        <span style="flex:1">${it.name_zh}</span>
        <label class="muted">數量</label>
        <input type="number" min="1" value="${it.quantity || 1}" data-id="${it.item_id}" class="qty" style="width:70px" />
        <label class="muted">排序</label>
        <input type="number" value="${it.sort_order ?? idx}" data-id="${it.item_id}" class="ord" style="width:70px" />
        <button class="btn danger" data-id="${it.item_id}" data-act="remove">移除</button>
      </div>`
    ul.appendChild(li)
  })
}

function bindEvents() {
  qs('#btnLoadSet').onclick = async () => {
    state.activeSetId = Number(qs('#setSelect').value)
    await loadSetItems(); renderCatalog(); renderSelected()
  }

  // Toggle items via catalog checkboxes
  qs('#catalog').addEventListener('change', (e) => {
    const ck = e.target.closest('input[type="checkbox"][data-id]')
    if (!ck) return
    const id = Number(ck.dataset.id)
    const name = ck.dataset.name
    if (ck.checked) {
      state.selected.set(id, { item_id: id, name_zh: name, quantity: 1, sort_order: state.selected.size })
    } else {
      state.selected.delete(id)
    }
    renderSelected()
  })

  // Adjust quantity/sort or remove from selected list
  qs('#selectedList').addEventListener('input', (e) => {
    const qty = e.target.closest('input.qty')
    const ord = e.target.closest('input.ord')
    if (!qty && !ord) return
    const id = Number((qty||ord).dataset.id)
    const it = state.selected.get(id); if (!it) return
    if (qty) it.quantity = Math.max(1, Number(qty.value || 1))
    if (ord) it.sort_order = Number(ord.value || 0)
  })
  qs('#selectedList').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-act="remove"][data-id]')
    if (!btn) return
    const id = Number(btn.dataset.id)
    state.selected.delete(id)
    // also uncheck in catalog
    const ck = qs(`#catalog input[type="checkbox"][data-id="${id}"]`)
    if (ck) ck.checked = false
    renderSelected()
  })

  // Save
  qs('#btnSave').onclick = async () => {
    if (!state.activeSetId) { alert('請先選擇套餐'); return }
    const items = Array.from(state.selected.values()).map(it => ({
      item_id: it.item_id,
      quantity: it.quantity || 1,
      sort_order: it.sort_order ?? 0,
    }))
    await api(`/api/admin/sets/${state.activeSetId}/items`, { method:'PUT', body: JSON.stringify({ items }) })
    qs('#hint').textContent = '已儲存'
    setTimeout(()=>{ qs('#hint').textContent='' }, 1500)
  }
}

async function boot() {
  await loadSets()
  await loadCategoriesAndDishes()
  await loadSetItems()
  renderCatalog()
  renderSelected()
  bindEvents()
}

boot()

