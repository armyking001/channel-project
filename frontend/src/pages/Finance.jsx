import { useState, useEffect, useRef } from 'react'
import {
  importFinanceReceivables, importFinanceTrust,
  getFinanceReceivables, getFinanceTrust, getFinancePersons,
  sendFinanceReminder, updateReceivableFrequency, updateTrustFrequency,
  getFinanceReminderLogs,
  deleteReceivable, deleteReceivablesBulk,
  deleteTrust, deleteTrustsBulk,
  updateReceivableRemindStart, updateReceivableRemindEnd,
  updateTrustRemindStart, updateTrustRemindEnd,
} from '../api'

// 频率选项
const FREQ_OPTIONS = [
  { value: 'once',    label: '仅一次' },
  { value: 'daily',   label: '每天' },
  { value: 'weekly',  label: '每周' },
  { value: 'monthly', label: '每月' },
]
const FREQ_LABEL = Object.fromEntries(FREQ_OPTIONS.map(o => [o.value, o.label]))

// 三色通道 chip(尺寸一致, 颜色不同)
const CHANNEL_CHIPS = [
  { v: 'dingtalk_corp', label: '钉钉通知',   tone: 'blue'   },
  { v: 'wechat_mp',     label: '微信通知',   tone: 'green'  },
  { v: 'sms_custom',    label: '短信通知',   tone: 'amber'  },
  { v: 'sms_aliyun',    label: '阿里云短信', tone: 'orange' },
  { v: 'sms_tencent',   label: '腾讯云短信', tone: 'rose'   },
]
const TONE = {
  blue:   { on: 'bg-blue-600 text-white border-blue-600',  off: 'bg-white text-blue-700 border-blue-300 hover:bg-blue-50' },
  green:  { on: 'bg-green-600 text-white border-green-600', off: 'bg-white text-green-700 border-green-300 hover:bg-green-50' },
  cyan:   { on: 'bg-cyan-600 text-white border-cyan-600',  off: 'bg-white text-cyan-700 border-cyan-300 hover:bg-cyan-50' },
  amber:  { on: 'bg-amber-500 text-white border-amber-500', off: 'bg-white text-amber-700 border-amber-300 hover:bg-amber-50' },
  orange: { on: 'bg-orange-500 text-white border-orange-500', off: 'bg-white text-orange-700 border-orange-300 hover:bg-orange-50' },
  rose:   { on: 'bg-rose-500 text-white border-rose-500',  off: 'bg-white text-rose-700 border-rose-300 hover:bg-rose-50' },
}
// 默认全选, 进入页面首次出现时使用, 之后以 localStorage 为准
const defaultChannels = () => CHANNEL_CHIPS.reduce((m, c) => { m[c.v] = true; return m }, {})
const STATUS_LABEL = {
  pending:    { text: '未发送', cls: 'bg-gray-100 text-gray-600' },
  sent:       { text: '已送达', cls: 'bg-green-100 text-green-700' },
  failed:     { text: '失败',   cls: 'bg-red-100 text-red-700' },
  skipped:    { text: '跳过',   cls: 'bg-yellow-100 text-yellow-700' },
}
const STATUS_TAG = {
  sent:    'bg-green-100 text-green-700',
  failed:  'bg-red-100 text-red-700',
  skipped: 'bg-yellow-100 text-yellow-700',
  pending: 'bg-gray-100 text-gray-600',
}

export default function Finance() {
  const [tab, setTab] = useState('receivables')  // receivables / trust / import / logs

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">财务借支催收管理</h1>
      </div>
      <div className="bg-white rounded-lg shadow p-1 inline-flex gap-1">
        {[
          { v: 'receivables', l: '应收款项' },
          { v: 'trust',       l: '财务借支' },
          { v: 'import',      l: '导入' },
          { v: 'logs',        l: '发送日志' },
        ].map(t => (
          <button key={t.v}
            onClick={() => setTab(t.v)}
            className={`px-4 py-2 rounded text-sm transition ${
              tab === t.v
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-gray-700 hover:bg-gray-100'
            }`}>
            {t.l}
          </button>
        ))}
      </div>

      {tab === 'import' && <ImportTab />}
      {tab === 'receivables' && <ReceivablesTab />}
      {tab === 'trust' && <TrustTab />}
      {tab === 'logs' && <LogsTab />}
    </div>
  )
}

