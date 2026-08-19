import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { login, applyAccount } from '../api'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showApply, setShowApply] = useState(false)
  const [applyName, setApplyName] = useState('')
  const [applyResult, setApplyResult] = useState(null)
  const [applyError, setApplyError] = useState('')
  const [applying, setApplying] = useState(false)
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('username', username)
      formData.append('password', password)
      const res = await login(formData)
      setAuth(res.data.user, res.data.access_token)
      navigate('/projects')
    } catch (err) {
      setError(err.response?.data?.detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = async (e) => {
    e?.preventDefault?.()
    setApplyError('')
    setApplyResult(null)
    if (!applyName.trim()) {
      setApplyError('请输入姓名')
      return
    }
    setApplying(true)
    try {
      const res = await applyAccount(applyName.trim())
      setApplyResult(res.data)
    } catch (err) {
      setApplyError(err.response?.data?.detail || '申请失败')
    } finally {
      setApplying(false)
    }
  }

  const closeApply = () => {
    setShowApply(false)
    setApplyName('')
    setApplyResult(null)
    setApplyError('')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="relative bg-white p-8 rounded-lg shadow-md w-[480px] pb-12">
        {/* 顶部 Logo + 标题 */}
        <div className="flex items-center justify-center mb-6 gap-4">
          <img src="/admin/logo_login.png?v=20260801" alt="深捷科技"
               style={{ width: '128px', height: '68px', transform: 'translateY(-2px)' }}
               className="object-contain flex-shrink-0" />
          <h1 className="text-[29px] font-bold text-gray-800 whitespace-nowrap">项目管理系统V2.0</h1>
        </div>
        {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">账号 / 姓名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="请输入账号或姓名"
              required
            />
          </div>
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-1">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="请输入密码"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {loading ? '登录中...' : '登录'}
          </button>
          {/* 申请账号链接 */}
          <div className="mt-3 text-center text-sm text-gray-600">
            还没有账号？
            <button
              type="button"
              onClick={() => setShowApply(true)}
              className="ml-1 text-blue-600 hover:text-blue-800 hover:underline font-medium"
            >
              申请账号
            </button>
          </div>
          {/* 底部署名 —— 贴近卡片底部 */}
          <div className="absolute bottom-2 right-3 text-xs text-gray-400">
            by 信息化部 王军
          </div>
        </form>
      </div>

      {/* 申请账号 Modal */}
      {showApply && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={closeApply}>
          <div
            className="bg-white rounded-lg shadow-xl w-[420px] p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-800">申请账号</h2>
              <button
                type="button"
                onClick={closeApply}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >×</button>
            </div>

            {!applyResult ? (
              <form onSubmit={handleApply}>
                <div className="mb-3 text-sm text-gray-600 leading-relaxed">
                  请输入您的<strong>真实姓名</strong>，系统会自动生成账号。
                  <br />
                  <span className="text-xs text-gray-500">
                    生成规则：<strong>名</strong>的拼音首字母 + <strong>姓</strong>的全拼（如 张三 → szhang）
                  </span>
                </div>
                {applyError && (
                  <div className="bg-red-50 text-red-600 p-2 rounded mb-3 text-sm">{applyError}</div>
                )}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">姓名</label>
                  <input
                    type="text"
                    value={applyName}
                    onChange={(e) => setApplyName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="例如：张三"
                    autoFocus
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={closeApply}
                    className="px-4 py-2 text-gray-600 hover:text-gray-800"
                  >取消</button>
                  <button
                    type="submit"
                    disabled={applying}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    {applying ? '提交中...' : '提交申请'}
                  </button>
                </div>
              </form>
            ) : (
              <div>
                <div className="bg-green-50 text-green-700 p-3 rounded mb-4 text-sm">
                  {applyResult.message}
                </div>
                <div className="bg-gray-50 p-4 rounded mb-4 text-sm">
                  <div className="mb-2"><span className="text-gray-500">姓名：</span><strong>{applyResult.real_name}</strong></div>
                  <div className="mb-2"><span className="text-gray-500">账号：</span><strong className="text-blue-600 text-base">{applyResult.username}</strong></div>
                  {applyResult.initial_password && (
                    <div className="mb-2">
                      <span className="text-gray-500">初始密码：</span>
                      <strong className="text-red-600 text-base font-mono select-all">{applyResult.initial_password}</strong>
                    </div>
                  )}
                  <div><span className="text-gray-500">状态：</span><span className="text-orange-600">待审核</span></div>
                </div>
                <div className="text-xs text-gray-500 mb-4 leading-relaxed">
                  {applyResult.initial_password
                    ? <>请<span className="text-red-600 font-medium">妥善保存初始密码</span>，管理员审核通过后即可用该账号与密码登录系统。</>
                    : <>请将账号告知系统管理员，由管理员在「用户管理」处为您设置初始密码并启用账号。</>}
                </div>
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={closeApply}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >我知道了</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
