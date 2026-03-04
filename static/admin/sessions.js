$(function () {
  const $sessionList = $('#sessionList')
  const $keywordInput = $('#sessionKeyword')
  const $btnRefresh = $('#btnRefreshSessions')

  const $detailTitle = $('#detailTitle')
  const $detailSummary = $('#detailSummary')
  const $detailMeta = $('#detailMeta')
  const $detailCart = $('#detailCart')
  const $detailActions = $('#detailActions')
  const $btnClearCart = $('#btnClearCart')
  const $btnDeleteSession = $('#btnDeleteSession')

  let sessions = []
  let filteredSessions = []
  let currentSessionId = null
  let currentDetail = null

  const fmtDateTime = (value) => {
    if (!value) return '-'
    const dt = new Date(value)
    if (Number.isNaN(dt.valueOf())) return value
    return dt.toLocaleString('zh-TW', { hour12: false })
  }

  async function fetchSessions() {
    $sessionList.html('<div class="list-group-item text-center text-secondary py-4">載入資料中…</div>')
    try {
      const res = await fetch('/api/admin/sessions')
      if (!res.ok) throw new Error(await res.text())
      sessions = await res.json()
      applyFilter()
    } catch (err) {
      console.error('載入 Session 失敗', err)
      $sessionList.html('<div class="list-group-item text-center text-danger py-4">無法載入 Session，請稍後再試。</div>')
    }
  }

  function applyFilter() {
    const keyword = $keywordInput.val()?.toString().trim().toLowerCase() || ''
    filteredSessions = sessions.filter((session) => {
      if (!keyword) return true
      const haystack = [
        session.session_id,
        session.note || '',
        String(session.cart_size || ''),
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(keyword)
    })
    renderList()
  }

  function renderList() {
    if (!filteredSessions.length) {
      $sessionList.html('<div class="list-group-item text-center text-secondary py-4">目前沒有符合條件的 Session。</div>')
      return
    }

    const items = filteredSessions
      .map((session) => {
        const active = session.session_id === currentSessionId ? 'active' : ''
        return `
          <button type="button" class="list-group-item list-group-item-action d-flex flex-column gap-2 ${active}" data-id="${session.session_id}">
            <div class="d-flex justify-content-between align-items-center">
              <strong class="text-truncate me-2">#${session.session_id}</strong>
              <div class="d-flex gap-2">
                <span class="badge text-bg-primary-subtle text-primary-emphasis">購物車 ${session.cart_size ?? 0}</span>
                <button type="button" class="btn btn-sm btn-outline-danger btn-delete-session" data-id="${session.session_id}">刪除</button>
              </div>
            </div>
            <div class="small text-secondary">
              <div>最後更新：${fmtDateTime(session.updated_at)}</div>
              ${session.note ? `<div>備註：${session.note}</div>` : ''}
            </div>
          </button>
        `
      })
      .join('')

    $sessionList.html(items)
  }

  async function loadSessionDetail(sessionId) {
    try {
      const res = await fetch(`/api/admin/sessions/${sessionId}`)
      if (!res.ok) throw new Error(await res.text())
      currentDetail = await res.json()
      currentSessionId = sessionId
      renderDetail()
      applyFilter()
    } catch (err) {
      console.error('取得 Session 詳細失敗', err)
      alert('取得 Session 詳細失敗，請稍後再試。')
    }
  }

  function renderDetail() {
    if (!currentDetail) {
      $detailTitle.text('尚未選擇 Session')
      $detailSummary.text('左側點選 Session 以檢視詳細資料。')
      $detailMeta.text('尚無資料')
      $detailCart.html('<tr><td colspan="4" class="text-secondary text-center py-4">尚未選擇 Session。</td></tr>')
      $detailActions.attr('hidden', true)
      return
    }
    const { session_id, created_at, updated_at, cart_items, note } = currentDetail
    $detailTitle.text(`Session #${session_id}`)
    $detailSummary.html(`建立：${fmtDateTime(created_at)} · 更新：${fmtDateTime(updated_at)}`)
    $detailMeta.html(`備註：${note || '—'}`)
    $detailActions.removeAttr('hidden')

    if (!Array.isArray(cart_items) || !cart_items.length) {
      $detailCart.html('<tr><td colspan="4" class="text-secondary text-center py-4">目前購物車為空。</td></tr>')
      return
    }

    const rows = cart_items
      .map(
        (item) => `
          <tr>
            <td>${item.name || '-'}</td>
            <td>${item.size ? `份量：${item.size}` : ''}${item.note ? `<div>備註：${item.note}</div>` : ''}</td>
            <td class="text-end">${item.qty}</td>
            <td class="text-end">NT$${Number(item.price || 0)}</td>
          </tr>
        `,
      )
      .join('')
    $detailCart.html(rows)
  }

  async function clearCart() {
    if (!currentSessionId) return
    if (!confirm('確認清空此 Session 的購物車內容？')) return
    $btnClearCart.prop('disabled', true)
    try {
      const res = await fetch(`/api/admin/sessions/${currentSessionId}/clear-cart`, { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      await loadSessionDetail(currentSessionId)
      await fetchSessions()
    } catch (err) {
      console.error('清空購物車失敗', err)
      alert('清空購物車失敗，請稍後再試。')
    } finally {
      $btnClearCart.prop('disabled', false)
    }
  }

  async function deleteSession(sessionId) {
    if (!confirm('確認刪除此 Session？若使用者仍在線將重新建立新 Session。')) return
    try {
      const res = await fetch(`/api/admin/sessions/${sessionId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(await res.text())
      if (sessionId === currentSessionId) {
        currentSessionId = null
        currentDetail = null
        renderDetail()
      }
      await fetchSessions()
    } catch (err) {
      console.error('刪除 Session 失敗', err)
      alert('刪除 Session 失敗，請稍後再試。')
    }
  }

  $sessionList.on('click', '.list-group-item', function (event) {
    const sessionId = $(this).data('id')
    if ($(event.target).hasClass('btn-delete-session')) {
      deleteSession(sessionId)
    } else {
      loadSessionDetail(sessionId)
    }
  })

  $keywordInput.on('input', applyFilter)
  $btnRefresh.on('click', fetchSessions)
  $btnClearCart.on('click', clearCart)
  $btnDeleteSession.on('click', () => {
    if (currentSessionId) deleteSession(currentSessionId)
  })

  fetchSessions()
})