// ================= 导入页签 =================
function ImportTab() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <ImportCard
        title="应收款项导入"
        desc="支持 .xlsx / .xls / .csv。列名包含:合同号、项目名称、客户、应收款、商务、工程人员、联系电话、计划收款时间、提醒启动时间、提醒频率、备注"
        onImport={importFinanceReceivables}
      />
      <ImportCard
        title="财务借支导入"
        desc="支持 .xlsx / .xls / .csv。列名包含:科目名称、期末项目余额、分类、发生时间、公司、部门、员工、联系电话、对账负责人、计划还款时间、提醒启动时间、提醒频率、备注"
        onImport={importFinanceTrust}
      />
      <div className="md:col-span-2 bg-white rounded-lg shadow p-4 text-xs text-gray-500">
        <div className="font-medium text-gray-700 mb-2">导入说明</div>
        <ul className="list-disc list-inside space-y-1">
          <li>第一行必须是表头(列名,中文)。空字符串自动规范为 None。</li>
          <li>金额字段非数字的行会被跳过并在结果中列出原因。</li>
          <li>频率取值(归一化): 一次/仅一次→once; 每天/日→daily; 每周/周→weekly; 每月/月→monthly; 其他→once。</li>
          <li>导入成功后, 后续在列表页可对单条记录修改频率或触发短信发送。</li>
        </ul>
      </div>
    </div>
  )
}

