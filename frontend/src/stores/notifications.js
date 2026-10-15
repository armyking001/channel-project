import { create } from 'zustand'

const API_WS_BASE = (() => {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return proto + '//' + window.location.host + '/ws/notifications'
})()

export const useNotificationStore = create((set, get) => ({
  unreadCount: 0,
  recent: [],
  total: 0,
  ws: null,
  connected: false,

  // 连接 WebSocket(token from query string;登录后由 Layout 调用)
  init() {
    const token = localStorage.getItem('token')
    if (!token) return
    if (get().ws) return
    try {
      const ws = new WebSocket(API_WS_BASE + '?token=' + encodeURIComponent(token))
      ws.onopen = () => set({ connected: true })
      ws.onclose = () => {
        set({ connected: false, ws: null })
        // 简单重连(3 秒)
        setTimeout(() => {
          if (localStorage.getItem('token') && !get().ws) get().init()
        }, 3000)
      }
      ws.onerror = () => { try { ws.close() } catch (_) {} }
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.event === 'notification.new') {
            get()._onNew(msg.data)
          } else if (msg.event === 'notification.unread') {
            set({ unreadCount: (msg.data && msg.data.unread_count) || 0 })
          }
        } catch (_) {}
      }
      set({ ws })
    } catch (_) {}
  },

  // 收到后端推送的新通知:未读+1,加入 recent,并把浏览器 tab 标题加前缀
  _onNew(n) {
    const state = get()
    if (state.recent.some(r => r.id === n.id)) return
    const recent = [n].concat(state.recent).slice(0, 10)
    set({
      unreadCount: state.unreadCount + 1,
      recent: recent,
      total: state.total + 1,
    })
    try {
      if (!document.title.startsWith('[')) {
        document.title = '[新消息] ' + document.title
      }
    } catch (_) {}
  },

  async refreshUnread() {
    try {
      const m = await import('../api')
      const r = await m.getUnreadCount()
      set({ unreadCount: r.data.unread_count })
    } catch (_) {}
  },

  async refreshRecent() {
    try {
      const m = await import('../api')
      const r = await m.listNotifications({ page: 1, page_size: 10 })
      set({ recent: r.data.items || [], total: r.data.total || 0 })
    } catch (_) {}
  },

  async markRead(id) {
    try {
      const m = await import('../api')
      await m.markNotificationRead(id)
      const state = get()
      const recent = state.recent.map(n => n.id === id ? Object.assign({}, n, { is_read: true }) : n)
      const wasUnread = state.recent.find(n => n.id === id && !n.is_read)
      const unreadCount = Math.max(0, state.unreadCount - (wasUnread ? 1 : 0))
      set({ recent: recent, unreadCount: unreadCount })
    } catch (_) {}
  },

  async markAllRead() {
    try {
      const m = await import('../api')
      await m.markAllNotificationsRead()
      const recent = get().recent.map(n => Object.assign({}, n, { is_read: true }))
      set({ unreadCount: 0, recent: recent })
    } catch (_) {}
  },

  close() {
    const ws = get().ws
    if (ws) { try { ws.close() } catch (_) {} }
    set({ ws: null, connected: false, unreadCount: 0, recent: [], total: 0 })
    try {
      document.title = document.title.replace(/^\[新消息\]\s*/, '')
    } catch (_) {}
  },
}))