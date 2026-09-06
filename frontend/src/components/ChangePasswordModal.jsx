import { useState } from 'react'
import { changePassword } from '../api'
import { useAuthStore } from '../stores/auth'

export default function ChangePasswordModal({ onClose }) {
  const { user, logout } = useAuthStore()
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [showOld, setShowOld] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [ok, setOk] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErr('')
    if (!oldPwd) { setErr('请输入旧密码'); return }
    if (!newPwd || newPwd.length < 6) { setErr('新密码至少 6 位'); return }
    if (newPwd !== confirmPwd) { setErr('两次输入的新密码不一致'); return }
    if (oldPwd === newPwd) { setErr('新密码不能与旧密码相同'); return }

    setLoading(true)
    try {
      await changePassword({
        old_password: oldPwd,
        new_password: newPwd,
        confirm_password: confirmPwd,
      })
      setOk(true)
      // 2 秒后自动退出登录,跳转到登录页
      setTimeout(() => {
        logout()
        window.location.href = '/login'
      }, 2000)
    } catch (e) {
      const msg = e?.response?.data?.detail || '修改失败,请稍后重试'
      setErr(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-800">🔑 修改密码</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            disabled={loading || ok}
          >×</button>
        </div>

        {ok ? (
          <div className="px-6 py-8 text-center">
            <div className="text-green-600 text-5xl mb-4">✓</div>
            <p className="text-gray-800 text-lg font-medium">密码修改成功!</p>
            <p className="text-gray-500 text-sm mt-2">即将退出登录,请使用新密码重新登录...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
            <div className="text-sm text-gray-600 bg-blue-50 border border-blue-200 rounded px-3 py-2">
              当前账号: <span className="font-medium text-gray-800">{user?.real_name} ({user?.username})</span>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                旧密码
              </label>
              <div className="relative">
                <input
                  type={showOld ? 'text' : 'password'}
                  value={oldPwd}
                  onChange={(e) => setOldPwd(e.target.value)}
                  disabled={loading}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  placeholder="请输入当前密码"
                />
                <button
                  type="button"
                  onClick={() => setShowOld(!showOld)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm px-1"
                >
                  {showOld ? '🙈' : '👁'}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                新密码
              </label>
              <div className="relative">
                <input
                  type={showNew ? 'text' : 'password'}
                  value={newPwd}
                  onChange={(e) => setNewPwd(e.target.value)}
                  disabled={loading}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  placeholder="至少 6 位"
                />
                <button
                  type="button"
                  onClick={() => setShowNew(!showNew)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm px-1"
                >
                  {showNew ? '🙈' : '👁'}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                确认新密码
              </label>
              <div className="relative">
                <input
                  type={showConfirm ? 'text' : 'password'}
                  value={confirmPwd}
                  onChange={(e) => setConfirmPwd(e.target.value)}
                  disabled={loading}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  placeholder="再次输入新密码"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm px-1"
                >
                  {showConfirm ? '🙈' : '👁'}
                </button>
              </div>
            </div>

            {err && (
              <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">
                {err}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={loading}
                className="flex-1 px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? '提交中...' : '确认修改'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}