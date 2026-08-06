import { useState, useEffect } from 'react'
import { getUsers, createUser, updateUser, deleteUser, rejectUser, hardDeleteUser, resetPassword } from '../api'
import { useAuthStore } from '../stores/auth'

const ROLE_MAP = {
  admin: '系统管理员',
  important: '重要账号',
  normal: '普通账号',
  archive: '档案管理'
}
const ROLE_BADGE = {
  admin: 'bg-red-100 text-red-700',
  important: 'bg-blue-100 text-blue-700',
  normal: 'bg-gray-100 text-gray-700',
  archive: 'bg-amber-100 text-amber-700',
}

// 带眼睛图标的密码输入框
function PasswordInput({ value, onChange, placeholder = '请输入密码' }) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input
        type={show ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full border rounded px-3 py-2 pr-10"
      />
      <button
        type="button"
        onClick={() => setShow(s => !s)}
        title={show ? '隐藏密码' : '显示密码'}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 text-lg leading-none"
      >
        {show ? '🙈' : '👁'}
      </button>
    </div>
  )
}

// 用户状态徽章
// 优先级：is_rejected > is_active=False(PENDING) > is_active=False(已停用) > is_active=True(正常)
function StatusBadge({ user }) {
  if (user.is_rejected) {
    return <span className="px-2 py-1 rounded text-xs bg-gray-200 text-gray-700 font-medium">已驳回</span>
  }
  if (user.is_active) {
    return <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-700">正常</span>
  }
  if (user.username && user.username.startsWith('!PENDING_')) {
    return <span className="px-2 py-1 rounded text-xs bg-orange-100 text-orange-700 font-medium">待审批</span>
  }
  return <span className="px-2 py-1 rounded text-xs bg-red-100 text-red-700">已停用</span>
}

