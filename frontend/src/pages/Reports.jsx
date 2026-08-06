import { useState, useEffect } from 'react'
import {
  getReportSummary, getReportTrend, getReportByPartner,
  getReportByCooperation, getReportByWinBid, exportReport,
} from '../api'
import { useAuthStore } from '../stores/auth'

const STATUS_COLOR = {
  pending_submit: '#9ca3af',
  pending_approval: '#facc15',
  approved: '#22c55e',
  rejected: '#ef4444',
}
const STATUS_LABEL = {
  pending_submit: '待提交',
  pending_approval: '待审批',
  approved: '已通过',
  rejected: '已驳回',
}
const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16', '#ec4899']

export default function Reports() {
  const { user } = useAuthStore()
  const [keyword, setKeyword] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [summary, setSummary] = useState(null)
  const [trend, setTrend] = useState([])
  const [partners, setPartners] = useState([])
  const [coop, setCoop] = useState([])
  const [winBid, setWinBid] = useState([])
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)

  const params = () => {
    const p = {}
    if (keyword) p.keyword = keyword
    if (startDate) p.start_date = startDate
    if (endDate) p.end_date = endDate
    return p
  }

  const fetchAll = async () => {
    setLoading(true)
    try {
      const p = params()
      const [s, t, pp, cc, w] = await Promise.all([
        getReportSummary(p),
        getReportTrend(p),
        getReportByPartner(p),
        getReportByCooperation(p),
        getReportByWinBid(p),
      ])
      setSummary(s.data)
      setTrend(t.data)
      setPartners(pp.data)
      setCoop(cc.data)
      setWinBid(w.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [])

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await exportReport(params())
      const blob = new Blob([res.data])
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const cd = res.headers['content-disposition'] || ''
      const m = /filename=([^;]+)/.exec(cd)
      a.download = m ? m[1].trim() : 'projects.xlsx'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert('导出失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setExporting(false)
    }
  }

  const handleReset = () => {
    setKeyword(''); setStartDate(''); setEndDate('')
    setTimeout(fetchAll, 0)
  }

  const totalCount = summary?.total || 0
  const totalAmount = summary?.total_amount || 0
  const feeAmount = summary?.fee_amount || 0

  return (
    <div className="space-y-6">
      {/* 筛选 */}
      <div className="bg-white rounded shadow p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">关键字</label>
            <input
              type="text" value={keyword} onChange={e => setKeyword(e.target.value)}
              placeholder="项目名 / 合作单位 / 编号"
              className="border rounded px-3 py-1.5 text-sm w-56"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">投标起始日期</label>
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
              className="border rounded px-3 py-1.5 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">投标截止日期</label>
            <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
              className="border rounded px-3 py-1.5 text-sm" />
          </div>
          <button onClick={fetchAll} disabled={loading}
            className="px-4 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50">
            查询
          </button>
          <button onClick={handleReset}
            className="px-4 py-1.5 border rounded text-sm hover:bg-gray-50">
            重置
          </button>
          <div className="ml-auto">
            <button onClick={handleExport} disabled={exporting}
              className="px-4 py-1.5 bg-green-500 text-white rounded text-sm hover:bg-green-600 disabled:opacity-50">
              📥 导出 Excel
            </button>
          </div>
        </div>
      </div>

      {/* KPI 卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="项目总数" value={totalCount} unit="个" color="blue" />
        <KpiCard label="项目总金额" value={(totalAmount / 10000).toLocaleString(undefined, {maximumFractionDigits: 2})} unit="万元" color="green" />
        <KpiCard label="费用总额" value={(feeAmount / 10000).toLocaleString(undefined, {maximumFractionDigits: 2})} unit="万元" color="amber" />
        <KpiCard label="审批状态数" value={(summary?.by_status || []).length} unit="种" color="purple" />
      </div>

      {/* 状态分布 */}
      <div className="bg-white rounded shadow p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">按审批状态分布</h3>
        <StatusBar data={summary?.by_status || []} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* 月度趋势 */}
        <div className="bg-white rounded shadow p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">月度趋势（投标时间）</h3>
          <BarChart
            data={trend.map(t => ({ label: t.month, value: t.count, sub: t.amount }))}
            color="#3b82f6"
            valueFmt={(v) => `${v} 个`}
            subFmt={(s) => `${(s / 10000).toFixed(2)} 万元`}
          />
        </div>

        {/* 合作模式 */}
        <div className="bg-white rounded shadow p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">合作模式分布</h3>
          <PieChart
            data={coop.map(c => ({ label: c.label, value: c.count }))}
            colors={COLORS}
          />
        </div>

        {/* 中标状态 */}
        <div className="bg-white rounded shadow p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">中标状态分布</h3>
          <PieChart
            data={winBid.map(w => ({ label: w.label, value: w.count }))}
            colors={COLORS.slice(2)}
          />
        </div>

        {/* Top 合作单位 */}
        <div className="bg-white rounded shadow p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">合作单位 Top {partners.length}</h3>
          <BarChart
            data={partners.slice(0, 10).map(p => ({ label: p.partner, value: p.count }))}
            color="#22c55e"
            horizontal
            valueFmt={(v) => `${v} 个`}
          />
        </div>
      </div>

      {/* 合作单位明细表 */}
      <div className="bg-white rounded shadow p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">合作单位明细</h3>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-3 py-2 text-left">排名</th>
              <th className="px-3 py-2 text-left">合作单位</th>
              <th className="px-3 py-2 text-right">项目数</th>
              <th className="px-3 py-2 text-right">金额合计 (万元)</th>
              <th className="px-3 py-2 text-right">占比</th>
            </tr>
          </thead>
          <tbody>
            {partners.length === 0 ? (
              <tr><td colSpan={5} className="text-center py-6 text-gray-400">暂无数据</td></tr>
            ) : partners.map((p, i) => (
              <tr key={p.partner} className="border-t hover:bg-gray-50">
                <td className="px-3 py-2">{i + 1}</td>
                <td className="px-3 py-2">{p.partner}</td>
                <td className="px-3 py-2 text-right">{p.count}</td>
                <td className="px-3 py-2 text-right">{(Number(p.amount) / 10000).toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
                <td className="px-3 py-2 text-right text-gray-500">
                  {totalCount > 0 ? `${(p.count / totalCount * 100).toFixed(1)}%` : '0%'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function KpiCard({ label, value, unit, color }) {
  const colorMap = {
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
    green: 'bg-green-50 border-green-200 text-green-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
  }
  return (
    <div className={`rounded border p-4 ${colorMap[color]}`}>
      <div className="text-xs opacity-80">{label}</div>
      <div className="mt-1 flex items-baseline">
        <span className="text-2xl font-bold">{value}</span>
        <span className="ml-1 text-xs opacity-70">{unit}</span>
      </div>
    </div>
  )
}

function StatusBar({ data }) {
  if (!data.length) return <div className="text-gray-400 text-sm">暂无数据</div>
  const total = data.reduce((s, d) => s + d.count, 0) || 1
  return (
    <div className="space-y-2">
      {data.map(d => {
        const pct = d.count / total * 100
        return (
          <div key={d.status} className="flex items-center gap-3">
            <div className="w-24 text-sm text-gray-600">{STATUS_LABEL[d.status] || d.status}</div>
            <div className="flex-1 h-6 bg-gray-100 rounded overflow-hidden">
              <div className="h-full transition-all" style={{
                width: `${pct}%`,
                background: STATUS_COLOR[d.status] || '#9ca3af',
              }} />
            </div>
            <div className="w-24 text-right text-sm">
              <span className="font-medium">{d.count}</span>
              <span className="text-gray-400 text-xs ml-1">({pct.toFixed(1)}%)</span>
            </div>
            <div className="w-28 text-right text-xs text-gray-500">
              {(Number(d.amount) / 10000).toLocaleString(undefined, {maximumFractionDigits: 2})} 万元
            </div>
          </div>
        )
      })}
    </div>
  )
}

function BarChart({ data, color = '#3b82f6', horizontal = false, valueFmt = (v) => v }) {
  if (!data.length) return <div className="text-gray-400 text-sm py-8 text-center">暂无数据</div>
  if (horizontal) {
    const max = Math.max(...data.map(d => d.value)) || 1
    return (
      <div className="space-y-2 max-h-72 overflow-auto">
        {data.map((d, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="w-28 text-xs text-gray-600 truncate text-right" title={d.label}>{d.label}</div>
            <div className="flex-1 h-5 bg-gray-100 rounded overflow-hidden">
              <div className="h-full" style={{
                width: `${d.value / max * 100}%`,
                background: color,
              }} />
            </div>
            <div className="w-20 text-xs text-gray-700 text-right">{valueFmt(d.value)}</div>
          </div>
        ))}
      </div>
    )
  }
  // vertical bar
  const max = Math.max(...data.map(d => d.value)) || 1
  const W = 500, H = 200, P = 30
  const bw = data.length ? (W - P * 2) / data.length : 0
  return (
    <svg viewBox={`0 0 ${W} ${H + 30}`} className="w-full h-56">
      <line x1={P} y1={H - 30} x2={W - P} y2={H - 30} stroke="#e5e7eb" />
      {data.map((d, i) => {
        const h = (d.value / max) * (H - 50)
        const x = P + i * bw + 2
        const y = H - 30 - h
        return (
          <g key={i}>
            <rect x={x} y={y} width={Math.max(bw - 4, 4)} height={h} fill={color} rx="2">
              <title>{d.label}: {valueFmt(d.value)}</title>
            </rect>
            <text x={x + (bw - 4) / 2} y={H - 18} textAnchor="middle"
              fontSize="10" fill="#6b7280">{String(d.label).slice(5)}</text>
            <text x={x + (bw - 4) / 2} y={y - 4} textAnchor="middle"
              fontSize="10" fill="#374151">{d.value}</text>
          </g>
        )
      })}
    </svg>
  )
}

function PieChart({ data, colors = COLORS }) {
  if (!data.length) return <div className="text-gray-400 text-sm py-8 text-center">暂无数据</div>
  const total = data.reduce((s, d) => s + d.value, 0) || 1
  const R = 70, C = 2 * Math.PI * R
  let offset = 0
  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 200 200" className="w-44 h-44">
        <g transform="translate(100,100) rotate(-90)">
          {data.map((d, i) => {
            const len = (d.value / total) * C
            const el = (
              <circle key={i} r={R} fill="none"
                stroke={colors[i % colors.length]}
                strokeWidth={28}
                strokeDasharray={`${len} ${C - len}`}
                strokeDashoffset={-offset}>
                <title>{d.label}: {d.value} ({((d.value / total) * 100).toFixed(1)}%)</title>
              </circle>
            )
            offset += len
            return el
          })}
        </g>
        <text x="100" y="98" textAnchor="middle" fontSize="13" fill="#6b7280">合计</text>
        <text x="100" y="115" textAnchor="middle" fontSize="16" fill="#111" fontWeight="600">{total}</text>
      </svg>
      <div className="flex-1 space-y-1 max-h-44 overflow-auto">
        {data.map((d, i) => (
          <div key={i} className="flex items-center text-sm">
            <span className="w-3 h-3 rounded mr-2" style={{ background: colors[i % colors.length] }} />
            <span className="flex-1 text-gray-700 truncate">{d.label}</span>
            <span className="ml-2 text-gray-500">{d.value}</span>
            <span className="ml-2 text-xs text-gray-400 w-12 text-right">
              {((d.value / total) * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}