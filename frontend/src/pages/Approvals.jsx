import { useState, useEffect } from 'react'
import { getApprovalPending, getApprovalHistory, getApprovalSummary, fastApprove, fastReject } from '../api'
import { useAuthStore } from '../stores/auth'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(utc)
dayjs.extend(timezone)

const TABS = [
  { key: 'pending', label: '待我审批' },
  { key: 'history', label: '我已审批' },
]

const STATUS_MAP = {
  pending_approval: { label: '待审批', color: 'bg-yellow-100 text-yellow-700' },
  approved: { label: '已通过', color: 'bg-green-100 text-green-700' },
  rejected: { label: '已拒绝', color: 'bg-red-100 text-red-700' },
}

export default function Approvals() {
  const { user } = useAuthStore()
  const [tab, setTab] = useState('pending')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState({ pending: 0, history: 0, scope: 0 })
  const [filterName, setFilterName] = useState('')
  const [filterPartner, setFilterPartner] = useState('')
  const [busyId, setBusyId] = useState(null)

  const canApprove = user?.role === 'admin' || user?.role === 'important'

  const fetchSummary = async () => {
    try {
      const res = await getApprovalSummary()
      const m = /pending=(\d+)\|history=(\d+)\|scope=(\d+)/.exec(res.data.message || '')
      if (m) setSummary({ pending: +m[1], history: +m[2], scope: +m[3] })
    } catch (e) { console.error(e) }
  }

  const fetchList = async () => {
    setLoading(true)
    try {
      const params = { page, page_size: 20 }
      if (filterName) params.project_name = filterName
      if (filterPartner) params.partner_company = filterPartner
      const apiCall = tab === 'pending' ? getApprovalPending : getApprovalHistory
      const res = await apiCall(params)
      setItems(res.data.items)
      setTotal(res.data.total)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchSummary() }, [])
  useEffect(() => { setPage(1) }, [tab])
  useEffect(() => { fetchList() }, [tab, page, filterName, filterPartner])

  const handleApprove = async (id) => {
    if (!confirm('确认通过该项目？')) return
    setBusyId(id)
    try {
      await fastApprove(id)
      await fetchSummary()
      await fetchList()
    } finally { setBusyId(null) }
  }

  const handleReject = async (id) => {
    if (!confirm('确认驳回该项目？')) return
    setBusyId(id)
    try {
      await fastReject(id)
      await fetchSummary()
      await fetchList()
    } finally { setBusyId(null) }
  }

  return (
    <div>
      {/* 顶部 KPI */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
          <div className="text-xs text-yellow-700">待我审批</div>
          <div className="text-2xl font-bold text-yellow-700">{summary.pending}</div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded p-4">
          <div className="text-xs text-green-700">我已审批</div>
          <div className="text-2xl font-bold text-green-700">{summary.history}</div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded p-4">
          <div className="text-xs text-blue-700">管理范围内</div>
          <div className="text-2xl font-bold text-blue-700">{summary.scope}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-4 mb-4 border-b">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 -mb-px border-b-2 transition ${
              tab === t.key
                ? 'border-blue-500 text-blue-600 font-medium'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label} {t.key === 'pending' && summary.pending > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-yellow-500 text-white">{summary.pending}</span>
            )}
          </button>
        ))}
      </div>

      {/* 筛选 */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          placeholder="项目名称"
          value={filterName}
          onChange={e => { setPage(1); setFilterName(e.target.value) }}
          className="border rounded px-3 py-1.5 text-sm"
        />
        <input
          type="text"
          placeholder="合作单位"
          value={filterPartner}
          onChange={e => { setPage(1); setFilterPartner(e.target.value) }}
          className="border rounded px-3 py-1.5 text-sm"
        />
      </div>

      {/* 表格 */}
      <div className="bg-white rounded shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-3 py-2 text-left">序号</th>
              <th className="px-3 py-2 text-left">项目名称</th>
              <th className="px-3 py-2 text-left">编号</th>
              <th className="px-3 py-2 text-left">合作单位</th>
              <th className="px-3 py-2 text-right">金额(元)</th>
              <th className="px-3 py-2 text-center">状态</th>
              <th className="px-3 py-2 text-left">创建人</th>
              <th className="px-3 py-2 text-left">审批人</th>
              <th className="px-3 py-2 text-left">填报时间</th>
              {tab === 'pending' && canApprove && (
                <th className="px-3 py-2 text-center">操作</th>
              )}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={10} className="text-center py-8 text-gray-400">加载中…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={10} className="text-center py-8 text-gray-400">暂无数据</td></tr>
            ) : items.map((p, idx) => {
              const st = STATUS_MAP[p.approval_status]
              return (
                <tr key={p.id} className="border-t hover:bg-gray-50">
                  <td className="px-3 py-2 text-gray-500">{(page - 1) * 20 + idx + 1}</td>
                  <td className="px-3 py-2">{p.project_name}</td>
                  <td className="px-3 py-2 font-mono text-xs">{p.project_code}</td>
                  <td className="px-3 py-2">{p.partner_company}</td>
                  <td className="px-3 py-2 text-right">{Number(p.project_amount).toLocaleString()}</td>
                  <td className="px-3 py-2 text-center">
                    <span className={`px-2 py-0.5 rounded text-xs ${st?.color}`}>{st?.label || p.approval_status}</span>
                  </td>
                  <td className="px-3 py-2">{p.creator?.real_name || '-'}</td>
                  <td className="px-3 py-2">{p.approver?.real_name || '-'}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">{p.created_at ? dayjs.utc(p.created_at).tz('Asia/Shanghai').format('YYYY-MM-DD HH:mm') : '-'}</td>
                  {tab === 'pending' && canApprove && (
                    <td className="px-3 py-2 text-center">
                      <div className="flex justify-center gap-2">
                        <button
                          onClick={() => handleApprove(p.id)}
                          disabled={busyId === p.id}
                          className="px-3 py-1 text-xs rounded bg-green-500 text-white hover:bg-green-600 disabled:opacity-50"
                        >通过</button>
                        <button
                          onClick={() => handleReject(p.id)}
                          disabled={busyId === p.id}
                          className="px-3 py-1 text-xs rounded bg-red-500 text-white hover:bg-red-600 disabled:opacity-50"
                        >驳回</button>
                      </div>
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      <div className="flex items-center justify-between mt-4 text-sm">
        <span className="text-gray-500">共 {total} 条，第 {page} 页</span>
        <div className="flex gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="px-3 py-1 border rounded disabled:opacity-40">上一页</button>
          <button onClick={() => setPage(p => p + 1)} disabled={page * 20 >= total}
            className="px-3 py-1 border rounded disabled:opacity-40">下一页</button>
        </div>
      </div>
    </div>
  )
}
