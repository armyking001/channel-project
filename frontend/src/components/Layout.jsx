import { useState, useRef, useEffect } from 'react'
import { Outlet, Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import ChangePasswordModal from './ChangePasswordModal'

export default function Layout() {
  const { user, setAuth, logout } = useAuthStore()
  const navigate = useNavigate()

  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showChangePwd, setShowChangePwd] = useState(false)
  const menuRef = useRef(null)

  // 每次进入页面都向后端校验当前登录账号（防止 localStorage 缓存与 token 不一致）
  useEffect(() => {
    let cancelled = false
    async function refreshMe() {
      const token = localStorage.getItem('token')
      if (!token) return
      try {
        const { getMe } = await import('../api')
        const r = await getMe()
        if (cancelled) return
        // 与 store 中现有 user 对比，不一致则同步（可能是另 tab 切换了账号）
        const fresh = r.data
        const cur = useAuthStore.getState().user
        if (!cur || cur.id !== fresh.id || cur.role !== fresh.role) {
          setAuth(fresh, token)
        }
      } catch (e) {
        // 401 时 axios 拦截器会跳登录页；其他错误忽略
        console.warn('[Layout] refreshMe failed:', e?.response?.status, e?.message)
      }
    }
    refreshMe()
    return () => { cancelled = true }
  }, [setAuth])

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
  const canApprove = ['admin', 'important'].includes(user?.role)
  const isAdmin = user?.role === 'admin'
  const isArchive = user?.role === 'archive'

  return (
    <div className="min-h-screen flex">
      {/* 侧边栏 */}
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-4 border-b border-gray-700 flex items-center gap-3">
          {/* 公司 Logo:深捷科技,与系统标题横排 */}
          <img
            src="/admin/logo.png?v=20260804"
            alt="深捷科技"
            className="h-10 w-auto object-contain shrink-0 select-none"
            draggable={false}
          />
          <div className="min-w-0 flex-1">
            <h1 className="text-sm font-bold leading-tight">项目管理系统V2.0</h1>
            <p className="text-xs text-gray-400 mt-0.5 truncate">{user?.real_name} · {roleLabel[user?.role] || ''}</p>
          </div>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <Link to="/projects" className="block px-4 py-2 rounded hover:bg-gray-700 transition">
            📋 项目列表
          </Link>
          {canApprove && (
            <Link to="/approvals" className="block px-4 py-2 rounded hover:bg-gray-700 transition">
              ✅ 审批管理
            </Link>
          )}
          <Link to="/project-followups" className="block px-4 py-2 rounded hover:bg-gray-700 transition">
            📈 项目跟单
          </Link>
          <Link to="/reports" className="block px-4 py-2 rounded hover:bg-gray-700 transition">
            📊 报表管理
          </Link>
          {isAdmin && (
            <Link to="/file-storage" className="block px-4 py-2 rounded hover:bg-gray-700 transition">
              🗂️ 存储区域
            </Link>
          )}
          {isAdmin && (
            <Link to="/admin/users" className="block px-4 py-2 rounded hover:bg-gray-700 transition">
              👥 用户管理
            </Link>
          )}
          {isAdmin && (
            <Link to="/admin/audit" className="block px-4 py-2 rounded hover:bg-gray-700 transition">
              📜 审计记录
            </Link>
          )}
          {isAdmin && (
            <Link to="/admin/forms" className="block px-4 py-2 rounded hover:bg-gray-700 transition">
              📐 表单管理
            </Link>
          )}
        </nav>
      </aside>

      {/* 主内容 + 顶栏 */}
      <div className="flex-1 flex flex-col">
        {/* 顶栏:右上角用户菜单 */}
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex justify-end items-center">
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-2 px-3 py-1.5 rounded hover:bg-gray-100 transition"
            >
              <span className="text-sm text-gray-700">
                <span className="font-medium">{user?.real_name}</span>
                <span className="text-gray-500 ml-1">({roleLabel[user?.role] || ''})</span>
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

      {/* 修改密码弹窗 */}
      {showChangePwd && (
        <ChangePasswordModal onClose={() => setShowChangePwd(false)} />
      )}
    </div>
  )
}