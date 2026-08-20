import { useState, useEffect, useMemo } from 'react'
import {
  listFollowups, exportFollowups, getFollowupSummary, getFollowupTimeline,
  createFollowup, updateFollowup, deleteFollowup,
  getFollowupStageOptions,
  getFollowableProjects,
  getFollowupTemplate,
} from '../api'
import { useAuthStore } from '../stores/auth'
import dayjs from 'dayjs'
import weekOfYear from 'dayjs/plugin/weekOfYear'

dayjs.extend(weekOfYear)

const STAGE_COLORS = {
  '需求对接': 'bg-blue-100 text-blue-700',
  '方案提供': 'bg-cyan-100 text-cyan-700',
  '商务沟通': 'bg-amber-100 text-amber-700',
  '投标报价': 'bg-purple-100 text-purple-700',
  '其他': 'bg-gray-100 text-gray-600',
}

// 获取当前时间字符串（YYYY-MM-DD HH:mm）
function nowString() {
  return dayjs().format('YYYY-MM-DD HH:mm')
}

export default function ProjectFollowups() {
  const { user } = useAuthStore()

  // 列表 / 筛选
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState({
    project_name: '', stage: '', responsible_sales: '',
  })
  // 是否按项目维度聚合（默认 true：每个项目仅显示最新一条；查看时间轴显示全部历史）
  const [aggregate, setAggregate] = useState(true)
  // 导出中标志
  const [exporting, setExporting] = useState(false)

  // 汇总
  const [summary, setSummary] = useState(null)
  const [stageOptions, setStageOptions] = useState([])

  // 当前账号可新建跟单的项目（自建 + 责任销售是自己的，已审批）
  const [followableProjects, setFollowableProjects] = useState([])

  // 列表中多选的项目（用于按项目导出 Excel）
  const [selectedProjectIds, setSelectedProjectIds] = useState([])

  // 新建/编辑弹窗
  const [showForm, setShowForm] = useState(false)
  const [editRecord, setEditRecord] = useState(null)
  const [form, setForm] = useState(emptyForm())
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // 汇报时间：弹窗打开时实时显示当前时间，每分钟刷新
  const [reportTimeStr, setReportTimeStr] = useState(nowString())
  const [projectKeyword, setProjectKeyword] = useState('')
  // 复合下拉：是否打开
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false)

  // 时间轴弹窗
  const [showTimeline, setShowTimeline] = useState(false)
  const [timeline, setTimeline] = useState([])
  const [timelineProject, setTimelineProject] = useState(null)
  const [timelineLoading, setTimelineLoading] = useState(false)

  // 跟单模板（从 form_templates 表中读取「项目跟单登记表」）
  const [template, setTemplate] = useState(null)

  function emptyForm() {
    return {
      project_id: '',
      stage: '需求对接',
      progress: '',
      risks: '',
      next_plan: '',
      next_owner: '',
      next_deadline: '',
      expected_amount: '',
      expected_sign_date: '',
      form_data: {},
    }
  }

  useEffect(() => {
    getFollowupStageOptions().then(r => setStageOptions(r.data)).catch(() => {})
    fetchSummary()
    // 拉取当前账号可新建跟单的项目（一次性返回）
    fetchFollowableProjects()
    // 拉取跟单模板（用于动态渲染表单）
    getFollowupTemplate().then(r => setTemplate(r.data)).catch(() => {})
  }, [])

  // 汇报时间：弹窗打开时每分钟刷新到当前时间，确保显示总是最新
  useEffect(() => {
    if (!showForm) return
    setReportTimeStr(nowString())
    const t = setInterval(() => setReportTimeStr(nowString()), 60_000)
    return () => clearInterval(t)
  }, [showForm])

  // 点击外部关闭复合下拉
  useEffect(() => {
    if (!projectDropdownOpen) return
    const onClick = (e) => {
      const el = e.target
      // 点击项目下拉区域（含 input/button/选项 div）不关闭
      if (el.closest && el.closest('[data-project-dropdown]')) return
      setProjectDropdownOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [projectDropdownOpen])

  const fetchFollowableProjects = async () => {
    try {
      const r = await getFollowableProjects()
      setFollowableProjects(r.data || [])
    } catch (e) { console.error(e) }
  }

  useEffect(() => { fetchList() }, [page, filters, aggregate])

  const fetchSummary = async () => {
    try {
      const r = await getFollowupSummary()
      setSummary(r.data)
    } catch (e) { console.error(e) }
  }

  const fetchList = async () => {
    setLoading(true)
    try {
      const params = {
        page, page_size: 20,
        aggregate,
        ...(filters.project_name ? { project_name: filters.project_name } : {}),
        ...(filters.stage ? { stage: filters.stage } : {}),
        ...(filters.responsible_sales ? { responsible_sales: filters.responsible_sales } : {}),
      }
      const r = await listFollowups(params)
      setItems(r.data.items || [])
      setTotal(r.data.total || 0)
    } catch (e) { console.error(e) } finally {
      setLoading(false)
    }
  }

  // ---------- 操作 ----------
  const openCreate = () => {
    setEditRecord(null)
    setForm(emptyForm())
    setFormError('')
    setProjectKeyword('')
    setProjectDropdownOpen(false)
    setReportTimeStr(nowString())  // 汇报时间：当前时间
    setShowForm(true)
    // 每次打开都重新拉取最新可新建跟单的项目
    fetchFollowableProjects()
    // 重新拉模板（保证是最新）
    getFollowupTemplate().then(r => setTemplate(r.data)).catch(() => {})
  }

  const openEdit = (rec) => {
    // 权限：仅 admin 或 reporter 本人可编辑
    const isAdmin = user?.role === 'admin'
    const isReporter = rec.reporter_id === user?.id
    if (!isAdmin && !isReporter) {
      alert('仅创建人本人或管理员可编辑')
      return
    }
    setEditRecord(rec)
    setForm({
      project_id: rec.project_id,
      stage: rec.stage,
      progress: rec.progress || '',
      risks: rec.risks || '',
      next_plan: rec.next_plan || '',
      next_owner: rec.next_owner || '',
      next_deadline: rec.next_deadline || '',
      expected_amount: rec.expected_amount ?? '',
      expected_sign_date: rec.expected_sign_date || '',
      form_data: rec.form_data || {},
    })
    setFormError('')
    setReportTimeStr(nowString())  // 汇报时间：编辑时也重置为当前时间
    setShowForm(true)
  }

  // 列表中切换单个项目的选中状态
  const toggleSelectProject = (projectId) => {
    setSelectedProjectIds(arr => arr.includes(projectId)
      ? arr.filter(x => x !== projectId)
      : [...arr, projectId])
  }
  // 切换"全选当前页"
  const toggleSelectAll = () => {
    const pageIds = items.map(it => it.project_id)
    const allSelected = pageIds.length > 0 && pageIds.every(id => selectedProjectIds.includes(id))
    if (allSelected) {
      setSelectedProjectIds(arr => arr.filter(x => !pageIds.includes(x)))
    } else {
      setSelectedProjectIds(arr => Array.from(new Set([...arr, ...pageIds])))
    }
  }

  // 导出 Excel：按当前筛选条件 + 选中项目导出
  // 注意：导出时强制 aggregate=false（导出该项目的全部历史跟单），
  // 列表的 aggregate state 仅影响列表显示，不影响导出。
  const doExport = async () => {
    if (exporting) return
    setExporting(true)
    try {
      const params = {
        aggregate: false,  // 导出全部历史（用户明确需求：和查看时间轴内容一致）
        ...(filters.project_name ? { project_name: filters.project_name } : {}),
        ...(filters.stage ? { stage: filters.stage } : {}),
        ...(filters.responsible_sales ? { responsible_sales: filters.responsible_sales } : {}),
        ...(selectedProjectIds.length > 0 ? { project_ids: selectedProjectIds.join(',') } : {}),
      }
      const r = await exportFollowups(params)
      // 从响应头解析文件名（fallback 到默认）
      const dispo = r.headers?.['content-disposition'] || ''
      const m = dispo.match(/filename=([^;]+)/)
      const fname = m ? decodeURIComponent(m[1]) : `project_followups_${dayjs().format('YYYYMMDD_HHmmss')}.xlsx`
      // 用浏览器下载
      const url = URL.createObjectURL(new Blob([r.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = fname
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('导出失败:', e)
      alert('导出失败：' + (e?.message || '未知错误'))
    } finally {
      setExporting(false)
    }
  }

  // 后端约定字段（存到 ProjectFollowup 表的固定列，不是 form_data）
  const BACKEND_FIXED_KEYS = new Set([
    'progress', 'risks', 'next_plan', 'next_owner',
    'next_deadline', 'expected_amount', 'expected_sign_date',
  ])

  // 模板字段按 section 分组
  const getTemplateSections = () => {
    if (!template || !template.fields) return []
    const map = new Map()
    template.fields.forEach(f => {
      const s = f.section || '其他'
      if (!map.has(s)) map.set(s, [])
      map.get(s).push(f)
    })
    return Array.from(map.entries()).map(([name, fields]) => ({ name, fields }))
  }

  // 读取模板字段当前值（兼容后端固定列 + form_data）
  const getFieldValue = (f) => {
    if (BACKEND_FIXED_KEYS.has(f.key)) return form[f.key] ?? ''
    return (form.form_data || {})[f.key] ?? ''
  }

  // 写入模板字段值
  const setFieldValue = (f, v) => {
    if (BACKEND_FIXED_KEYS.has(f.key)) {
      setForm(prev => ({ ...prev, [f.key]: v }))
    } else {
      setForm(prev => ({
        ...prev,
        form_data: { ...(prev.form_data || {}), [f.key]: v },
      }))
    }
  }

  const submitForm = async () => {
    if (!form.project_id) {
      setFormError('请选择关联项目')
      throw new Error('请选择关联项目')
    }
    if (!form.stage) {
      setFormError('请选择所处阶段')
      throw new Error('请选择所处阶段')
    }
    // 必填校验：遍历模板 required 字段
    if (template && template.fields) {
      for (const f of template.fields) {
        if (!f.required) continue
        const v = BACKEND_FIXED_KEYS.has(f.key) ? form[f.key] : (form.form_data || {})[f.key]
        if (!v || (typeof v === 'string' && !v.trim())) {
          const msg = `请填写「${f.label || f.key}」`
          setFormError(msg)
          throw new Error(msg)
        }
      }
    } else if (!form.progress || !form.progress.trim()) {
      // 模板未加载时兜底：仍然校验 progress 必填
      const msg = '请填写当前进展描述'
      setFormError(msg)
      throw new Error(msg)
    }
    setSubmitting(true)
    try {
      const payload = {
        project_id: Number(form.project_id),
        stage: form.stage,
        progress: form.progress || null,
        risks: form.risks || null,
        next_plan: form.next_plan || null,
        next_owner: form.next_owner || null,
        next_deadline: form.next_deadline || null,
        expected_amount: form.expected_amount === '' ? null : Number(form.expected_amount),
        expected_sign_date: form.expected_sign_date || null,
        form_data: form.form_data && Object.keys(form.form_data).length > 0 ? form.form_data : null,
      }
      let saved
      if (editRecord) {
        saved = await updateFollowup(editRecord.id, payload)
      } else {
        saved = await createFollowup(payload)
      }
      return saved
    } catch (e) {
      // 提取友好错误信息（避免显示 Pydantic 完整堆栈）
      let msg = '保存失败'
      const detail = e?.response?.data?.detail
      if (typeof detail === 'string') {
        msg = detail
      } else if (Array.isArray(detail) && detail.length > 0) {
        // FastAPI 422 错误：detail 是 [{loc, msg, type, ...}, ...]
        msg = detail.map(d => d?.msg || JSON).join('；') || '提交数据有误'
      } else if (typeof detail === 'object' && detail) {
        msg = JSON.stringify(detail)
      } else if (e?.message) {
        // 处理 Pydantic "1 validation error for..." 这种长字符串
        if (e.message.includes('validation error')) {
          const m = e.message.match(/Input should be (a valid )?([^,]+)/)
          msg = m ? `字段格式不正确：${m[2]}` : '数据格式校验失败'
        } else {
          msg = e.message
        }
      }
      setFormError(msg)
      throw e
    } finally {
      setSubmitting(false)
    }
  }

  const submitAndClose = async () => {
    try {
      await submitForm()
      // 成功：关闭弹窗 + 刷新列表
      setShowForm(false)
      await fetchList()
      await fetchSummary()
    } catch (e) {
      // 校验失败或后端错误：formError 已在 submitForm 中设置，保持弹窗打开
      console.error('保存跟单失败:', e)
    }
  }

  const removeRecord = async (rec) => {
    if (!confirm(`确认删除这条跟单记录？`)) return
    try {
      await deleteFollowup(rec.id)
      fetchList(); fetchSummary()
    } catch (e) {
      alert(e?.response?.data?.detail || e?.message || '删除失败')
    }
  }

  const openTimeline = async (projectId) => {
    setShowTimeline(true)
    setTimelineProject(followableProjects.find(p => p.id === projectId) || null)
    setTimelineLoading(true)
    try {
      // 确保模板已加载（用于渲染字段名/格式化）
      if (!template) {
        try {
          const tr = await getFollowupTemplate()
          setTemplate(tr.data)
        } catch (_) { /* 兜底显示 form_data */ }
      }
      const r = await getFollowupTimeline(projectId)
      setTimeline(r.data || [])
    } catch (e) {
      console.error(e)
      setTimeline([])
    } finally {
      setTimelineLoading(false)
    }
  }

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / 20)), [total])

  // ---------- 渲染 ----------
  return (
    <div className="p-6 bg-gray-50 min-h-full">
      {/* 汇总 */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {stageOptions.map(s => {
            const item = (summary.by_stage || []).find(x => x.stage === s)
            const count = item?.count || 0
            return (
              <div key={s} className="bg-white rounded-lg shadow p-4">
                <div className="text-xs text-gray-500">{s}</div>
                <div className="text-2xl font-bold mt-1 text-gray-800">{count}</div>
              </div>
            )
          })}
          <div className="bg-white rounded-lg shadow p-4 col-span-2 md:col-span-1">
            <div className="text-xs text-gray-500">涉及项目数</div>
            <div className="text-2xl font-bold mt-1 text-gray-800">
              {summary.projects_with_followup}
            </div>
            <div className="text-xs text-gray-400 mt-1">
              预计成交合计：{summary.expected_total_amount?.toLocaleString()} 万
            </div>
          </div>
        </div>
      )}

      {/* 工具栏 */}
      <div className="bg-white rounded-lg shadow p-4 mb-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-bold text-gray-800 mr-auto">项目跟单 / 项目汇报</h2>
          <button
            onClick={doExport}
            disabled={exporting}
            title={
              selectedProjectIds.length > 0
                ? `导出所选 ${selectedProjectIds.length} 个项目的全部历史跟单`
                : '导出当前筛选条件下所有项目的全部历史跟单（未选中项目时按列表全部导出）'
            }
            className={`px-4 py-2 rounded border ${
              exporting
                ? 'border-gray-300 text-gray-400 cursor-not-allowed'
                : 'border-blue-500 text-blue-600 hover:bg-blue-50'
            }`}
          >
            {exporting
              ? '导出中…'
              : selectedProjectIds.length > 0
                ? `⤓ 导出所选 ${selectedProjectIds.length} 项`
                : '⤓ 导出 Excel（全部历史）'}
          </button>
          <button
            onClick={openCreate}
            disabled={followableProjects.length === 0}
            title={followableProjects.length === 0
              ? '您没有可跟单的项目（请确认：您自建的项目 或 责任销售是您本人的项目）'
              : ''}
            className={`px-4 py-2 rounded text-white ${
              followableProjects.length === 0
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            + 新建跟单
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-3 text-sm">
          <input
            placeholder="项目名称"
            value={filters.project_name}
            onChange={e => { setPage(1); setFilters(f => ({ ...f, project_name: e.target.value })) }}
            className="px-3 py-1.5 border rounded w-48"
          />
          <input
            placeholder="责任销售"
            value={filters.responsible_sales}
            onChange={e => { setPage(1); setFilters(f => ({ ...f, responsible_sales: e.target.value })) }}
            className="px-3 py-1.5 border rounded w-48"
          />
          <select
            value={filters.stage}
            onChange={e => { setPage(1); setFilters(f => ({ ...f, stage: e.target.value })) }}
            className="px-3 py-1.5 border rounded"
          >
            <option value="">全部阶段</option>
            {stageOptions.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <label className="flex items-center gap-2 px-2 py-1 border rounded bg-gray-50 cursor-pointer">
            <input
              type="checkbox"
              checked={aggregate}
              onChange={e => { setPage(1); setAggregate(e.target.checked) }}
              className="accent-blue-600"
            />
            <span className="text-gray-700">按项目聚合（每项目显示最新一条；查看时间轴显示全部历史）</span>
          </label>
          <button
            onClick={() => setFilters({ project_name: '', stage: '', responsible_sales: '' })}
            className="px-3 py-1.5 border rounded text-gray-600"
          >
            重置
          </button>
        </div>
      </div>

      {/* 列表 */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-2 py-3 text-center w-10">
                <input
                  type="checkbox"
                  checked={items.length > 0 && items.every(it => selectedProjectIds.includes(it.project_id))}
                  ref={el => el && (el.indeterminate = !items.every(it => selectedProjectIds.includes(it.project_id)) && items.some(it => selectedProjectIds.includes(it.project_id)))}
                  onChange={toggleSelectAll}
                  title="全选当前页"
                  className="accent-blue-600 cursor-pointer"
                />
              </th>
              <th className="px-4 py-3 text-left">项目名称</th>
              <th className="px-4 py-3 text-left">所处阶段</th>
              <th className="px-4 py-3 text-left">当前进展</th>
              <th className="px-4 py-3 text-left">责任人</th>
              <th className="px-4 py-3 text-right">预计成交(万)</th>
              <th className="px-4 py-3 text-left">责任销售</th>
              <th className="px-4 py-3 text-left">汇报时间</th>
              <th className="px-4 py-3 text-left">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">加载中…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">暂无数据</td></tr>
            )}
            {!loading && items.map(it => {
              const proj = followableProjects.find(p => p.id === it.project_id)
              const projName = it.project_name || proj?.project_name || `#${it.project_id}`
              return (
                <tr key={it.id} className="hover:bg-gray-50">
                  <td className="px-2 py-3 text-center w-10">
                    <input
                      type="checkbox"
                      checked={selectedProjectIds.includes(it.project_id)}
                      onChange={() => toggleSelectProject(it.project_id)}
                      title="选择此项目（导出时只导出所选项目的全部历史）"
                      className="accent-blue-600 cursor-pointer"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => openTimeline(it.project_id)}
                      className="text-blue-600 hover:underline"
                    >
                      {projName}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${STAGE_COLORS[it.stage] || STAGE_COLORS['其他']}`}>
                      {it.stage}
                    </span>
                  </td>
                  <td className="px-4 py-3 max-w-md truncate" title={it.progress}>
                    {it.progress || '-'}
                  </td>
                  <td className="px-4 py-3">{it.next_owner || '-'}</td>
                  <td className="px-4 py-3 text-right">
                    {it.expected_amount != null ? Number(it.expected_amount).toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-3">{it.responsible_sales || '-'}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {dayjs(it.created_at).format('YYYY-MM-DD HH:mm')}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {(() => {
                      const isAdmin = user?.role === 'admin'
                      const isReporter = it.reporter_id === user?.id
                      return (
                        <>
                          {/* 查看：所有角色都可见 */}
                          <button
                            onClick={() => openTimeline(it.project_id)}
                            className="text-blue-600 hover:underline mr-3"
                          >查看</button>
                          {/* 编辑：仅 admin 或 reporter 本人可见 */}
                          {(isAdmin || isReporter) && (
                            <button
                              onClick={() => openEdit(it)}
                              className="text-blue-600 hover:underline mr-3"
                            >编辑</button>
                          )}
                          {/* 删除：仅 admin 可见（后端校验也仅允许 admin） */}
                          {isAdmin && (
                            <button
                              onClick={() => removeRecord(it)}
                              className="text-red-600 hover:underline"
                            >删除</button>
                          )}
                        </>
                      )
                    })()}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div className="flex items-center justify-end gap-3 px-4 py-3 text-sm text-gray-600">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            className="px-3 py-1 border rounded disabled:opacity-40"
          >上一页</button>
          <span>第 {page} / {totalPages} 页</span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            className="px-3 py-1 border rounded disabled:opacity-40"
          >下一页</button>
        </div>
      </div>

      {/* 新建/编辑弹窗 */}
      {showForm && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-gray-800">
                  {editRecord ? '编辑跟单' : '新建跟单'}
                </h3>
                <button onClick={() => setShowForm(false)} className="text-gray-500 hover:text-gray-700">
                  ✕
                </button>
              </div>
              {formError && (
                <div className="mb-3 px-3 py-2 bg-red-50 text-red-700 text-sm rounded">{formError}</div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <label className="text-sm">
                  <div className="text-gray-600 mb-1">关联项目 <span className="text-red-500">*</span></div>
                  {editRecord ? (
                    <div className="w-full px-3 py-2 border rounded bg-gray-100 text-gray-700">
                      {/* 编辑时：项目不可改，显示当前项目名 */}
                      {(() => {
                        const cur = followableProjects.find(p => String(p.id) === String(form.project_id))
                          || items.find(i => i.project_id === Number(form.project_id))
                        if (cur) {
                          const pn = cur.project_name || cur.projectName || `#${form.project_id}`
                          return pn
                        }
                        return form.project_id ? `#${form.project_id}` : '-'
                      })()}
                    </div>
                  ) : (
                    <>
                  {/* 复合下拉：选择框 + 下拉列表（一体化设计） */}
                      <div data-project-dropdown className="relative">
                        {/* 选择框：已选择时显示项目名 + 清除 + 箭头；未选择时显示 placeholder */}
                        <div
                          onClick={() => {
                            if (!projectDropdownOpen) setProjectDropdownOpen(true)
                          }}
                          className={`relative w-full px-3 py-2 border rounded cursor-pointer flex items-center justify-between text-sm bg-white ${
                            form.project_id ? 'border-blue-400' : 'border-gray-300'
                          }`}
                        >
                          {form.project_id ? (() => {
                            const sel = followableProjects.find(p => String(p.id) === String(form.project_id))
                            if (sel) {
                              return (
                                <div className="flex items-center gap-1.5 min-w-0">
                                  <span className="inline-block px-1.5 py-0.5 bg-blue-600 text-white text-xs rounded shrink-0">✓</span>
                                  <span className="truncate text-gray-800">
                                    [{sel.source === 'self' ? '自营' : '渠道'}] {sel.project_name}
                                    {sel.project_code && <span className="text-gray-500"> ({sel.project_code})</span>}
                                    {sel.responsible_sales && <span className="text-gray-500 ml-1">· {sel.responsible_sales}</span>}
                                  </span>
                                </div>
                              )
                            }
                            return <span className="text-gray-500">已选择 #{form.project_id}</span>
                          })() : (
                            <span className="text-gray-400">搜索并选择项目…</span>
                          )}
                          <div className="flex items-center gap-1 shrink-0">
                            {form.project_id && (
                              <button
                                type="button"
                                onMouseDown={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  setForm(f => ({ ...f, project_id: '' }))
                                  setProjectKeyword('')
                                }}
                                onClick={(e) => e.stopPropagation()}
                                className="text-gray-400 hover:text-red-500 text-base leading-none px-1"
                                title="清除"
                              >×</button>
                            )}
                            <span className="text-gray-400 text-xs">▼</span>
                          </div>
                        </div>
                        {/* 下拉面板：搜索框 + 选项列表 */}
                        {projectDropdownOpen && (
                          <div className="absolute z-10 left-0 right-0 mt-1 border rounded bg-white shadow-lg">
                            {/* 内嵌搜索框 */}
                            <div className="border-b">
                              <input
                                autoFocus
                                placeholder="搜索项目名称/编号/责任销售…"
                                value={projectKeyword}
                                onChange={e => {
                                  setProjectKeyword(e.target.value)
                                  setProjectDropdownOpen(true)
                                }}
                                onClick={e => e.stopPropagation()}
                                className="w-full px-3 py-2 outline-none text-sm"
                              />
                            </div>
                            {/* 选项列表 */}
                            <div className="max-h-60 overflow-y-auto">
                              {(() => {
                                const kw = projectKeyword.trim().toLowerCase()
                                const filtered = kw
                                  ? followableProjects.filter(p =>
                                      (p.project_name || '').toLowerCase().includes(kw) ||
                                      (p.project_code || '').toLowerCase().includes(kw) ||
                                      (p.responsible_sales || '').toLowerCase().includes(kw)
                                    )
                                  : followableProjects
                                if (filtered.length === 0) {
                                  return (
                                    <div className="px-3 py-3 text-sm text-gray-400 text-center">
                                      无匹配项目（您可能没有自建的项目或责任销售不是您本人）
                                    </div>
                                  )
                                }
                                return filtered.map(p => (
                                  <div
                                    key={p.id}
                                    onMouseDown={(e) => {
                                      // 用 onMouseDown 而非 onClick + preventDefault，
                                      // 阻止 input 重新获取焦点导致 setProjectDropdownOpen(true)
                                      // 覆盖 setProjectDropdownOpen(false)
                                      e.preventDefault()
                                      e.stopPropagation()
                                      setForm(f => ({ ...f, project_id: String(p.id) }))
                                      setProjectKeyword('')
                                      setProjectDropdownOpen(false)
                                    }}
                                    className={`px-3 py-2 text-sm cursor-pointer hover:bg-blue-50 ${
                                      String(form.project_id) === String(p.id) ? 'bg-blue-50 font-medium' : ''
                                    }`}
                                  >
                                    [{p.source === 'self' ? '自营' : '渠道'}] {p.project_name}
                                    {p.project_code && <span className="text-gray-400"> ({p.project_code})</span>}
                                    {p.responsible_sales && <span className="text-gray-400 ml-2">· {p.responsible_sales}</span>}
                                  </div>
                                ))
                              })()}
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="text-xs text-gray-400 mt-1">仅显示「您自建」或「责任销售是您本人」且「已审批通过」的项目</div>
                    </>
                  )}
                </label>
                <label className="text-sm">
                  <div className="text-gray-600 mb-1">所处阶段 <span className="text-red-500">*</span></div>
                  <select
                    value={form.stage}
                    onChange={e => setForm(f => ({ ...f, stage: e.target.value }))}
                    className="w-full px-3 py-2 border rounded"
                  >
                    {stageOptions.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </label>
                <label className="text-sm">
                  <div className="text-gray-600 mb-1">汇报时间</div>
                  <input
                    readOnly
                    value={reportTimeStr}
                    className="w-full px-3 py-2 border rounded bg-gray-100 text-gray-700 cursor-not-allowed"
                  />
                </label>
              </div>

              {/* 模板字段（按 section 分组渲染，所见即所得） */}
              {getTemplateSections().length > 0 && (
                <div className="mt-4 space-y-4">
                  {getTemplateSections().map(sec => (
                    <div key={sec.name} className="border-t pt-4">
                      <div className="text-sm font-medium text-gray-700 mb-3">
                        {sec.name} <span className="text-xs text-gray-400">（{sec.fields.length} 个字段）</span>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        {sec.fields.map(f => (
                          <label key={f.id} className={`text-sm ${f.type === 'textarea' ? 'col-span-2' : ''}`}>
                            <div className="text-gray-600 mb-1">
                              {f.label || f.key}
                              {f.required && <span className="text-red-500">*</span>}
                            </div>
                            {f.type === 'textarea' ? (
                              <textarea
                                rows={3}
                                placeholder={f.placeholder || ''}
                                value={getFieldValue(f)}
                                onChange={e => setFieldValue(f, e.target.value)}
                                className="w-full px-3 py-2 border rounded"
                              />
                            ) : f.type === 'date' ? (
                              <input
                                type="date"
                                value={getFieldValue(f) || ''}
                                onChange={e => setFieldValue(f, e.target.value)}
                                className="w-full px-3 py-2 border rounded"
                              />
                            ) : f.type === 'number' ? (
                              <input
                                type="number" step="0.01"
                                placeholder={f.placeholder || '0.00'}
                                value={getFieldValue(f)}
                                onChange={e => setFieldValue(f, e.target.value)}
                                className="w-full px-3 py-2 border rounded"
                              />
                            ) : f.type === 'select' ? (
                              <select
                                value={getFieldValue(f) || ''}
                                onChange={e => setFieldValue(f, e.target.value)}
                                className="w-full px-3 py-2 border rounded"
                              >
                                <option value="">请选择</option>
                                {(f.options || []).map((opt, i) => (
                                  <option key={i} value={opt}>{opt}</option>
                                ))}
                              </select>
                            ) : (
                              <input
                                type="text"
                                placeholder={f.placeholder || ''}
                                value={getFieldValue(f)}
                                onChange={e => setFieldValue(f, e.target.value)}
                                className="w-full px-3 py-2 border rounded"
                              />
                            )}
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {/* 模板未加载完成时的提示 */}
              {!template && (
                <div className="mt-4 text-xs text-gray-400">正在加载模板字段…</div>
              )}

              <div className="flex justify-end gap-3 mt-6">
                <button
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 border rounded text-gray-600"
                >取消</button>
                <button
                  disabled={submitting}
                  onClick={submitAndClose}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                >{submitting ? '提交中…' : (editRecord ? '保存修改' : '保存')}</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 时间轴弹窗 */}
      {showTimeline && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-gray-800">
                  跟单时间轴：{timelineProject?.project_name || `#${timelineProject?.id}`}
                </h3>
                <button onClick={() => setShowTimeline(false)} className="text-gray-500 hover:text-gray-700">✕</button>
              </div>
              {timelineLoading && <div className="text-gray-400 text-sm">加载中…</div>}
              {!timelineLoading && timeline.length === 0 && (
                <div className="text-gray-400 text-sm">该项目暂无跟单记录</div>
              )}
              <div className="space-y-4">
                {timeline.map(it => {
                  // 读取该条跟单的所有字段值：优先 ORM 列，再 form_data
                  const fd = it.form_data || {}
                  const get = (key) => {
                    if (!key) return null
                    // 先看 ORM 字段
                    if (it[key] !== undefined && it[key] !== null && it[key] !== '') return it[key]
                    // 再看 form_data
                    if (fd[key] !== undefined && fd[key] !== null && fd[key] !== '') return fd[key]
                    return null
                  }
                  // 当前模板的字段
                  const tplFields = template?.fields || []
                  return (
                    <div key={it.id} className="border-l-4 border-blue-400 pl-4 py-2 bg-gray-50 rounded-r">
                      <div className="flex items-center gap-2 text-gray-500 text-sm">
                        <span>{dayjs(it.created_at).format('YYYY-MM-DD HH:mm')}</span>
                        <span>·</span>
                        <span>汇报人 {it.reporter_name || '-'}</span>
                        <span className={`ml-auto px-2 py-0.5 rounded text-xs ${STAGE_COLORS[it.stage] || ''}`}>{it.stage}</span>
                      </div>
                      {/* 按模板字段展示（所见即所得）：每字段一行，已填显示值，未填显示"未填报" */}
                      <div className="mt-2 space-y-1 text-sm">
                        {tplFields.length > 0 ? tplFields.map(f => {
                          const v = get(f.key)
                          const formatted = v == null || v === ''
                            ? <span className="text-gray-400 italic">（未填报）</span>
                            : (typeof v === 'number' && f.type === 'number'
                              ? Number(v).toLocaleString()
                              : (f.type === 'date' && typeof v === 'string'
                                ? dayjs(v).format('YYYY-MM-DD')
                                : String(v)))
                          return (
                            <div key={f.id || f.key}>
                              <span className="text-gray-500">{f.label || f.key}：</span>
                              <span className="text-gray-800 whitespace-pre-wrap">{formatted}</span>
                            </div>
                          )
                        }) : (
                          // 模板未加载：兜底显示 form_data
                          Object.entries(fd).map(([k, v]) => (
                            <div key={k}>
                              <span className="text-gray-500">{k}：</span>
                              <span className="text-gray-800 whitespace-pre-wrap">{String(v)}</span>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}