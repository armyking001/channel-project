import { useEffect, useState } from 'react'
import { useNotificationStore } from '../stores/notifications'
import { listNotifications, markNotificationRead, listNotificationSettings, updateNotificationSetting } from '../api'

const TYPE_LABEL = {
  account_apply: '账号申请',
  account_approved: '账号通过',
  account_rejected: '账号驳回',
  password_reset: '密码重置',
  followup_viewed: '跟单被查看',
  project_pending: '项目待审批',
  project_approved: '项目通过',
  project_rejected: '项目驳回',
  system_announcement: '系统公告',
}

const TYPE_ICON = {
  account_apply: '👤',
  account_approved: '✅',
  account_rejected: '❌',
  password_reset: '🔑',
  followup_viewed: '👀',
  project_pending: '📋',
  project_approved: '✅',
  project_rejected: '❌',
  system_announcement: '📣',
}

export default function Notifications() {
  const { unreadCount, markRead, markAllRead } = useNotificationStore()
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [settings, setSettings] = useState([])
  const [settingsLoaded, setSettingsLoaded] = useState(false)

  const load = async (p = page, f = filter) => {
    setLoading(true)
    try {
      const params = { page: p, page_size: pageSize }
      if (f === 'unread') params.only_unread = true
      const r = await listNotifications(params)
      setItems(r.data.items || [])
      setTotal(r.data.total || 0)
    } catch (_) {}
    setLoading(false)
  }

  const loadSettings = async () => {
    if (settingsLoaded) return
    try {
      const r = await listNotificationSettings()
      setSettings(r.data || [])
      setSettingsLoaded(true)
    } catch (_) {}
  }

  useEffect(() => { load(1, filter); setPage(1) }, [filter])
  useEffect(() => { load(page, filter) }, [page])

  const handleItem = async (n) => {
    if (!n.is_read) {
      await markRead(n.id)
      setItems(items.map(it => it.id === n.id ? Object.assign({}, it, { is_read: true }) : it))
    }
  }

  const updateSetting = async (type, field, value) => {
    try {
      const payload = {}
      payload[field] = value
      await updateNotificationSetting(type, payload)
      setSettings(settings.map(s => s.type === type ? Object.assign({}, s, { [field]: value }) : s))
    } catch (_) {}
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">🔔 通知中心</h2>
        <button
          onClick={async () => { await markAllRead(); load(page, filter) }}
          disabled={unreadCount === 0}
          className={"text-sm px-4 py-1.5 rounded " + (unreadCount === 0 ? 'bg-gray-200 text-gray-400 cursor-not-allowed' : 'bg-blue-500 text-white hover:bg-blue-600')}
        >
          全部标记已读 {unreadCount > 0 && '(' + unreadCount + ')'}
        </button>
      </div>

      {/* 推送偏好 - 折叠面板 */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <button
          onClick={() => { const will = !settingsLoaded; if (will) loadSettings() }}
          className="w-full px-4 py-3 text-left font-semibold text-gray-700 hover:bg-gray-50 flex justify-between items-center"
        >
          <span>📡 推送偏好 (站内 / 短信 / 钉钉工作通知)</span>
          <span className="text-xs text-gray-400">{settingsLoaded ? (settings.some(s => s.sms || s.dingtalk) ? '已配置部分外推' : '当前仅站内通知') : '点击展开'}</span>
        </button>
        {settingsLoaded && (
          <div className="border-t border-gray-200 p-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-100">
                  <th className="py-2 px-3">事件类型</th>
                  <th className="py-2 px-3 text-center">站内</th>
                  <th className="py-2 px-3 text-center">短信</th>
                  <th className="py-2 px-3 text-center">钉钉</th>
                </tr>
              </thead>
              <tbody>
                {settings.map(s => (
                  <tr key={s.type} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-3">{TYPE_ICON[s.type] || '🔔'} {TYPE_LABEL[s.type] || s.type}</td>
                    {['in_app', 'sms', 'dingtalk'].map(field => (
                      <td key={field} className="py-2 px-3 text-center">
                        <input
                          type="checkbox"
                          checked={!!s[field]}
                          onChange={(e) => updateSetting(s.type, field, e.target.checked)}
                          className="w-4 h-4 cursor-pointer"
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-400 mt-2">
              短信/钉钉渠道需在「系统管理 → 通道配置」中配置密钥(仅管理员可见)。
            </p>
          </div>
        )}
      </div>

      {/* 筛选 */}
      <div className="flex gap-2 items-center">
        {[
          { v: 'all', l: '全部' },
          { v: 'unread', l: '未读' },
        ].map(t => (
          <button
            key={t.v}
            onClick={() => setFilter(t.v)}
            className={"px-3 py-1 rounded text-sm " + (filter === t.v ? 'bg-blue-500 text-white' : 'bg-white text-gray-700 border border-gray-200 hover:bg-gray-50')}
          >{t.l}</button>
        ))}
        <span className="text-xs text-gray-400 ml-2">共 {total} 条</span>
        {loading && <span className="text-xs text-gray-400">加载中...</span>}
      </div>

      {/* 列表 */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {(!items || items.length === 0) && !loading && (
          <div className="px-6 py-16 text-center text-gray-400">
            <div className="text-4xl mb-2">🔕</div>
            暂无通知
          </div>
        )}
        {items.map(n => (
          <div
            key={n.id}
            onClick={() => handleItem(n)}
            className={"px-5 py-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 flex gap-3 transition " + (n.is_read ? '' : 'bg-blue-50/50')}
          >
            <span className="text-2xl shrink-0">{TYPE_ICON[n.type] || '🔔'}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline justify-between gap-3">
                <span className={"text-sm " + (n.is_read ? 'text-gray-700' : 'text-gray-900 font-bold')}>{n.title}</span>
                <span className="text-xs text-gray-400 shrink-0">{(n.created_at || '').replace('T', ' ').slice(0, 16)}</span>
              </div>
              {n.content && <div className="text-sm text-gray-600 mt-1 whitespace-pre-wrap">{n.content}</div>}
              <div className="text-xs text-gray-400 mt-1.5 flex items-center gap-2">
                <span className="px-2 py-0.5 bg-gray-100 rounded">{TYPE_LABEL[n.type] || n.type}</span>
                {!n.is_read && <span className="text-red-500">● 未读</span>}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 分页 */}
      {total > pageSize && (
        <div className="flex justify-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
            className={"px-3 py-1 rounded text-sm " + (page <= 1 ? 'bg-gray-100 text-gray-400' : 'bg-white border border-gray-200 hover:bg-gray-50')}
          >上一页</button>
          <span className="px-3 py-1 text-sm text-gray-600">{page} / {Math.ceil(total / pageSize)}</span>
          <button
            disabled={page >= Math.ceil(total / pageSize)}
            onClick={() => setPage(page + 1)}
            className={"px-3 py-1 rounded text-sm " + (page >= Math.ceil(total / pageSize) ? 'bg-gray-100 text-gray-400' : 'bg-white border border-gray-200 hover:bg-gray-50')}
          >下一页</button>
        </div>
      )}
    </div>
  )
}