function ImportCard({ title, desc, onImport }) {
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const onPick = e => setFile(e.target.files?.[0] || null)

  const submit = async () => {
    if (!file) return alert('请先选择文件')
    setBusy(true)
    setResult(null)
    try {
      const r = await onImport(file)
      setResult(r.data)
    } catch (e) {
      setResult({ success: false, error: e.response?.data?.detail || e.message })
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="bg-white rounded-lg shadow p-5">
      <h3 className="text-base font-bold text-gray-800 mb-2">{title}</h3>
      <p className="text-xs text-gray-500 mb-4">{desc}</p>
      <div className="flex items-center gap-2">
        <input type="file" accept=".xlsx,.xls,.csv" onChange={onPick}
          className="flex-1 text-sm file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
        <button onClick={submit} disabled={busy || !file}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50">
          {busy ? '导入中…' : '上传导入'}
        </button>
      </div>
      {result && (
        <div className={`mt-3 p-3 rounded text-sm ${result.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {result.success ? (
            <>
              <div>✅ 成功导入 <b>{result.imported_count}</b> 条, 跳过 <b>{result.skipped_count}</b> 条</div>
              <div className="text-xs text-gray-500 mt-1">批次号: {result.batch_id}</div>
              {result.skipped && result.skipped.length > 0 && (
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer text-gray-600">查看跳过的行</summary>
                  <ul className="mt-1 list-disc list-inside text-gray-500">
                    {result.skipped.map((s, i) => (
                      <li key={i}>第 {s.row} 行: {s.reason}</li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          ) : (
            <>❌ {result.error || '导入失败'}</>
          )}
        </div>
      )}
    </div>
  )
}

// ================= 应收款项(财务催收) =================
function ReceivablesTab() {
  return (
    <DataTable
      type="receivables"
      title="财务催收"
      columns={[
        { key: 'contract_no',    label: '合同号' },
        { key: 'project_name',   label: '项目名称' },
        { key: 'customer',       label: '客户' },
        { key: 'amount',         label: '应收款', render: r => `¥${(r.amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}` },
        { key: 'sales_person',   label: '商务' },
        { key: 'engineer',       label: '工程人员' },
        { key: 'phone',          label: '联系电话' },
        { key: 'plan_date',      label: '计划收款时间' },
        { key: 'remind_start_at',label: '提醒启动时间', editable: 'datetime' },
        { key: 'remind_end_at',  label: '提醒结束时间', editable: 'datetime' },
        { key: 'frequency',      label: '提醒频率', editable: true },
        { key: 'reminder_count', label: '已提醒次数' },
        { key: 'last_status',    label: '发送状态', render: r => <StatusTag s={r.last_status} /> },
      ]}
    />
  )
}

// ================= 财务借支(原'财务信托') =================
function TrustTab() {
  return (
    <DataTable
      type="trust"
      title="财务借支"
      columns={[
        { key: 'subject_name',   label: '科目名称' },
        { key: 'balance',        label: '期末项目余额', render: r => `¥${(r.balance || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}` },
        { key: 'category',       label: '分类' },
        { key: 'occurred_at',    label: '发生时间' },
        { key: 'company',        label: '公司' },
        { key: 'department',     label: '部门' },
        { key: 'employee',       label: '员工' },
        { key: 'phone',          label: '联系电话' },
        { key: 'owner',          label: '对账负责人' },
        { key: 'plan_repay_date',label: '计划还款时间' },
        { key: 'remind_start_at',label: '提醒启动时间', editable: 'datetime' },
        { key: 'remind_end_at',  label: '提醒结束时间', editable: 'datetime' },
        { key: 'frequency',      label: '提醒频率', editable: true },
        { key: 'reminder_count', label: '已提醒次数' },
        { key: 'last_status',    label: '发送状态', render: r => <StatusTag s={r.last_status} /> },
      ]}
    />
  )
}

function StatusTag({ s }) {
  const t = STATUS_LABEL[s] || STATUS_LABEL.pending
  return <span className={`inline-block px-2 py-0.5 rounded text-xs ${t.cls}`}>{t.text}</span>
}

// ================= 通用表格页签 =================
function DataTable({ type, title, columns }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [persons, setPersons] = useState([])
  const [showSend, setShowSend] = useState(false)
  const [sendResult, setSendResult] = useState(null)
  const [sending, setSending] = useState(false)
  const [selectedPerson, setSelectedPerson] = useState('')  // '' = 全部
  const [freq, setFreq] = useState('once')
  // 选中行(跨页保留)
  const [selectedIds, setSelectedIds] = useState(new Set())
  // 发送范围模式: 'all'=全部人员 / 'person'=选人员 / 'selected'=选中行
  const [sendMode, setSendMode] = useState(() => {
    try { return localStorage.getItem('finance.sendMode') || 'all' } catch (e) { return 'all' }
  })
  // 本次允许的通道(每个通道 chip 独立记忆, 进入页面/换 tab 时从 localStorage 恢复)
  const [enabledChannels, setEnabledChannels] = useState(() => {
    const key = `finance.channels.${type}`
    try {
      const raw = localStorage.getItem(key)
      if (raw) return { ...defaultChannels(), ...JSON.parse(raw) }
    } catch (e) {}
    return defaultChannels()
  })
  // 每次 type(应收/信托)切换或 enabledChannels 变化都持久化
  useEffect(() => {
    try { localStorage.setItem(`finance.channels.${type}`, JSON.stringify(enabledChannels)) } catch (e) {}
  }, [enabledChannels, type])
  // 发送范围变化也持久化
  useEffect(() => {
    try { localStorage.setItem('finance.sendMode', sendMode) } catch (e) {}
  }, [sendMode])

  const load = async () => {
    setLoading(true)
    try {
      const fn = type === 'receivables' ? getFinanceReceivables : getFinanceTrust
      const r = await fn({ page, page_size: pageSize, q: q || undefined })
      setItems(r.data.items || [])
      setTotal(r.data.total || 0)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }
  const loadPersons = async () => {
    try {
      const r = await getFinancePersons(type)
      setPersons(r.data.items || [])
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => { load() }, [page, q, type])
  useEffect(() => { loadPersons() }, [type])

  const onChangeFreq = async (row, newFreq) => {
    try {
      const fn = type === 'receivables' ? updateReceivableFrequency : updateTrustFrequency
      await fn(row.id, newFreq)
      setItems(prev => prev.map(r => r.id === row.id ? { ...r, frequency: newFreq } : r))
    } catch (e) {
      alert(e.response?.data?.detail || '更新失败')
    }
  }

  // 将后端 ISO 字符串裁剪成 <input type="datetime-local"> 接受的格式 (YYYY-MM-DDTHH:mm)
  const toLocalInput = (iso) => {
    if (!iso) return ''
    const s = String(iso).replace(' ', 'T')
    // 取到分钟
    return s.length >= 16 ? s.slice(0, 16) : s
  }
  const fromLocalInput = (v) => v ? v : null  // 'YYYY-MM-DDTHH:mm' or null

  const onChangeRemindEnd = async (row, newVal) => {
    // 1) 校验: 结束时间不能早于启动时间
    if (newVal && row.remind_start_at) {
      const startLocal = toLocalInput(row.remind_start_at)
      if (startLocal && newVal < startLocal) {
        alert('提醒结束时间不能早于提醒启动时间')
        return
      }
    }
    try {
      const fn = type === 'receivables' ? updateReceivableRemindEnd : updateTrustRemindEnd
      const payloadVal = fromLocalInput(newVal)  // null 或 "YYYY-MM-DDTHH:mm"
      await fn(row.id, payloadVal)
      setItems(prev => prev.map(r => r.id === row.id
        ? { ...r, remind_end_at: payloadVal ? payloadVal + ':00' : null }
        : r))
    } catch (e) {
      alert(e.response?.data?.detail || '更新失败')
    }
  }

  const onChangeRemindStart = async (row, newVal) => {
    // 1) 校验: 启动时间不能晚于结束时间
    if (newVal && row.remind_end_at) {
      const endLocal = toLocalInput(row.remind_end_at)
      if (endLocal && newVal > endLocal) {
        alert('提醒启动时间不能晚于提醒结束时间')
        return
      }
    }
    try {
      const fn = type === 'receivables' ? updateReceivableRemindStart : updateTrustRemindStart
      const payloadVal = fromLocalInput(newVal)
      await fn(row.id, payloadVal)
      setItems(prev => prev.map(r => r.id === row.id
        ? { ...r, remind_start_at: payloadVal ? payloadVal + ':00' : null }
        : r))
    } catch (e) {
      alert(e.response?.data?.detail || '更新失败')
    }
  }

  const openSend = async () => {
    setShowSend(true)
    setSendResult(null)
    setSelectedPerson('')
    setFreq('once')
    setSendMode(selectedIds.size > 0 ? 'selected' : 'all')
    if (persons.length === 0) await loadPersons()
  }
  const doSend = async () => {
    setSending(true)
    setSendResult(null)
    try {
      // 计算本次实际允许的通道(按 chip 顺序: 钉钉 -> 微信 -> 短信)
      const chipOrder = ['dingtalk_corp', 'wechat_mp', 'sms_custom', 'sms_aliyun', 'sms_tencent']
      const channels = chipOrder.filter(v => enabledChannels[v])
      const payload = {
        record_type: type,
        frequency: freq,
        channels: channels.length ? channels : undefined,
      }
      if (sendMode === 'selected') {
        payload.record_ids = Array.from(selectedIds)
      } else if (sendMode === 'person' && selectedPerson) {
        payload.person_name = selectedPerson
      } else {
        // 'all' = 全量所有页(后端不再过滤)
      }
      const r = await sendFinanceReminder(payload)
      setSendResult(r.data)
      load()
      loadPersons()
    } catch (e) {
      setSendResult({ success: false, error: e.response?.data?.detail || e.message })
    } finally {
      setSending(false)
    }
  }

  const toggleSelectAll = (checked) => {
    setSelectedIds(prev => {
      const n = new Set(prev)
      const visibleIds = items.map(r => r.id)
      if (checked) visibleIds.forEach(id => n.add(id))
      else visibleIds.forEach(id => n.delete(id))
      return n
    })
  }
  const toggleSelectOne = (id, checked) => {
    setSelectedIds(prev => {
      const n = new Set(prev)
      if (checked) n.add(id); else n.delete(id)
      return n
    })
  }
  const allVisibleSelected = items.length > 0 && items.every(r => selectedIds.has(r.id))

  // 单条删除
  const confirmDeleteOne = async (row) => {
    const label = type === 'receivables'
      ? `合同 ${row.contract_no || '-'} 项目 ${row.project_name || '-'}`
      : `科目 ${row.subject_name || '-'}`
    if (!window.confirm(`确定要删除这条记录吗？\n\n${label}\n\n此操作不可撤销！`)) return
    try {
      const fn = type === 'receivables' ? deleteReceivable : deleteTrust
      await fn(row.id)
      // 从选中集合里清掉
      setSelectedIds(prev => {
        const n = new Set(prev); n.delete(row.id); return n
      })
      load()
    } catch (e) {
      alert(e.response?.data?.detail || '删除失败')
    }
  }
  // 批量删除
  const confirmBulkDelete = async () => {
    if (selectedIds.size === 0) return
    if (!window.confirm(`确定要删除选中的 ${selectedIds.size} 条记录吗？\n\n此操作不可撤销！`)) return
    try {
      const fn = type === 'receivables' ? deleteReceivablesBulk : deleteTrustsBulk
      const r = await fn(Array.from(selectedIds))
      const n = r.data?.deleted_count ?? selectedIds.size
      alert(`✅ 已删除 ${n} 条记录`)
      setSelectedIds(new Set())
      load()
    } catch (e) {
      alert(e.response?.data?.detail || '删除失败')
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-4 space-y-3">
      {/* 第一行: 搜索 + 通道 chip */}
      <div className="flex flex-wrap items-center gap-2">
        <input value={q} onChange={e => { setQ(e.target.value); setPage(1) }}
          placeholder="搜索项目/客户/合同号/电话..."
          className="px-3 py-2 border rounded text-sm w-64" />
        <button onClick={load} className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm">🔄 查询</button>
        {/* 三色通道 chip: 同尺寸不同色, 可勾选(本次发送有效) */}
        <div className="flex flex-wrap items-center gap-1.5 ml-2">
          {CHANNEL_CHIPS.map(c => {
            const on = !!enabledChannels[c.v]
            return (
              <label key={c.v}
                className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full border text-xs font-medium cursor-pointer select-none transition ${TONE[c.tone][on ? 'on' : 'off']}`}>
                <input type="checkbox" className="hidden"
                  checked={on}
                  onChange={e => setEnabledChannels(s => ({ ...s, [c.v]: e.target.checked }))} />
                <span className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center text-[10px] ${on ? 'border-white bg-white/20' : 'border-current'}`}>
                  {on ? '✓' : ''}
                </span>
                {c.label}
              </label>
            )
          })}
        </div>
      </div>
      {/* 第二行: 操作按钮 (不受第一行 chip 数量影响, 保证始终可见) */}
      <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-gray-100">
        <span className="text-xs text-gray-500">
          已选 <b className="text-blue-600">{selectedIds.size}</b> 条
          {selectedIds.size > 0 && (
            <button onClick={() => setSelectedIds(new Set())}
              className="ml-2 text-xs text-gray-400 hover:text-red-500">清空</button>
          )}
        </span>
        {selectedIds.size > 0 && (
          <button onClick={confirmBulkDelete}
            className="px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-700 border border-red-300 text-xs rounded shadow-sm">
            🗑 批量删除 ({selectedIds.size})
          </button>
        )}
        <button onClick={openSend}
          className="px-4 py-1.5 bg-amber-500 hover:bg-amber-600 text-white text-sm rounded shadow-sm">
          📱 发送催收
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-700">
            <tr>
              <th className="px-2 py-2 w-8 text-center">
                <input type="checkbox" checked={allVisibleSelected}
                  onChange={e => toggleSelectAll(e.target.checked)} />
              </th>
              {columns.map(c => (
                <th key={c.key} className="px-3 py-2 text-left whitespace-nowrap">{c.label}</th>
              ))}
              <th className="px-2 py-2 w-12 text-center">操作</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={columns.length + 1} className="text-center py-8 text-gray-400">加载中…</td></tr>}
            {!loading && items.length === 0 && (
              <tr><td colSpan={columns.length + 1} className="text-center py-8 text-gray-400">暂无数据</td></tr>
            )}
            {!loading && items.map(row => (
              <tr key={row.id} className={`border-t hover:bg-gray-50 ${selectedIds.has(row.id) ? 'bg-blue-50/50' : ''}`}>
                <td className="px-2 py-2 w-8 text-center">
                  <input type="checkbox" checked={selectedIds.has(row.id)}
                    onChange={e => toggleSelectOne(row.id, e.target.checked)} />
                </td>
                {columns.map(c => (
                  <td key={c.key} className="px-3 py-2 whitespace-nowrap">
                    {c.editable === 'datetime' ? (
                      <input type="datetime-local"
                        value={toLocalInput(row[c.key])}
                        onChange={e => {
                          if (c.key === 'remind_end_at') onChangeRemindEnd(row, e.target.value)
                          else if (c.key === 'remind_start_at') onChangeRemindStart(row, e.target.value)
                        }}
                        className="text-xs border rounded px-1 py-0.5 bg-white" />
                    ) : c.editable ? (
                      <select value={row[c.key] || 'once'}
                        onChange={e => onChangeFreq(row, e.target.value)}
                        className="text-xs border rounded px-1 py-0.5 bg-white">
                        {FREQ_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    ) : c.render ? c.render(row) : (row[c.key] || '-')}
                  </td>
                ))}
                <td className="px-2 py-2 w-12 text-center">
                  <button onClick={() => confirmDeleteOne(row)}
                    title="删除此条记录"
                    className="text-gray-400 hover:text-red-600 text-base px-1">
                    🗑
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={pageSize} total={total} onPage={setPage} />

      {showSend && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
             onClick={e => { if (e.target === e.currentTarget) setShowSend(false) }}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-bold text-gray-800 mb-3">📱 发送催收</h3>
            <p className="text-xs text-gray-500 mb-4">
              类型: {type === 'receivables' ? '应收款项' : '财务借支'}<br />
              提醒频率: {FREQ_LABEL[freq]} (本次发送的频率快照)<br />
              多个勾选通道按 钉钉 → 微信 → 短信 顺序回退, 命中即停。
            </p>
            <div className="mb-3">
              <label className="block text-sm font-medium text-gray-700 mb-1">发送范围</label>
              <div className="flex gap-2 mb-2">
                {[
                  { v: 'all',      l: '📢 全部人员' },
                  { v: 'person',   l: '👤 选人员' },
                  { v: 'selected', l: `☑ 选中行 (${selectedIds.size})` },
                ].map(m => (
                  <button key={m.v} type="button" onClick={() => setSendMode(m.v)}
                    disabled={m.v === 'selected' && selectedIds.size === 0}
                    className={`flex-1 px-2 py-1.5 rounded border text-xs ${sendMode === m.v ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 disabled:opacity-40'}`}>
                    {m.l}
                  </button>
                ))}
              </div>
              {sendMode === 'person' && (
                <select value={selectedPerson} onChange={e => setSelectedPerson(e.target.value)}
                  className="w-full border rounded px-3 py-2 text-sm">
                  <option value="">-- 请选择 --</option>
                  {persons.map(p => (
                    <option key={`${p.record_id}-${p.name}`} value={p.name}>
                      {p.name} ({p.phone})
                    </option>
                  ))}
                </select>
              )}
              {sendMode === 'selected' && (
                <div className="text-xs text-gray-500 bg-blue-50 border border-blue-200 rounded px-2 py-1.5">
                  将对 <b className="text-blue-700">{selectedIds.size}</b> 条已选记录发送催收 (跨页保留)
                </div>
              )}
              {sendMode === 'all' && (
                <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
                  将向 <b>全量所有页</b> 的全部记录发送催收
                </div>
              )}
            </div>
            <div className="mb-3">
              <label className="block text-sm font-medium text-gray-700 mb-1">频率</label>
              <select value={freq} onChange={e => setFreq(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm">
                {FREQ_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <p className="text-xs text-gray-400 mt-1">选 daily/weekly/monthly 时, 将按此频率持续发送, 需中途干预或停用</p>
            </div>
            {sendResult && (
              <div className={`mb-3 p-3 rounded text-sm ${sendResult.success ? 'bg-blue-50 text-blue-800' : 'bg-red-50 text-red-800'}`}>
                {sendResult.success ? (
                  <>
                    <div>✅ 完成,共 {sendResult.target_count} 条记录</div>
                    <div className="text-xs mt-1">
                      成功 {sendResult.sent} · 失败 {sendResult.failed} · 跳过 {sendResult.skipped} · 无通道 {sendResult.no_channel}
                    </div>
                    {sendResult.warning && <div className="text-xs text-amber-700 mt-1">⚠ {sendResult.warning}</div>}
                  </>
                ) : (
                  <>❌ {sendResult.error}</>
                )}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowSend(false)} className="px-4 py-2 border rounded text-gray-700 text-sm hover:bg-gray-50">关闭</button>
              <button onClick={doSend} disabled={sending}
                className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm rounded disabled:opacity-50">
                {sending ? '发送中…' : '确认发送'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Pagination({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="flex items-center justify-between text-xs text-gray-500 pt-2">
      <div>共 {total} 条 · 第 {page} / {pages} 页</div>
      <div className="flex gap-1">
        <button onClick={() => onPage(Math.max(1, page - 1))} disabled={page <= 1}
          className="px-3 py-1 border rounded disabled:opacity-30 hover:bg-gray-50">上一页</button>
        <button onClick={() => onPage(Math.min(pages, page + 1))} disabled={page >= pages}
          className="px-3 py-1 border rounded disabled:opacity-30 hover:bg-gray-50">下一页</button>
      </div>
    </div>
  )
}

// ================= 发送日志 =================
function LogsTab() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [type, setType] = useState('')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)
  const load = async () => {
    setLoading(true)
    try {
      const r = await getFinanceReminderLogs({
        page, page_size: 50,
        record_type: type || undefined,
        status: status || undefined,
      })
      setItems(r.data.items || [])
      setTotal(r.data.total || 0)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [page, type, status])
  return (
    <div className="bg-white rounded-lg shadow p-4 space-y-3">
      <div className="flex items-center gap-2">
        <select value={type} onChange={e => { setType(e.target.value); setPage(1) }}
          className="border rounded px-2 py-1 text-sm">
          <option value="">全部类型</option>
          <option value="receivables">应收款项</option>
          <option value="trust">财务借支</option>
        </select>
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(1) }}
          className="border rounded px-2 py-1 text-sm">
          <option value="">全部状态</option>
          <option value="sent">sent</option>
          <option value="failed">failed</option>
          <option value="skipped">skipped</option>
          <option value="pending">pending</option>
        </select>
        <button onClick={load} className="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-sm">🔄 刷新</button>
        <div className="flex-1" />
        <span className="text-xs text-gray-500">共 {total} 条</span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead className="bg-gray-50 text-gray-700">
            <tr>
              <th className="px-3 py-2 text-left">时间</th>
              <th className="px-3 py-2 text-left">类型</th>
              <th className="px-3 py-2 text-left">记录ID</th>
              <th className="px-3 py-2 text-left">收件人</th>
              <th className="px-3 py-2 text-left">手机</th>
              <th className="px-3 py-2 text-left">通道</th>
              <th className="px-3 py-2 text-left">状态</th>
              <th className="px-3 py-2 text-left">错误</th>
              <th className="px-3 py-2 text-left">操作员</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={9} className="text-center py-6 text-gray-400">加载中…</td></tr>}
            {!loading && items.length === 0 && (
              <tr><td colSpan={9} className="text-center py-6 text-gray-400">暂无日志</td></tr>
            )}
            {items.map(it => (
              <tr key={it.id} className="border-t hover:bg-gray-50">
                <td className="px-3 py-1.5 whitespace-nowrap">{it.created_at?.replace('T', ' ').slice(0, 19)}</td>
                <td className="px-3 py-1.5">{it.record_type}</td>
                <td className="px-3 py-1.5">{it.record_id}</td>
                <td className="px-3 py-1.5">{it.recipient || '-'}</td>
                <td className="px-3 py-1.5">{it.phone || '-'}</td>
                <td className="px-3 py-1.5">{it.channel_type || '-'}</td>
                <td className="px-3 py-1.5">
                  <span className={`inline-block px-2 py-0.5 rounded ${STATUS_TAG[it.status] || STATUS_TAG.pending}`}>
                    {it.status}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-red-600 max-w-xs truncate" title={it.error}>{it.error || '-'}</td>
                <td className="px-3 py-1.5">{it.operator_name || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={50} total={total} onPage={setPage} />
    </div>
  )
}
