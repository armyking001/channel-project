import { useState, useRef, useEffect } from 'react'
import { Outlet, Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { useNotificationStore } from '../stores/notifications'
import ChangePasswordModal from './ChangePasswordModal'
import NotificationBell from './NotificationBell'

export default function Layout() {
  const { user, setAuth, logout } = useAuthStore()
  const navigate = useNavigate()

  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showChangePwd, setShowChangePwd] = useState(false)
  const menuRef = useRef(null)

  // 每次进入页面都向后端校验当前登录账号(防止 localStorage 缓存与 token 不一致)
  useEffect(() => {
    let cancelled = false
    async function refreshMe() {
      const token = localStorage.getItem('token')
      if (!token) return
      try {
        const { getMe } = await import('../api')
        const r = await getMe()
        if (cancelled) return
        const fresh = r.data
        const cur = useAuthStore.getState().user
        if (!cur || cur.id !== fresh.id || cur.role !== fresh.role) {
          setAuth(fresh, token)
        }
      } catch (e) {}
    }
    refreshMe()
    return () => { cancelled = true }
  }, [setAuth])

  // 建立/重连 WebSocket(每次登录态变化都重建)
  useEffect(() => {
    if (!user) return
    const ns = useNotificationStore.getState()
    ns.init()
    ns.refreshUnread()
    ns.refreshRecent()
    return () => {
      // 用户切换/登出时关闭 - 但 Layout 卸载一般只在登出,留待 close() 显式调用
    }
  }, [user?.id])

  useEffect(() => {
    function onClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setShowUserMenu(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const handleLogout = () => {
    setShowUserMenu(false)
    useNotificationStore.getState().close()
    logout()
    navigate('/login')
  }

  const handleChangePwd = () => {
    setShowUserMenu(false)
    setShowChangePwd(true)
  }

  const roleLabel = {
    admin: '系统管理员',
    important: '重要账号',
    normal: '普通账号',
    archive: '档案管理'
  }
  const canApprove = ['admin', 'important'].includes(user && user.role)
  const isAdmin = user && user.role === 'admin'
  const isArchive = user && user.role === 'archive'

  return (
    <div className="min-h-screen flex">
      {/* 侧边栏 */}
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-4 border-b border-gray-700 flex items-center gap-3">
          <img
            src="/admin/logo.png?v=20260804"
            alt="logo"
            className="h-8 w-auto object-contain shrink-0 select-none"
            draggable={false}
          />
          <div className="min-w-0 flex-1">
            <h1 className="text-sm font-bold leading-tight whitespace-nowrap">销售项目管理系统V2.0</h1>
            <p className="text-xs text-gray-400 mt-0.5 truncate">{(user && user.real_name) + ' \u00b7 ' + (roleLabel[(user && user.role)] || '')}</p>
          </div>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <Link to="/projects" className="block px-4 py-2 rounded hover:bg-gray-700 transition">📋 项目列表</Link>
          {canApprove && (
            <Link to="/approvals" className="block px-4 py-2 rounded hover:bg-gray-700 transition">✅ 审批管理</Link>
          )}
          {!isArchive && (
            <Link to="/project-followups" className="block px-4 py-2 rounded hover:bg-gray-700 transition">📈 项目跟单</Link>
          )}
          <Link to="/reports" className="block px-4 py-2 rounded hover:bg-gray-700 transition">📊 AI报表</Link>
          {isAdmin && (
            <Link to="/file-storage" className="block px-4 py-2 rounded hover:bg-gray-700 transition">🗂️ 存储区域</Link>
          )}
          {isAdmin && (
            <Link to="/admin/users" className="block px-4 py-2 rounded hover:bg-gray-700 transition">👥 用户管理</Link>
          )}
          {isAdmin && (
            <Link to="/admin/forms" className="block px-4 py-2 rounded hover:bg-gray-700 transition">📐 表单管理</Link>
          )}
          {isAdmin && (
            <Link to="/admin/audit" className="block px-4 py-2 rounded hover:bg-gray-700 transition">📜 审计记录</Link>
          )}
          {isAdmin && (
            <Link to="/admin/notifications" className="block px-4 py-2 rounded hover:bg-gray-700 transition">📣 通知管理</Link>
          )}
          <Link to="/notifications" className="block px-4 py-2 rounded hover:bg-gray-700 transition">🔔 通知中心</Link>
        </nav>
      </aside>

      {/* 主内容 + 顶栏 */}
      <div className="flex-1 flex flex-col">
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex justify-end items-center gap-3">
          {/* 通知铃铛 */}
          <NotificationBell />
          {/* 用户菜单 */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-2 px-3 py-1.5 rounded hover:bg-gray-100 transition"
            >
              <span className="text-sm text-gray-700">
                <span className="font-medium">{(user && user.real_name) || ''}</span>
                <span className="text-gray-500 ml-1">{(roleLabel[(user && user.role)] || '')}</span>
              </span>
              <span className="text-gray-400 text-xs">▼</span>
            </button>
            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50 overflow-hidden">
                <button
                  onClick={handleChangePwd}
                  className="w-full px-4 py-2.5 text-left text-sm hover:bg-gray-50 transition flex items-center gap-2"
                >
                  <span>🔑</span>
                  <span>修改密码</span>
                </button>
                <div className="border-t border-gray-100"></div>
                <button
                  onClick={handleLogout}
                  className="w-full px-4 py-2.5 text-left text-sm hover:bg-red-50 text-red-600 transition flex items-center gap-2"
                >
                  <span>🚪</span>
                  <span>退出登录</span>
                </button>
              </div>
            )}
          </div>
        </header>
        <main className="flex-1 p-6 overflow-auto bg-gray-50">
          <Outlet />
        </main>
      </div>

      {showChangePwd && (
        <ChangePasswordModal onClose={() => setShowChangePwd(false)} />
      )}
    </div>
  )
}