export default function UserManagement() {
  const { user: currentUser } = useAuthStore()
  const isAdmin = currentUser?.role === 'admin'
  const isArchive = currentUser?.role === 'archive'

  const [users, setUsers] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editUser, setEditUser] = useState(null)
  const [form, setForm] = useState({ username: '', password: '', real_name: '', role: 'normal', parent_id: '' })

  // 重置密码弹窗状态
  const [showResetPwd, setShowResetPwd] = useState(false)
  const [resetPwdTarget, setResetPwdTarget] = useState(null)
  const [resetPwdForm, setResetPwdForm] = useState({ pwd1: '', pwd2: '' })

  // 审批弹窗状态
  const [showApprove, setShowApprove] = useState(false)
  const [approveTarget, setApproveTarget] = useState(null)
  const [approveForm, setApproveForm] = useState({ pwd1: '', pwd2: '', role: 'normal', parent_id: '' })

  // 批量审批
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [showBatchApprove, setShowBatchApprove] = useState(false)
  const [batchForm, setBatchForm] = useState({ pwd: '', role: 'normal', parent_id: '' })
  const [batchProgress, setBatchProgress] = useState(null)  // { current, total, ok, fail, errors: [] }

  // 列表过滤
  const [filterTab, setFilterTab] = useState('all')  // all | active | pending | rejected | inactive

  const fetchUsers = async () => {
    const res = await getUsers(true)  // include_inactive=true，看全部用户（含待审批）
    setUsers(res.data)
  }

  useEffect(() => { fetchUsers() }, [])

  const openCreate = () => {
    setEditUser(null)
    setForm({ username: '', password: '', real_name: '', role: 'normal', parent_id: '' })
    setShowModal(true)
  }

  const openEdit = (u) => {
    setEditUser(u)
    setForm({ username: u.username, password: '', real_name: u.real_name, role: u.role, parent_id: u.parent_id || '' })
    setShowModal(true)
  }

  const handleSubmit = async () => {
    try {
      const data = { ...form, parent_id: form.parent_id || null }
      if (!data.password) delete data.password
      if (editUser) {
        await updateUser(editUser.id, data)
      } else {
        await createUser(data)
      }
      setShowModal(false)
      fetchUsers()
    } catch (err) {
      alert(err.response?.data?.detail || '操作失败')
    }
  }

  const handleDelete = async (u) => {
    const ok = confirm(`确认删除用户「${u.real_name} (${u.username})」？\n\n该用户将被标记为已停用，无法登录系统。\n该用户下的项目、审批记录等数据将保留。`)
    if (!ok) return
    try {
      const res = await deleteUser(u.id)
      alert(res.data?.message || '删除成功')
      fetchUsers()
    } catch (err) {
      const detail = err.response?.data?.detail || '删除失败'
      alert('删除失败: ' + detail)
    }
  }

  const openResetPwd = (u) => {
    setResetPwdTarget(u)
    setResetPwdForm({ pwd1: '', pwd2: '' })
    setShowResetPwd(true)
  }

  const closeResetPwd = () => {
    setShowResetPwd(false)
    setResetPwdTarget(null)
    setResetPwdForm({ pwd1: '', pwd2: '' })
  }

  const handleResetPwdSubmit = async () => {
    const { pwd1, pwd2 } = resetPwdForm
    if (!pwd1 || pwd1.length < 6) {
      alert('密码至少 6 位')
      return
    }
    if (pwd1 !== pwd2) {
      alert('两次输入的密码不一致')
      return
    }
    try {
      await resetPassword(resetPwdTarget.id, { new_password: pwd1 })
      alert('密码已重置')
      closeResetPwd()
    } catch (err) {
      alert(err.response?.data?.detail || '重置失败')
    }
  }

  // 打开审批弹窗
  const openApprove = (u) => {
    setApproveTarget(u)
    setApproveForm({
      pwd1: '',
      pwd2: '',
      role: 'normal',
      parent_id: '',
    })
    setShowApprove(true)
  }

  const closeApprove = () => {
    setShowApprove(false)
    setApproveTarget(null)
    setApproveForm({ pwd1: '', pwd2: '', role: 'normal', parent_id: '' })
  }

  // 提交审批：先设密码 + 改角色/上级，再激活
  const handleApproveSubmit = async () => {
    const { pwd1, pwd2, role, parent_id } = approveForm
    if (!pwd1 || pwd1.length < 6) {
      alert('请输入至少 6 位的初始密码')
      return
    }
    if (pwd1 !== pwd2) {
      alert('两次输入的密码不一致')
      return
    }
    try {
      // 1) 改角色/上级 + 去掉 PENDING 前缀 + 激活
      const cleanUsername = (approveTarget.username || '').replace(/^!PENDING_/, '')
      await updateUser(approveTarget.id, {
        username: cleanUsername,
        role,
        parent_id: parent_id || null,
        is_active: true,
      })
      // 2) 设初始密码
      await resetPassword(approveTarget.id, { new_password: pwd1 })
      alert(`账号 "${cleanUsername}" 审批通过！\n初始密码已设置，用户可登录。`)
      closeApprove()
      fetchUsers()
    } catch (err) {
      alert(err.response?.data?.detail || '审批失败')
    }
  }

  // 驳回申请：保留记录在"已驳回"Tab
  const handleReject = async (u) => {
    const ok = confirm(`确认驳回用户「${u.real_name} (${u.username})」的申请？\n该用户记录将保留在"已驳回"列表中，可随时彻底删除。`)
    if (!ok) return
    try {
      await rejectUser(u.id)
      alert('已驳回该申请')
      fetchUsers()
    } catch (err) {
      const detail = err.response?.data?.detail || '驳回失败'
      alert('驳回失败: ' + detail)
    }
  }

  // 彻底删除
  const handleHardDelete = async (u) => {
    const ok = confirm(`确认彻底删除用户「${u.real_name} (${u.username})」？\n该用户记录将从数据库中永久删除（不可恢复）。\n\n仅限"已停用/已驳回"用户。`)
    if (!ok) return
    try {
      const res = await hardDeleteUser(u.id)
      alert(res.data?.message || '已彻底删除')
      fetchUsers()
    } catch (err) {
      const detail = err.response?.data?.detail || '删除失败'
      alert('删除失败: ' + detail)
    }
  }

  // 多选：勾选/取消勾选单个
  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // 多选：当前 Tab 全选 / 全取消（所有 Tab 都生效）
  const toggleSelectAll = () => {
    const selectableList = filteredUsers.filter(u => u.id !== currentUser?.id)  // 不能选自己
    if (selectedIds.size === selectableList.length && selectableList.length > 0) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(selectableList.map(u => u.id)))
    }
  }

  // 清除选择（Tab 切换时调用）
  useEffect(() => { setSelectedIds(new Set()) }, [filterTab])

  // 批量审批
  const openBatchApprove = () => {
    if (selectedIds.size === 0) {
      alert('请先勾选要审批的账号')
      return
    }
    setBatchForm({ pwd: '', role: 'normal', parent_id: '' })
    setBatchProgress(null)
    setShowBatchApprove(true)
  }

  const closeBatchApprove = () => {
    setShowBatchApprove(false)
    setBatchProgress(null)
    setSelectedIds(new Set())
  }

  const handleBatchSubmit = async () => {
    const { pwd, role, parent_id } = batchForm
    if (!pwd || pwd.length < 6) {
      alert('请输入至少 6 位的初始密码（将应用于所有选中用户）')
      return
    }
    const targetUsers = users.filter(u => selectedIds.has(u.id))
    if (targetUsers.length === 0) {
      alert('选中的用户已不存在')
      closeBatchApprove()
      return
    }

    setBatchProgress({ current: 0, total: targetUsers.length, ok: 0, fail: 0, errors: [] })

    for (let i = 0; i < targetUsers.length; i++) {
      const u = targetUsers[i]
      try {
        const cleanUsername = (u.username || '').replace(/^!PENDING_/, '')
        await updateUser(u.id, {
          username: cleanUsername,
          role,
          parent_id: parent_id || null,
          is_active: true,
        })
        await resetPassword(u.id, { new_password: pwd })
        setBatchProgress(prev => ({ ...prev, current: i + 1, ok: (prev?.ok || 0) + 1 }))
      } catch (err) {
        const msg = err.response?.data?.detail || err.message || '未知错误'
        setBatchProgress(prev => ({
          ...prev,
          current: i + 1,
          fail: (prev?.fail || 0) + 1,
          errors: [...(prev?.errors || []), { name: u.real_name, username: u.username, error: msg }],
        }))
      }
    }

    fetchUsers()
  }

  // 通用批量操作：调用 fn(u) 逐个处理
  const runBatch = async (label, fn) => {
    const targetUsers = users.filter(u => selectedIds.has(u.id))
    if (targetUsers.length === 0) {
      alert('选中的用户已不存在')
      return
    }
    if (!confirm(`确认对 ${targetUsers.length} 个用户执行"${label}"操作？`)) return
    let ok = 0, fail = 0
    const errors = []
    for (const u of targetUsers) {
      try {
        await fn(u)
        ok++
      } catch (err) {
        fail++
        const msg = err.response?.data?.detail || err.message || '未知错误'
        errors.push({ name: u.real_name, username: u.username, error: msg })
      }
    }
    setSelectedIds(new Set())
    fetchUsers()
    let msg = `${label}：成功 ${ok}，失败 ${fail}`
    if (errors.length > 0) {
      msg += '\n\n失败明细：\n' + errors.map(e => `  ${e.name}(${e.username}): ${e.error}`).join('\n')
    }
    alert(msg)
  }

  // 批量驳回（仅待审批 Tab）
  const handleBatchReject = () => runBatch('批量驳回', u => rejectUser(u.id))
  // 批量彻底删除（已驳回 / 已停用 Tab）
  const handleBatchHardDelete = () => runBatch('批量彻底删除', u => hardDeleteUser(u.id))
  // 批量停用（正常 Tab）
  const handleBatchDeactivate = () => runBatch('批量停用', u => deleteUser(u.id))

  // 还原用户：恢复 is_active=True + 清理 __del_ 后缀恢复原 username
  const handleRestore = async (u) => {
    const ok = confirm(`确认还原用户「${u.real_name}」？\n还原后账号将恢复为正常状态，可登录系统。`)
    if (!ok) return
    try {
      const base = (u.username || '').replace(/__del_\d+$/, '')
      await updateUser(u.id, { is_active: true, username: base })
      alert('还原成功，账号已恢复正常')
      fetchUsers()
    } catch (err) {
      const detail = err.response?.data?.detail || '还原失败'
      alert('还原失败: ' + detail)
    }
  }
  // 批量还原（已停用 Tab）
  const handleBatchRestore = () => runBatch('批量还原', async (u) => {
    const base = (u.username || '').replace(/__del_\d+$/, '')
    await updateUser(u.id, { is_active: true, username: base })
  })

  const importantUsers = users.filter(u => u.role === 'important' || u.role === 'archive' || u.role === 'admin')

  // 过滤后的用户
  const filteredUsers = users.filter(u => {
    if (filterTab === 'all') return true
    if (filterTab === 'pending') return !u.is_active && !u.is_rejected && u.username && u.username.startsWith('!PENDING_')
    if (filterTab === 'rejected') return u.is_rejected === true
    if (filterTab === 'active') return u.is_active
    if (filterTab === 'inactive') return !u.is_active && !u.is_rejected && (!u.username || !u.username.startsWith('!PENDING_'))
    return true
  })

  const pendingCount = users.filter(u => !u.is_active && !u.is_rejected && u.username && u.username.startsWith('!PENDING_')).length
  const activeCount = users.filter(u => u.is_active).length
  const rejectedCount = users.filter(u => u.is_rejected).length
  const inactiveCount = users.filter(u => !u.is_active && !u.is_rejected && (!u.username || !u.username.startsWith('!PENDING_'))).length

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">用户管理</h2>
          {!isAdmin && isArchive && (
            <p className="text-sm text-gray-500 mt-1">档案管理账号：只读权限，无法编辑用户</p>
          )}
        </div>
        {isAdmin && (
          <button onClick={openCreate} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
            新建用户
          </button>
        )}
      </div>

      {/* Tabs */}
      {isAdmin && (
        <div className="flex gap-1 mb-4 border-b">
          <button
            onClick={() => setFilterTab('all')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition ${filterTab === 'all' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            全部 ({users.length})
          </button>
          <button
            onClick={() => setFilterTab('active')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition ${filterTab === 'active' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            正常 ({activeCount})
          </button>
          <button
            onClick={() => setFilterTab('pending')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition flex items-center gap-1 ${filterTab === 'pending' ? 'border-orange-500 text-orange-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            待审批 ({pendingCount})
            {pendingCount > 0 && (
              <span className="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 min-w-[18px] text-center">{pendingCount}</span>
            )}
          </button>
          <button
            onClick={() => setFilterTab('rejected')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition ${filterTab === 'rejected' ? 'border-gray-600 text-gray-800' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            已驳回 ({rejectedCount})
          </button>
          <button
            onClick={() => setFilterTab('inactive')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition ${filterTab === 'inactive' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            已停用 ({inactiveCount})
          </button>
        </div>
      )}

      <div className="bg-white rounded shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              {isAdmin && (
                <th className="px-3 py-3 text-center w-10">
                  <input
                    type="checkbox"
                    checked={filteredUsers.filter(u => u.id !== currentUser?.id).length > 0
                      && selectedIds.size === filteredUsers.filter(u => u.id !== currentUser?.id).length}
                    onChange={toggleSelectAll}
                    className="w-4 h-4 cursor-pointer"
                  />
                </th>
              )}
              <th className="px-4 py-3 text-left">账号</th>
              <th className="px-4 py-3 text-left">姓名</th>
              <th className="px-4 py-3 text-left">角色</th>
              <th className="px-4 py-3 text-left">上级</th>
              <th className="px-4 py-3 text-left">状态</th>
              <th className="px-4 py-3 text-left">创建时间</th>
              {isAdmin && <th className="px-4 py-3 text-center">操作</th>}
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map(u => {
              const isPending = !u.is_active && !u.is_rejected && u.username && u.username.startsWith('!PENDING_')
              const isRejected = u.is_rejected === true
              const isInactive = !u.is_active && !u.is_rejected && (!u.username || !u.username.startsWith('!PENDING_'))
              const isSelected = selectedIds.has(u.id)
              const canSelect = u.id !== currentUser?.id
              return (
                <tr key={u.id} className={`border-b hover:bg-gray-50 ${isPending ? 'bg-orange-50/40' : ''} ${isRejected ? 'bg-gray-50' : ''} ${isInactive ? 'bg-red-50/30' : ''} ${isSelected ? 'bg-blue-50' : ''}`}>
                  {isAdmin && (
                    <td className="px-3 py-3 text-center">
                      {canSelect && (
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(u.id)}
                          className="w-4 h-4 cursor-pointer"
                        />
                      )}
                    </td>
                  )}
                  <td className="px-4 py-3 font-mono">
                    {u.username && u.username.startsWith('!PENDING_')
                      ? <span className="text-orange-600">{u.username.replace('!PENDING_', '')}</span>
                      : u.username && u.username.includes('__del_')
                        ? <span className="text-gray-500">{u.username.replace(/__del_\d+$/, '')}</span>
                        : u.username}
                  </td>
                  <td className="px-4 py-3">{u.real_name}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${ROLE_BADGE[u.role] || 'bg-gray-100 text-gray-700'}`}>
                      {ROLE_MAP[u.role] || u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {u.parent_id ? users.find(x => x.id === u.parent_id)?.real_name || '-' : '-'}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge user={u} />
                  </td>
                  <td className="px-4 py-3 text-gray-500">{new Date(u.created_at).toLocaleDateString()}</td>
                  {isAdmin && (
                    <td className="px-4 py-3 text-center whitespace-nowrap">
                      {isPending ? (
                        <>
                          <button onClick={() => openApprove(u)} className="text-green-600 hover:underline mr-3 font-medium">通过</button>
                          <button onClick={() => handleReject(u)} className="text-red-600 hover:underline font-medium">驳回</button>
                        </>
                      ) : isRejected ? (
                        <>
                          <button onClick={() => openEdit(u)} className="text-blue-600 hover:underline mr-3">编辑</button>
                          <button onClick={() => handleHardDelete(u)} className="text-red-600 hover:underline font-medium">删除</button>
                        </>
                      ) : isInactive ? (
                        <>
                          <button onClick={() => handleRestore(u)} className="text-green-600 hover:underline mr-3 font-medium">还原</button>
                          <button onClick={() => handleHardDelete(u)} className="text-red-600 hover:underline font-medium">删除</button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => openEdit(u)} className="text-blue-600 hover:underline mr-3">编辑</button>
                          <button onClick={() => openResetPwd(u)} className="text-orange-600 hover:underline mr-3">重置密码</button>
                          {u.id !== currentUser?.id && (
                            <button onClick={() => handleDelete(u)} className="text-red-600 hover:underline font-medium">停用</button>
                          )}
                        </>
                      )}
                    </td>
                  )}
                </tr>
              )
            })}
            {filteredUsers.length === 0 && (
              <tr><td colSpan={isAdmin ? 8 : 7} className="text-center text-gray-400 py-8">
                {filterTab === 'pending' ? '暂无待审批申请'
                  : filterTab === 'rejected' ? '暂无已驳回申请'
                  : '暂无用户'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 浮动批量操作栏（选中后从底部弹出） */}
      {isAdmin && selectedIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-white shadow-2xl rounded-full px-6 py-3 flex items-center gap-3 z-40 border">
          <span className="text-sm text-gray-700">已选 <strong className="text-blue-600">{selectedIds.size}</strong> 个</span>
          {/* 按当前 Tab 决定显示哪些操作按钮 */}
          {filterTab === 'pending' && (
            <>
              <button onClick={openBatchApprove} className="bg-green-600 text-white px-4 py-1.5 rounded-full hover:bg-green-700 text-sm font-medium">
                批量通过
              </button>
              <button onClick={handleBatchReject} className="bg-orange-500 text-white px-4 py-1.5 rounded-full hover:bg-orange-600 text-sm font-medium">
                批量驳回
              </button>
            </>
          )}
          {filterTab === 'rejected' && (
            <button onClick={handleBatchHardDelete} className="bg-red-700 text-white px-4 py-1.5 rounded-full hover:bg-red-800 text-sm font-medium">
              批量彻底删除
            </button>
          )}
          {filterTab === 'active' && (
            <button onClick={handleBatchDeactivate} className="bg-red-600 text-white px-4 py-1.5 rounded-full hover:bg-red-700 text-sm font-medium">
              批量停用
            </button>
          )}
          {filterTab === 'inactive' && (
            <>
              <button onClick={handleBatchRestore} className="bg-green-600 text-white px-4 py-1.5 rounded-full hover:bg-green-700 text-sm font-medium">
                批量还原
              </button>
              <button onClick={handleBatchHardDelete} className="bg-red-700 text-white px-4 py-1.5 rounded-full hover:bg-red-800 text-sm font-medium">
                批量删除
              </button>
            </>
          )}
          {filterTab === 'all' && (
            <span className="text-xs text-gray-500">切换到具体 Tab 进行批量操作</span>
          )}
          <button onClick={() => setSelectedIds(new Set())} className="text-gray-500 hover:text-gray-700 text-sm ml-2">
            取消选择
          </button>
        </div>
      )}

      {/* 审批弹窗 */}
      {showApprove && approveTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-[460px]">
            <h3 className="text-lg font-bold mb-1">审批账号</h3>
            <p className="text-sm text-gray-500 mb-4">
              申请人：<strong>{approveTarget.real_name}</strong>　账号：<strong className="text-orange-600 font-mono">{approveTarget.username.replace('!PENDING_', '')}</strong>
            </p>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">分配角色<span className="text-red-500 ml-1">*</span></label>
                <select value={approveForm.role} onChange={e => setApproveForm(f => ({ ...f, role: e.target.value }))}
                  className="w-full border rounded px-3 py-2">
                  <option value="normal">普通账号</option>
                  <option value="important">重要账号</option>
                  <option value="archive">档案管理</option>
                  <option value="admin">系统管理员</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">归属上级（重要账号及以下必选）</label>
                <select value={approveForm.parent_id} onChange={e => setApproveForm(f => ({ ...f, parent_id: e.target.value }))}
                  className="w-full border rounded px-3 py-2">
                  <option value="">无</option>
                  {importantUsers.filter(x => x.id !== approveTarget.id).map(x => (
                    <option key={x.id} value={x.id}>{x.real_name} ({ROLE_MAP[x.role]})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">初始密码<span className="text-red-500 ml-1">*</span></label>
                <PasswordInput
                  value={approveForm.pwd1}
                  onChange={e => setApproveForm(f => ({ ...f, pwd1: e.target.value }))}
                  placeholder="请输入初始密码（至少6位）"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">确认初始密码<span className="text-red-500 ml-1">*</span></label>
                <PasswordInput
                  value={approveForm.pwd2}
                  onChange={e => setApproveForm(f => ({ ...f, pwd2: e.target.value }))}
                  placeholder="请再次输入初始密码"
                />
                {approveForm.pwd2 && approveForm.pwd1 !== approveForm.pwd2 && (
                  <p className="text-xs text-red-500 mt-1">两次输入的密码不一致</p>
                )}
              </div>
              <div className="bg-yellow-50 border border-yellow-200 rounded p-2 text-xs text-yellow-800">
                提示：审批通过后，该账号将立即可登录，请妥善告知用户初始密码。
              </div>
            </div>
            <div className="flex justify-end space-x-2 mt-6">
              <button onClick={closeApprove} className="px-4 py-2 border rounded">取消</button>
              <button
                onClick={handleApproveSubmit}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                通过审批
              </button>
            </div>
          </div>
        </div>
      )}

      {showModal && isAdmin && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96">
            <h3 className="text-lg font-bold mb-4">{editUser ? '编辑用户' : '新建用户'}</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">账号</label>
                <input value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                  disabled={!!editUser} className="w-full border rounded px-3 py-2 disabled:bg-gray-100" />
              </div>
              {!editUser && (
                <div>
                  <label className="block text-sm text-gray-600 mb-1">密码</label>
                  <PasswordInput
                    value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                    placeholder="请输入密码（至少6位）"
                  />
                </div>
              )}
              <div>
                <label className="block text-sm text-gray-600 mb-1">姓名</label>
                <input value={form.real_name} onChange={e => setForm(f => ({ ...f, real_name: e.target.value }))}
                  className="w-full border rounded px-3 py-2" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">角色</label>
                <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                  className="w-full border rounded px-3 py-2">
                  <option value="normal">普通账号</option>
                  <option value="important">重要账号</option>
                  <option value="archive">档案管理</option>
                  <option value="admin">系统管理员</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">归属上级（重要账号及以下）</label>
                <select value={form.parent_id} onChange={e => setForm(f => ({ ...f, parent_id: e.target.value }))}
                  className="w-full border rounded px-3 py-2">
                  <option value="">无</option>
                  {importantUsers.filter(x => x.id !== editUser?.id).map(x => (
                    <option key={x.id} value={x.id}>{x.real_name} ({ROLE_MAP[x.role]})</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end space-x-2 mt-6">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 border rounded">取消</button>
              <button onClick={handleSubmit} className="px-4 py-2 bg-blue-600 text-white rounded">保存</button>
            </div>
          </div>
        </div>
      )}

      {/* 批量审批弹窗 */}
      {showBatchApprove && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-[480px]">
            <h3 className="text-lg font-bold mb-1">批量审批账号</h3>
            <p className="text-sm text-gray-500 mb-4">
              将对 <strong className="text-blue-600">{selectedIds.size}</strong> 个待审批账号统一处理
            </p>
            {!batchProgress ? (
              <>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">统一分配角色<span className="text-red-500 ml-1">*</span></label>
                    <select value={batchForm.role} onChange={e => setBatchForm(f => ({ ...f, role: e.target.value }))}
                      className="w-full border rounded px-3 py-2">
                      <option value="normal">普通账号</option>
                      <option value="important">重要账号</option>
                      <option value="archive">档案管理</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">统一归属上级（重要账号及以下必选）</label>
                    <select value={batchForm.parent_id} onChange={e => setBatchForm(f => ({ ...f, parent_id: e.target.value }))}
                      className="w-full border rounded px-3 py-2">
                      <option value="">无</option>
                      {importantUsers.map(x => (
                        <option key={x.id} value={x.id}>{x.real_name} ({ROLE_MAP[x.role]})</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">统一初始密码<span className="text-red-500 ml-1">*</span></label>
                    <PasswordInput
                      value={batchForm.pwd}
                      onChange={e => setBatchForm(f => ({ ...f, pwd: e.target.value }))}
                      placeholder="将应用于所有选中用户（至少6位）"
                    />
                  </div>
                  <div className="bg-blue-50 border border-blue-200 rounded p-2 text-xs text-blue-800">
                    提示：批量审批将统一设置角色、初始密码和归属上级。请提前通知相关用户该初始密码。
                  </div>
                </div>
                <div className="flex justify-end space-x-2 mt-6">
                  <button onClick={closeBatchApprove} className="px-4 py-2 border rounded">取消</button>
                  <button
                    onClick={handleBatchSubmit}
                    className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                  >
                    确认批量通过
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="space-y-2 mb-4">
                  <div className="flex justify-between text-sm">
                    <span>进度：{batchProgress.current} / {batchProgress.total}</span>
                    <span>
                      <span className="text-green-600">成功 {batchProgress.ok}</span>
                      {batchProgress.fail > 0 && <span className="text-red-600 ml-2">失败 {batchProgress.fail}</span>}
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded overflow-hidden">
                    <div
                      className="h-full bg-green-500 transition-all"
                      style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}
                    />
                  </div>
                  {batchProgress.current < batchProgress.total ? (
                    <p className="text-xs text-gray-500 text-center">处理中...</p>
                  ) : (
                    <p className="text-xs text-green-600 text-center">处理完成！</p>
                  )}
                </div>
                {batchProgress.errors && batchProgress.errors.length > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded p-2 text-xs max-h-32 overflow-y-auto">
                    <p className="text-red-700 font-medium mb-1">失败明细：</p>
                    {batchProgress.errors.map((e, i) => (
                      <div key={i} className="text-red-600">
                        {e.name}（{e.username}）：{e.error}
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex justify-end space-x-2 mt-4">
                  <button onClick={closeBatchApprove} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                    {batchProgress.current < batchProgress.total ? '后台继续' : '完成'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* 重置密码弹窗 */}
      {showResetPwd && resetPwdTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96">
            <h3 className="text-lg font-bold mb-4">
              重置密码 — {resetPwdTarget.real_name}（{resetPwdTarget.username}）
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">新密码<span className="text-red-500 ml-1">*</span></label>
                <PasswordInput
                  value={resetPwdForm.pwd1}
                  onChange={e => setResetPwdForm(f => ({ ...f, pwd1: e.target.value }))}
                  placeholder="请输入新密码（至少6位）"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">确认新密码<span className="text-red-500 ml-1">*</span></label>
                <PasswordInput
                  value={resetPwdForm.pwd2}
                  onChange={e => setResetPwdForm(f => ({ ...f, pwd2: e.target.value }))}
                  placeholder="请再次输入新密码"
                />
                {resetPwdForm.pwd2 && resetPwdForm.pwd1 !== resetPwdForm.pwd2 && (
                  <p className="text-xs text-red-500 mt-1">两次输入的密码不一致</p>
                )}
              </div>
            </div>
            <div className="flex justify-end space-x-2 mt-6">
              <button onClick={closeResetPwd} className="px-4 py-2 border rounded">取消</button>
              <button
                onClick={handleResetPwdSubmit}
                className="px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700"
              >
                确认重置
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
