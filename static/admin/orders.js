$(function () {
  const $orderTableBody = $('#orderTableBody')
  const $keywordInput = $('#keywordInput')
  const $statusFilter = $('#statusFilter')
  const $orderCountLabel = $('#orderCountLabel')
  const $btnRefresh = $('#btnRefresh')

  const orderModal = new bootstrap.Modal(document.getElementById('orderModal'))
  const $modalOrderId = $('#modalOrderId')
  const $modalStatus = $('#modalStatus')
  const $modalContactName = $('#modalContactName')
  const $modalContactPhone = $('#modalContactPhone')
  const $modalNote = $('#modalNote')
  const $modalMeta = $('#modalMeta')
  const $modalItemsBody = $('#modalItemsBody')
  const $btnAddOrderItem = $('#btnAddOrderItem')
  const $btnSaveOrder = $('#btnSaveOrder')

  const STATUS_BADGE = {
    pending: 'badge text-bg-secondary',
    preparing: 'badge text-bg-warning',
    completed: 'badge text-bg-success',
    cancelled: 'badge text-bg-danger',
  }

  const STATUS_LABEL = {
    pending: '待處理',
    preparing: '製作中',
    completed: '已完成',
    cancelled: '已取消',
  }

  let orders = []
  let currentOrder = null
  let menuItems = []
  let menuOptionsHtml = '<option value="">自訂品項</option>'
  const menuMap = new Map()

  bindEvents()
  init().catch((err) => console.error('初始化訂單管理失敗', err))

  async function init() {
    await loadMenuItems()
    await fetchOrders()
  }

  async function loadMenuItems() {
    try {
      const res = await fetch('/api/admin/categories')
      if (!res.ok) throw new Error(await res.text())
      const categories = await res.json()

      const items = []
      for (const cat of categories) {
        const dishRes = await fetch(`/api/admin/categories/${cat.category_id}/dishes`)
        if (!dishRes.ok) throw new Error(await dishRes.text())
        const dishes = await dishRes.json()
        dishes.forEach((dish) => {
          const prices = Array.isArray(dish.prices) ? dish.prices : []
          const defaultPrice = prices.length ? Number(prices[0].price || 0) : 0
          items.push({
            dish_id: dish.dish_id,
            name: dish.name_zh || dish.name || `品項 ${dish.dish_id}`,
            category_name: cat.name_zh || `分類 ${cat.category_id}`,
            default_price: Number.isFinite(defaultPrice) ? defaultPrice : 0,
            sizes: prices
              .filter((p) => p.label)
              .map((p) => ({
                label: p.label,
                price: Number(p.price || 0),
              })),
          })
        })
      }

      menuItems = items
      menuMap.clear()
      items.forEach((item) => menuMap.set(item.dish_id, item))

      const grouped = new Map()
      items.forEach((item) => {
        const key = item.category_name
        if (!grouped.has(key)) grouped.set(key, [])
        grouped.get(key).push(item)
      })

      let options = '<option value="">自訂品項</option>'
      for (const [category, list] of grouped.entries()) {
        const sorted = list.sort((a, b) => a.name.localeCompare(b.name, 'zh-Hant'))
        const inner = sorted.map((item) => `<option value="${item.dish_id}">${item.name}</option>`).join('')
        options += `<optgroup label="${category}">${inner}</optgroup>`
      }
      menuOptionsHtml = options
    } catch (err) {
      console.error('載入菜單資料失敗', err)
      menuItems = []
      menuMap.clear()
      menuOptionsHtml = '<option value="">自訂品項</option>'
    }
  }

  async function fetchOrders() {
    $orderTableBody.html('<tr><td colspan="7" class="text-center text-secondary py-4">載入資料中…</td></tr>')
    try {
      const res = await fetch('/api/admin/orders?limit=200')
      if (!res.ok) throw new Error(await res.text())
      orders = await res.json()
      renderOrders()
    } catch (err) {
      console.error('載入訂單失敗', err)
      $orderTableBody.html('<tr><td colspan="7" class="text-center text-danger py-4">載入訂單失敗，請稍後再試。</td></tr>')
    }
  }

  function renderOrders() {
    const keyword = $keywordInput.val()?.toLowerCase().trim() || ''
    const status = $statusFilter.val()

    const filtered = orders.filter((order) => {
      const matchesStatus = !status || order.status === status
      const haystack = [
        order.order_id,
        order.contact_name || '',
        order.contact_phone || '',
        order.note || '',
      ]
        .join(' ')
        .toLowerCase()
      const matchesKeyword = !keyword || haystack.includes(keyword)
      return matchesStatus && matchesKeyword
    })

    $orderCountLabel.text(`共 ${filtered.length} 筆訂單`)

    if (!filtered.length) {
      $orderTableBody.html('<tr><td colspan="7" class="text-center text-secondary py-4">目前沒有符合條件的訂單。</td></tr>')
      return
    }

    const rows = filtered
      .map((order) => {
        const badgeClass = STATUS_BADGE[order.status] || STATUS_BADGE.pending
        const badgeLabel = STATUS_LABEL[order.status] || STATUS_LABEL.pending
        return `
          <tr>
            <td class="fw-semibold">#${order.order_id}</td>
            <td>${fmtDateTime(order.created_at)}</td>
            <td><span class="${badgeClass}">${badgeLabel}</span></td>
            <td>${fmtCurrency(order.total_amount)}</td>
            <td>${order.item_count ?? 0}</td>
            <td>${order.contact_name || '—'}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-primary btn-view-order" data-id="${order.order_id}">檢視</button>
            </td>
          </tr>
        `
      })
      .join('')

    $orderTableBody.html(rows)
  }

  async function openOrder(orderId) {
    try {
      const res = await fetch(`/api/admin/orders/${orderId}`)
      if (!res.ok) throw new Error(await res.text())
      currentOrder = await res.json()
      fillOrderModal(currentOrder)
      orderModal.show()
    } catch (err) {
      console.error('取得訂單失敗', err)
      alert('取得訂單詳細失敗，請稍後再試。')
    }
  }

  function fillOrderModal(order) {
    $modalOrderId.text(`訂單 #${order.order_id}`)
    $modalStatus.val(order.status || 'pending')
    $modalContactName.val(order.contact_name || '')
    $modalContactPhone.val(order.contact_phone || '')
    $modalNote.val(order.note || '')
    $modalMeta.html(`
      <div class="d-flex flex-column gap-1">
        <span>總金額：<strong id="modalComputedTotal">${fmtCurrency(order.total_amount)}</strong></span>
        <span>建立時間：${fmtDateTime(order.created_at)}</span>
        <span>Session ID：${order.session_id || '—'}</span>
      </div>
    `)

    $modalItemsBody.empty()
    if (!Array.isArray(order.items) || !order.items.length) {
      $modalItemsBody.append(
        '<tr class="empty-row"><td colspan="5" class="text-center text-secondary py-3">本訂單沒有明細。</td></tr>',
      )
    } else {
      order.items.forEach((item) => {
        const $row = createItemRow(item)
        $modalItemsBody.append($row)
      })
    }
    recomputeTotals()
  }

  function createItemRow(item = {}, isNew = false) {
    const safeName = escapeHtml(item.name || '')
    const safeNote = escapeHtml(item.note || '')
    const safeSize = escapeHtml(item.size_label || '')
    const qty = Number(item.quantity ?? 1)
    const unitPrice = Number(item.unit_price ?? 0)
    const lineTotal = qty > 0 ? unitPrice * qty : 0

    const $row = $(`
      <tr class="order-item-row ${isNew ? 'table-success-subtle' : ''}" data-removed="0">
        <td>
          <div class="mb-2">
            <select class="form-select form-select-sm item-dish-select"></select>
          </div>
          <input type="text" class="form-control form-control-sm item-name mb-2" placeholder="品項名稱" value="${safeName}" />
          <div class="input-group input-group-sm">
            <span class="input-group-text">單價</span>
            <input type="number" min="0" step="0.01" class="form-control item-price" value="${unitPrice}" />
          </div>
        </td>
        <td>
          <select class="form-select form-select-sm item-size-select mb-2">
            <option value="">選擇份量</option>
          </select>
          <input type="hidden" class="item-size" value="${safeSize}" />
          <textarea class="form-control form-control-sm item-note" rows="2" placeholder="明細備註">${safeNote}</textarea>
        </td>
        <td style="width:110px;">
          <input type="number" min="0" class="form-control form-control-sm item-qty text-end" value="${qty}" />
        </td>
        <td class="text-end">
          <div class="fw-semibold item-line-total mb-2">${fmtCurrency(lineTotal)}</div>
        </td>
        <td class="text-end">
          <button type="button" class="btn btn-sm btn-outline-danger btn-remove-item">${item.order_item_id ? '移除' : '刪除'}</button>
        </td>
      </tr>
    `)

    $row.data('itemId', item.order_item_id || null)
    const dishId = item.dish_id || ''
    $row.attr('data-dish-id', dishId)
    populateRowMenuSelect($row, dishId, !isNew)
    return $row
  }

  function populateRowMenuSelect($row, selectedDishId, preserveExisting = true) {
    const $select = $row.find('.item-dish-select')
    $select.html(menuOptionsHtml)
    if (selectedDishId) {
      $select.val(String(selectedDishId))
      $row.attr('data-dish-id', selectedDishId)
      const dish = menuMap.get(Number(selectedDishId))
      applyDishDataToRow($row, dish, preserveExisting)
    } else {
      $select.val('')
      $row.attr('data-dish-id', '')
      applyDishDataToRow($row, null, preserveExisting)
    }
  }

  function populateSizeOptions($sizeSelect, sizes, currentValue) {
    let options = '<option value="">選擇份量</option>'
    const seen = new Set()
    if (Array.isArray(sizes) && sizes.length) {
      options += sizes
        .map((size) => {
          const label = size.label || ''
          seen.add(label)
          return `<option value="${escapeHtml(label)}" data-price="${Number(size.price)}">${escapeHtml(label)}</option>`
        })
        .join('')
    }
    if (currentValue && !seen.has(currentValue)) {
      options += `<option value="${escapeHtml(currentValue)}">${escapeHtml(currentValue)}</option>`
    }
    $sizeSelect.html(options)
    if (currentValue) {
      $sizeSelect.val(currentValue)
    }
  }

  function updateHiddenSize($row) {
    const selectedSize = $row.find('.item-size-select').val() || ''
    $row.find('.item-size').val(selectedSize)
  }

  function applyDishDataToRow($row, dish, preserveExisting) {
    const $sizeSelect = $row.find('.item-size-select')
    const hiddenSizeInput = $row.find('.item-size')
    const currentSize = preserveExisting ? hiddenSizeInput.val() : ''
    populateSizeOptions($sizeSelect, dish?.sizes || [], currentSize)

    if (!dish) {
      $sizeSelect.prop('disabled', true)
      if (!preserveExisting) {
        $row.find('.item-price').val(0)
        hiddenSizeInput.val('')
      }
      updateHiddenSize($row)
      return
    }

    $sizeSelect.prop('disabled', !(dish.sizes && dish.sizes.length))

    if (!preserveExisting || !$sizeSelect.val()) {
      const preferredSize = dish.sizes && dish.sizes.length ? dish.sizes[0].label : ''
      if (preferredSize) {
        $sizeSelect.val(preferredSize)
        hiddenSizeInput.val(preferredSize)
        const match = (dish.sizes || []).find((s) => s.label === preferredSize)
        if (match && Number(match.price) > 0) {
          $row.find('.item-price').val(Number(match.price))
        } else {
          $row.find('.item-price').val(dish.default_price || 0)
        }
      } else {
        hiddenSizeInput.val('')
        $row.find('.item-price').val(dish.default_price || 0)
      }
    } else {
      const selectedSize = $sizeSelect.val()
      const match = (dish.sizes || []).find((s) => s.label === selectedSize)
      if (match && Number(match.price) > 0) {
        $row.find('.item-price').val(Number(match.price))
      } else if (!selectedSize && Number(dish.default_price) > 0) {
        $row.find('.item-price').val(dish.default_price)
      }
    }

    if (!preserveExisting || !($row.find('.item-name').val() || '').trim()) {
      $row.find('.item-name').val(dish.name)
    }
    updateHiddenSize($row)
    recomputeTotals()
  }

  function addNewItemRow() {
    $modalItemsBody.find('.empty-row').remove()
    const $row = createItemRow({ quantity: 1, unit_price: 0 }, true)
    $modalItemsBody.append($row)
    recomputeTotals()
  }

  function markRowRemoved($row) {
    const itemId = $row.data('itemId')
    if (!itemId) {
      $row.remove()
      if (!$modalItemsBody.children('.order-item-row').length) {
        $modalItemsBody.append(
          '<tr class="empty-row"><td colspan="5" class="text-center text-secondary py-3">本訂單沒有明細。</td></tr>',
        )
      }
      recomputeTotals()
      return
    }
    $row.attr('data-removed', '1')
    $row.addClass('table-danger')
    $row.find('input, textarea, select').prop('disabled', true)
    $row.find('.btn-remove-item').prop('disabled', true).text('已標記刪除')
    recomputeTotals()
  }

  function gatherItemsPayload() {
    const payload = []
    $modalItemsBody.find('.order-item-row').each(function () {
      const $row = $(this)
      const removed = $row.attr('data-removed') === '1'
      const orderItemId = $row.data('itemId')

      if (removed) {
        if (orderItemId) {
          payload.push({ order_item_id: Number(orderItemId), quantity: 0 })
        }
        return
      }

      const name = $row.find('.item-name').val()?.toString().trim() || ''
      const quantityRaw = Number($row.find('.item-qty').val())
      const unitPriceRaw = Number($row.find('.item-price').val())
      const note = $row.find('.item-note').val()?.toString().trim() || null
      const sizeLabel = $row.find('.item-size').val()?.toString().trim() || null
      const dishIdAttr = $row.attr('data-dish-id')
      const dishId = dishIdAttr ? Number(dishIdAttr) : null
      const quantity = Number.isFinite(quantityRaw) && quantityRaw >= 0 ? quantityRaw : 0
      const unitPriceVal = Number.isFinite(unitPriceRaw) && unitPriceRaw >= 0 ? unitPriceRaw : 0

      if (!orderItemId) {
        if (!name || unitPriceVal <= 0 || quantity <= 0) {
          return
        }
        const payloadRow = {
          name,
          unit_price: unitPriceVal,
          quantity,
          note,
          size_label: sizeLabel,
        }
        if (dishId) payloadRow.dish_id = dishId
        payload.push(payloadRow)
      } else {
        const payloadRow = {
          order_item_id: Number(orderItemId),
          quantity,
          note,
          size_label: sizeLabel,
          name,
          unit_price: unitPriceVal,
        }
        if (dishId) payloadRow.dish_id = dishId
        payload.push(payloadRow)
      }
    })
    return payload
  }

  async function saveOrder() {
    if (!currentOrder) return
    const itemsPayload = gatherItemsPayload()
    const payload = {
      status: $modalStatus.val(),
      note: $modalNote.val()?.toString().trim() || null,
      contact_name: $modalContactName.val()?.toString().trim() || null,
      contact_phone: $modalContactPhone.val()?.toString().trim() || null,
      items: itemsPayload,
    }
    try {
      const res = await fetch(`/api/admin/orders/${currentOrder.order_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(await res.text())
      const updated = await res.json()
      currentOrder = updated
      fillOrderModal(updated)
      await fetchOrders()
      alert('訂單已更新')
    } catch (err) {
      console.error('更新訂單失敗', err)
      alert('更新訂單失敗，請稍後再試。')
    }
  }

  function recomputeTotals() {
    let total = 0
    $modalItemsBody.find('.order-item-row').each(function () {
      const $row = $(this)
      if ($row.attr('data-removed') === '1') {
        $row.find('.item-line-total').text(fmtCurrency(0))
        return
      }
      const qty = Number($row.find('.item-qty').val())
      const unitPrice = Number($row.find('.item-price').val())
      const lineTotal = qty > 0 ? unitPrice * qty : 0
      total += lineTotal
      $row.find('.item-line-total').text(fmtCurrency(lineTotal))
    })
    $('#modalComputedTotal').text(fmtCurrency(total))
  }

  function bindEvents() {
    $orderTableBody.on('click', '.btn-view-order', function () {
      const orderId = Number($(this).data('id'))
      openOrder(orderId)
    })

    $keywordInput.on('input', renderOrders)
    $statusFilter.on('change', renderOrders)
    $btnRefresh.on('click', fetchOrders)
    $btnSaveOrder.on('click', saveOrder)
    $btnAddOrderItem.on('click', addNewItemRow)

    $modalItemsBody.on('input', '.item-qty, .item-price', recomputeTotals)

    $modalItemsBody.on('click', '.btn-remove-item', function () {
      const $row = $(this).closest('.order-item-row')
      markRowRemoved($row)
    })

    $modalItemsBody.on('change', '.item-dish-select', function () {
      const $row = $(this).closest('.order-item-row')
      const value = $(this).val()
      if (!value) {
        $row.attr('data-dish-id', '')
        applyDishDataToRow($row, null, false)
        return
      }
      const dishId = Number(value)
      const dish = menuMap.get(dishId)
      $row.attr('data-dish-id', dishId)
      if (dish) {
        applyDishDataToRow($row, dish, false)
      } else {
        applyDishDataToRow($row, null, false)
      }
    })

    $modalItemsBody.on('change', '.item-size-select', function () {
      const $row = $(this).closest('.order-item-row')
      updateHiddenSize($row)
      const dishId = Number($row.attr('data-dish-id') || 0)
      if (dishId && menuMap.has(dishId)) {
        const dish = menuMap.get(dishId)
        const selectedLabel = $(this).val()
        const match = (dish.sizes || []).find((s) => s.label === selectedLabel)
        if (match && Number(match.price) > 0) {
          $row.find('.item-price').val(Number(match.price))
        } else if (!selectedLabel && Number(dish.default_price) > 0) {
          $row.find('.item-price').val(dish.default_price)
        }
      }
      recomputeTotals()
    })
  }

  function fmtCurrency(value) {
    if (typeof value !== 'number' || Number.isNaN(value)) return 'NT$0'
    return `NT$${value.toLocaleString('zh-TW', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
  }

  function fmtDateTime(value) {
    if (!value) return '-'
    const dt = new Date(value)
    if (Number.isNaN(dt.valueOf())) return value
    return dt.toLocaleString('zh-TW', { hour12: false })
  }

  function escapeHtml(text) {
    return (text || '').replace(/[&<>"']/g, (match) => {
      switch (match) {
        case '&':
          return '&amp;'
        case '<':
          return '&lt;'
        case '>':
          return '&gt;'
        case '"':
          return '&quot;'
        case "'":
          return '&#39;'
        default:
          return match
      }
    })
  }
})
