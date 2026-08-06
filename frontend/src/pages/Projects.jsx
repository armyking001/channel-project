import { useState, useEffect } from 'react'
import { getProjects, deleteProject, submitProject, approveProject, rejectProject } from '../api'
import { useAuthStore } from '../stores/auth'
import ProjectForm from '../components/ProjectForm'
import dayjs from 'dayjs'

const STATUS_MAP = {
  pending_submit: { label: '待提交', color: 'bg-gray-100 text-gray-600' },
  pending_approval: { label: '待审批', color: 'bg-yellow-100 text-yellow-700' },
  approved: { label: '已通过', color: 'bg-green-100 text-green-700' },
  rejected: { label: '已拒绝', color: 'bg-red-100 text-red-700' },
}

const WIN_MAP = {
  yes: '中标', no: '未中标', in_progress: '进行中'
}

export default function Projects() {
  const { user } = useAuthStore()
  const [projects, setProjects] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState({ project_name: '', partner_company: '', approval_status: '', win_bid_status: '', start_date: '', end_date: '', min_amount: '', max_amount: '' })
  const [showForm, setShowForm] = useState(false)
  const [showViewForm, setShowViewForm] = useState(false)
  const [editData, setEditData] = useState(null)
  const [selectedProject, setSelectedProject] = useState(null)
  const [showApproveModal, setShowApproveModal] = useState(false)
  const [approveComment, setApproveComment] = useState('')

  const fetchProjects = async () => {
    setLoading(true)
    try {
      // 过滤空值参数，避免发送空字符串导致后端解析错误
      const params = { page, page_size: 20 }
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== '' && v !== null && v !== undefined) params[k] = v
      })
      const res = await getProjects(params)
      setProjects(res.data.items)
      setTotal(res.data.total)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchProjects() }, [page, filters])

  const handleDelete = async (id) => {
    if (!confirm('确认删除该项目？')) return
    await deleteProject(id)
    fetchProjects()
  }

  const handleSubmit = async (id) => {
    await submitProject(id)
    fetchProjects()
  }

  const handleApprove = async () => {
    await approveProject(selectedProject.id, { comment: approveComment })
    setShowApproveModal(false)
    setApproveComment('')
    setSelectedProject(null)
    fetchProjects()
  }

  const handleReject = async () => {
    const comment = prompt('请输入驳回原因：')
    if (comment === null) return
    await rejectProject(selectedProject.id, { comment })
    setSelectedProject(null)
    fetchProjects()
  }

  const canApprove = user?.role === 'admin' || user?.role === 'important'
  const isAdmin = user?.role === 'admin'
  const isArchive = user?.role === 'archive'
  // 是否为项目创建者
  const isProjectCreator = (p) => p.created_by === user?.id

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">项目列表</h2>
        <button
          onClick={() => { setEditData(null); setShowForm(true) }}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition"
        >
          新建项目
        </button>
      </div>

      {/* 筛选 */}
      <div className="bg-white p-4 rounded shadow mb-4 flex gap-4 flex-wrap">
        <input
          placeholder="项目名称"
          value={filters.project_name}
          onChange={(e) => { setFilters(f => ({ ...f, project_name: e.target.value })); setPage(1) }}
          className="px-3 py-2 border rounded w-48"
        />
        <input
          placeholder="合作单位"
          value={filters.partner_company}
          onChange={(e) => { setFilters(f => ({ ...f, partner_company: e.target.value })); setPage(1) }}
          className="px-3 py-2 border rounded w-48"
        />
        <select
          value={filters.approval_status}
          onChange={(e) => { setFilters(f => ({ ...f, approval_status: e.target.value })); setPage(1) }}
          className="px-3 py-2 border rounded w-40"
        >
          <option value="">全部状态</option>
          {Object.entries(STATUS_MAP).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
        <select
          value={filters.win_bid_status}
          onChange={(e) => { setFilters(f => ({ ...f, win_bid_status: e.target.value })); setPage(1) }}
          className="px-3 py-2 border rounded w-40"
        >
          <option value="">全部中标状态</option>
          {Object.entries(WIN_MAP).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <div className="flex items-center gap-1">
          <span className="text-sm text-gray-500">金额(万元)</span>
          <input
            type="number"
            placeholder="最小"
            value={filters.min_amount}
            onChange={(e) => { setFilters(f => ({ ...f, min_amount: e.target.value })); setPage(1) }}
            className="px-3 py-2 border rounded w-24"
            min="0"
          />
          <span className="text-gray-400">-</span>
          <input
            type="number"
            placeholder="最大"
            value={filters.max_amount}
            onChange={(e) => { setFilters(f => ({ ...f, max_amount: e.target.value })); setPage(1) }}
            className="px-3 py-2 border rounded w-24"
            min="0"
          />
        </div>
        <div className="flex items-center gap-1">
          <span className="text-sm text-gray-500">填报日期</span>
          <input
            type="date"
            value={filters.start_date}
            onChange={(e) => { setFilters(f => ({ ...f, start_date: e.target.value })); setPage(1) }}
            className="px-3 py-2 border rounded"
          />
          <span className="text-gray-400">-</span>
          <input
            type="date"
            value={filters.end_date}
            onChange={(e) => { setFilters(f => ({ ...f, end_date: e.target.value })); setPage(1) }}
            className="px-3 py-2 border rounded"
          />
        </div>
      </div>

      {/* 表格 */}
      <div className="bg-white rounded shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left">序号</th>
              <th className="px-4 py-3 text-left">项目名称</th>
              <th className="px-4 py-3 text-left">编号</th>
              <th className="px-4 py-3 text-left">合作单位</th>
              <th className="px-4 py-3 text-left">金额(万元)</th>
              <th className="px-4 py-3 text-left">中标</th>
              <th className="px-4 py-3 text-left">状态</th>
              <th className="px-4 py-3 text-left">填报时间</th>
              <th className="px-4 py-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="text-center py-8 text-gray-400">加载中...</td></tr>
            ) : projects.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-8 text-gray-400">暂无数据</td></tr>
            ) : projects.map((p, idx) => (
              <tr key={p.id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-500">{(page - 1) * 20 + idx + 1}</td>
                <td className="px-4 py-3 font-medium">{p.project_name}</td>
                <td className="px-4 py-3 text-gray-500">{p.project_code}</td>
                <td className="px-4 py-3">{p.partner_company}</td>
                <td className="px-4 py-3 text-right">{p.project_amount != null ? ((p.project_amount / 10000).toLocaleString(undefined, {maximumFractionDigits: 2})) : '-'}</td>
                <td className="px-4 py-3">{WIN_MAP[p.win_bid_status] || '-'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs ${STATUS_MAP[p.approval_status]?.color}`}>
                    {STATUS_MAP[p.approval_status]?.label}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">{dayjs(p.created_at).format('YYYY-MM-DD')}</td>
                <td className="px-4 py-3 text-center space-x-2">
                  {/* 操作按钮 */}
                  {(() => {
                    // 档案管理：只能查看
                    if (isArchive) {
                      return (
                        <button onClick={() => { setEditData(p); setShowViewForm(true) }} className="text-gray-600 hover:underline">查看</button>
                      )
                    }
                    
                    const creator = isProjectCreator(p)
                    const status = p.approval_status
                    
                    // 系统管理员：任何状态都可操作（编辑 + 查看 + 删除）
                    if (isAdmin) {
                      return (
                        <>
                          <button onClick={() => { setEditData(p); setShowForm(true) }} className="text-blue-600 hover:underline">编辑</button>
                          <button onClick={() => { setEditData(p); setShowViewForm(true) }} className="text-gray-600 hover:underline">查看</button>
                          <button onClick={() => handleDelete(p.id)} className="text-red-600 hover:underline">删除</button>
                        </>
                      )
                    }
                    
                    // 项目创建者
                    if (creator) {
                      // 待提交状态：编辑 + 查看 + 删除
                      if (status === 'pending_submit') {
                        return (
                          <>
                            <button onClick={() => { setEditData(p); setShowForm(true) }} className="text-blue-600 hover:underline">编辑</button>
                            <button onClick={() => { setEditData(p); setShowViewForm(true) }} className="text-gray-600 hover:underline">查看</button>
                            <button onClick={() => handleDelete(p.id)} className="text-red-600 hover:underline">删除</button>
                          </>
                        )
                      }
                      // 其他状态：编辑、查看（不能删除）
                      return (
                        <>
                          <button onClick={() => { setEditData(p); setShowForm(true) }} className="text-blue-600 hover:underline">编辑</button>
                          <button onClick={() => { setEditData(p); setShowViewForm(true) }} className="text-gray-600 hover:underline">查看</button>
                        </>
                      )
                    }
                    
                    // 其他用户：只能查看
                    return (
                      <button onClick={() => { setEditData(p); setShowViewForm(true) }} className="text-gray-600 hover:underline">查看</button>
                    )
                  })()}
                  
                  {/* 审批按钮 */}
                  {p.approval_status === 'pending_approval' && (user?.role === 'admin' || user?.role === 'important' || p.approver_id === user?.id) ? (
                    <>
                      <button onClick={() => { setSelectedProject(p); setShowApproveModal(true) }} className="text-green-600 hover:underline">通过</button>
                      <button onClick={() => { setSelectedProject(p); handleReject() }} className="text-red-600 hover:underline">驳回</button>
                    </>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      <div className="flex justify-center mt-4 space-x-2">
        <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1 border rounded disabled:opacity-40">上一页</button>
        <span className="px-3 py-1">第 {page} / {Math.ceil(total / 20)} 页</span>
        <button disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(p => p + 1)} className="px-3 py-1 border rounded disabled:opacity-40">下一页</button>
      </div>

      {/* 编辑表单弹窗 */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-2xl max-h-[92vh] overflow-auto">
            <ProjectForm
              project={editData}
              onClose={() => setShowForm(false)}
              onSaved={() => { setShowForm(false); fetchProjects() }}
            />
          </div>
        </div>
      )}

      {/* 查看表单弹窗（只读模式） */}
      {showViewForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-2xl max-h-[92vh] overflow-auto">
            <ProjectForm
              project={editData}
              readOnly={true}
              onClose={() => setShowViewForm(false)}
              onSaved={() => { setShowViewForm(false); fetchProjects() }}
            />
          </div>
        </div>
      )}

      {/* 审批通过弹窗 */}
      {showApproveModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96">
            <h3 className="text-lg font-bold mb-4">审批通过</h3>
            <textarea
              placeholder="审批意见（可选）"
              value={approveComment}
              onChange={(e) => setApproveComment(e.target.value)}
              className="w-full border rounded p-2 mb-4 h-24"
            />
            <div className="flex justify-end space-x-2">
              <button onClick={() => setShowApproveModal(false)} className="px-4 py-2 border rounded">取消</button>
              <button onClick={handleApprove} className="px-4 py-2 bg-green-600 text-white rounded">确认通过</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}