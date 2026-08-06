import { Outlet, Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
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
            <h1 className="text-sm font-bold leading-tight">渠道项目管理系统</h1>
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
          <Link to="/reports" className="block px-4 py-2 rounded hover:bg-gray-700 transition">
            📊 报表管理
          </Link>
          {isAdmin && (
            <Link to="/file-storage" className="block px-4 py-2 rounded hover:bg-gray-700 transition">
              📁 文件管理
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
        </nav>
        <div className="p-4 border-t border-gray-700">
          <button onClick={handleLogout} className="w-full px-4 py-2 text-left rounded hover:bg-gray-700 transition text-red-400">
            退出登录
          </button>
        </div>
      </aside>

      {/* 主内容 */}
      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
