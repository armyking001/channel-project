import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useNotificationStore } from '../stores/notifications'

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

function timeAgo(iso) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  const diff = (Date.now() - t) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前'
  return Math.floor(diff / 86400) + ' 天前'
}

export default function NotificationBell() {
  const navigate = useNavigate()
  const { unreadCount, recent, markRead, markAllRead } = useNotificationStore()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const handleClick = (n) => {
    markRead(n.id)
    setOpen(false)
    if (n.target_type === 'user') {
      if (n.type === 'account_apply') navigate('/admin/users')
    } else if (n.target_type === 'followup_project') {
      navigate('/project-followups?project_id=' + n.target_id)
    } else if (n.target_type === 'project') {
      if (n.type === 'project_pending') navigate('/approvals')
      else navigate('/projects')
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded hover:bg-gray-100 transition"
        title="通知中心"
      >
        <span className="text-lg">🔔</span>
        {unreadCount > 0 && (
          <span className="absolute top-0.5 right-0.5 min-w-[18px] h-[18px] px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center leading-none">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-96 bg-white border border-gray-200 rounded-lg shadow-lg z-50 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100 flex justify-between items-center bg-gray-50">
            <span className="font-semibold text-sm">通知中心</span>
            <button
              onClick={() => markAllRead()}
              disabled={unreadCount === 0}
              className={"text-xs " + (unreadCount === 0 ? 'text-gray-400 cursor-not-allowed' : 'text-blue-600 hover:underline')}
            >
              全部已读
            </button>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {(!recent || recent.length === 0) && (
              <div className="px-6 py-12 text-center text-gray-400 text-sm">
                <div className="text-3xl mb-2">🔕</div>
                暂无通知
              </div>
            )}
            {recent && recent.map((n) => (
              <button
                key={n.id}
                onClick={() => handleClick(n)}
                className={"w-full px-4 py-3 text-left border-b border-gray-100 hover:bg-gray-50 transition flex gap-2 " + (n.is_read ? '' : 'bg-blue-50/40')}
              >
                <span className="text-xl shrink-0">{TYPE_ICON[n.type] || '🔔'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className={"text-sm truncate " + (n.is_read ? 'text-gray-700' : 'text-gray-900 font-semibold')}>{n.title}</span>
                    {!n.is_read && (
                      <span className="shrink-0 w-2 h-2 bg-red-500 rounded-full mt-1.5"></span>
                    )}
                  </div>
                  {n.content && (
                    <div className="text-xs text-gray-600 mt-0.5 line-clamp-2">{n.content}</div>
                  )}
                  <div className="text-[11px] text-gray-400 mt-1 flex justify-between">
                    <span>{TYPE_LABEL[n.type] || n.type}</span>
                    <span>{timeAgo(n.created_at)}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>

          <div className="px-4 py-2 border-t border-gray-100 bg-gray-50 text-center">
            <button
              onClick={() => { setOpen(false); navigate('/notifications') }}
              className="text-xs text-blue-600 hover:underline"
            >
              查看全部通知 →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}