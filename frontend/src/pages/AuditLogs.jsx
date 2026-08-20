import { useEffect, useState } from 'react'
import { getAuditLogs, exportAuditLogs } from '../api'
import { useAuthStore } from '../stores/auth'

const ACTION_LABELS = {
  'user.login': '登录',
  'user.logout': '登出',
  'user.create': '创建用户',
  'user.update': '编辑用户',
  'user.delete': '停用用户',
  'user.reset_password': '重置密码',
  'project.create': '创建项目',
  'project.update': '编辑项目',
  'project.delete': '删除项目',
  'project.submit': '提交项目',
  'project.approve': '审批通过',
  'project.reject': '审批驳回',
  'file.upload': '文件上传',
}

const ROLE_LABELS = {
  admin: '系统管理员',
  important: '重要账号',
  normal: '普通账号',
  archive: '档案管理',
}

const ACTION_OPTIONS = [
  { value: '', label: '全部操作' },
  { value: 'user.*', label: '— 用户类 —' },
  { value: 'user.login', label: '  登录' },
  { value: 'user.create', label: '  创建用户' },
  { value: 'user.update', label: '  编辑用户' },
  { value: 'user.delete', label: '  停用用户' },
  { value: 'user.reset_password', label: '  重置密码' },
  { value: 'project.*', label: '— 项目类 —' },
  { value: 'project.create', label: '  创建项目' },
  { value: 'project.update', label: '  编辑项目' },
  { value: 'project.delete', label: '  删除项目' },
  { value: 'project.submit', label: '  提交项目' },
  { value: 'project.approve', label: '  审批通过' },
  { value: 'project.reject', label: '  审批驳回' },
  { value: 'file.*', label: '— 文件类 —' },
  { value: 'file.upload', label: '  文件上传' },
]

function formatDetails(d) {
  if (!d) return '-'
  if (typeof d === 'string') {
    try {
      d = JSON.parse(d)
    } catch {
      return d
    }
  }
  if (typeof d === 'object') {
    return Object.entries(d)
      .map(([k, v]) => {
        if (typeof v === 'object' && v !== null) {
          return `${k}: ${JSON.stringify(v)}`
        }
        return `${k}: ${v}`
      })
      .join('； ')
  }
  return String(d)
}

function formatTime(s) {
  if (!s) return '-'
  // 后端返回的是 UTC ISO 字符串,加 Z 后浏览器会按本地时区解析
  // ISO 字符串若已含时区则直接解析,否则视为 UTC
  const iso = s.includes('Z') || /[+-]\d{2}:?\d{2}$/.test(s) ? s : (s + 'Z')
  return new Date(iso).toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' })
}

export default function AuditLogs() {
  const { user } = useAuthStore()
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState({
    action: '',
    target_type: '',
    username: '',
    start_date: '',
    end_date: '',
  })

  const canView = user?.role === 'admin'

  useEffect(() => {
    if (canView) loadLogs()
  }, [page, canView])

  const loadLogs = async () => {
    setLoading(true)
    try {
      const params = { page, page_size: pageSize, ...filters }
      Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
      const res = await getAuditLogs(params)
      setItems(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } catch (e) {
      alert('加载失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setPage(1)
    loadLogs()
  }

  const handleReset = () => {
    setFilters({ action: '', target_type: '', username: '', start_date: '', end_date: '' })
    setPage(1)
    setTimeout(loadLogs, 0)
  }

  const handleExport = async () => {
    try {
      const params = { ...filters }
      Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
      const res = await exportAuditLogs(params)
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `审计记录_${new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-')}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (e) {
      alert('导出失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  if (!canView) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        您没有权限查看审计记录
      </div>
    )
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-800">审计记录</h2>
        <button
          onClick={handleExport}
          className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition"
        >
          📥 导出 CSV
        </button>
      </div>

      {/* 搜索栏 */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">操作类型</label>
            <select
              value={filters.action}
              onChange={e => setFilters(f => ({ ...f, action: e.target.value }))}
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            >
              {ACTION_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">对象类型</label>
            <select
              value={filters.target_type}
              onChange={e => setFilters(f => ({ ...f, target_type: e.target.value }))}
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            >
              <option value="">全部</option>
              <option value="user">用户</option>
              <option value="project">项目</option>
              <option value="file">文件</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">操作人账号</label>
            <input
              type="text"
              value={filters.username}
              onChange={e => setFilters(f => ({ ...f, username: e.target.value }))}
              placeholder="模糊搜索"
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">开始日期</label>
            <input
              type="date"
              value={filters.start_date}
              onChange={e => setFilters(f => ({ ...f, start_date: e.target.value }))}
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">结束日期</label>
            <input
              type="date"
              value={filters.end_date}
              onChange={e => setFilters(f => ({ ...f, end_date: e.target.value }))}
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <button onClick={handleSearch} className="px-4 py-1.5 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700">
            🔍 搜索
          </button>
          <button onClick={handleReset} className="px-4 py-1.5 bg-gray-200 text-gray-700 rounded-md text-sm hover:bg-gray-300">
            重置
          </button>
        </div>
      </div>

      {/* 列表 */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">时间</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">操作人</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">角色</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">操作类型</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">对象</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">详情</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">IP</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {loading && (
              <tr><td colSpan={7} className="text-center py-8 text-gray-400">加载中...</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={7} className="text-center py-8 text-gray-400">暂无数据</td></tr>
            )}
            {!loading && items.map(it => (
              <tr key={it.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-xs text-gray-700 whitespace-nowrap">{formatTime(it.created_at)}</td>
                <td className="px-4 py-2 text-xs text-gray-700">
                  <div>{it.real_name || '-'}</div>
                  <div className="text-gray-400">@{it.username}</div>
                </td>
                <td className="px-4 py-2 text-xs text-gray-700">{ROLE_LABELS[it.role] || it.role || '-'}</td>
                <td className="px-4 py-2 text-xs">
                  <span className="px-2 py-0.5 rounded text-white text-xs" style={{
                    backgroundColor: it.action.startsWith('user') ? '#3b82f6'
                      : it.action.startsWith('project') ? '#10b981'
                      : it.action.startsWith('file') ? '#f59e0b' : '#6b7280'
                  }}>
                    {ACTION_LABELS[it.action] || it.action}
                  </span>
                </td>
                <td className="px-4 py-2 text-xs text-gray-700">
                  {it.target_type && (
                    <span className="text-gray-400">[{it.target_type}]</span>
                  )} {it.target_name || '-'}
                </td>
                <td className="px-4 py-2 text-xs text-gray-500 max-w-md truncate" title={formatDetails(it.details)}>
                  {formatDetails(it.details)}
                </td>
                <td className="px-4 py-2 text-xs text-gray-400">{it.ip_address || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <div>共 {total} 条</div>
        <div className="flex items-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            上一页
          </button>
          <span>第 {page} / {totalPages} 页</span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  )
}
