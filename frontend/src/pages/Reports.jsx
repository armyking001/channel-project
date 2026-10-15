import { useState, useEffect } from 'react'
import {
  getReportSummary, getReportTrend, getReportByPartner,
  getReportByCooperation, getReportByWinBid, exportReport, exportFullReport,
  getReportByFollowupStage,
  getAIModelConfigs, getAIModelPresets, analyzeReportWithAI, askReportAssistant, createAIModelConfig, updateAIModelConfig, deleteAIModelConfig, testAIModelConfig,
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
  const [activeTab, setActiveTab] = useState('standard')
  const [keyword, setKeyword] = useState('')
  const [projectType, setProjectType] = useState('')
  const [projectName, setProjectName] = useState('')
  const [responsibleSales, setResponsibleSales] = useState('')
  const [winBidStatusFilter, setWinBidStatusFilter] = useState('')
  const [partnerCompany, setPartnerCompany] = useState('')
  const [amountMin, setAmountMin] = useState('')
  const [amountMax, setAmountMax] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [summary, setSummary] = useState(null)
  const [trend, setTrend] = useState([])
  const [partners, setPartners] = useState([])
  const [coop, setCoop] = useState([])
  const [winBid, setWinBid] = useState([])
  const [followupByStage, setFollowupByStage] = useState([])
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [fullExporting, setFullExporting] = useState(false)
  const [aiModels, setAiModels] = useState([])
  const [aiModelPresets, setAiModelPresets] = useState([])
  const [selectedModelId, setSelectedModelId] = useState('')
  const [aiPrompt, setAiPrompt] = useState('请分析当前筛选条件下自营项目与渠道项目的金额、状态和跟单阶段分布，并给出适合的展示建议。')
  const [aiDisplayType, setAiDisplayType] = useState('table')
  const [aiFields, setAiFields] = useState(['source_label', 'project_name', 'project_type', 'partner_company', 'project_amount', 'approval_status', 'latest_followup_stage'])
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResult, setAiResult] = useState(null)
  const [assistantQuestion, setAssistantQuestion] = useState('')
  const [assistantLoading, setAssistantLoading] = useState(false)
  const [assistantMessages, setAssistantMessages] = useState([
    { role: 'assistant', content: '你好，我是小销。你先点一次“开始 AI 分析”，我会基于当前筛选数据帮你做总结，也可以继续追问。' },
  ])
  const [showModelModal, setShowModelModal] = useState(false)
  const [editingModel, setEditingModel] = useState(null)
  const [selectedPresetKey, setSelectedPresetKey] = useState('')
  const [savingModel, setSavingModel] = useState(false)
  const [testingModelId, setTestingModelId] = useState(null)
  const [modelTestResults, setModelTestResults] = useState({})
  const [modelForm, setModelForm] = useState({
    name: '',
    model_type: 'local',
    provider: 'openai_compatible',
    base_url: '',
    model_name: '',
    api_key: '',
    temperature: 0.2,
    max_tokens: '',
    timeout_seconds: 60,
    is_enabled: true,
    is_default: false,
    notes: '',
  })

  const AI_FIELD_OPTIONS = [
    ['source_label', '项目来源'],
    ['project_name', '项目名称'],
    ['project_type', '项目类型'],
    ['partner_company', '合作单位'],
    ['responsible_sales', '责任销售'],
    ['project_amount', '项目金额'],
    ['expected_amount', '预计金额'],
    ['fee_amount', '费用金额'],
    ['approval_status', '审批状态'],
    ['win_bid_status', '中标状态'],
    ['latest_followup_stage', '最新跟单阶段'],
    ['latest_followup_expected_amount', '最新跟单预计金额'],
  ]
  const PROJECT_TYPE_OPTIONS = ['信息化', '智能化', '机电消防', '软件开放', '系统运维', 'XC/SM', '军队武警', '其他']
  const WIN_BID_OPTIONS = [
    ['yes', '中标'],
    ['in_progress', '进行中'],
    ['no', '未中标'],
  ]
  const AI_FIELD_LABELS = Object.fromEntries(AI_FIELD_OPTIONS)

  const params = () => {
    const p = {}
    if (keyword) p.keyword = keyword
    if (projectType) p.project_type = projectType
    if (projectName) p.project_name = projectName
    if (responsibleSales) p.responsible_sales = responsibleSales
    if (winBidStatusFilter) p.win_bid_status = winBidStatusFilter
    if (partnerCompany) p.partner_company = partnerCompany
    if (amountMin !== '') p.amount_min = Number(amountMin)
    if (amountMax !== '') p.amount_max = Number(amountMax)
    if (startDate) p.start_date = startDate
    if (endDate) p.end_date = endDate
    return p
  }

  const fetchAll = async () => {
    setLoading(true)
    try {
      const p = params()
      const [s, t, pp, cc, w, f] = await Promise.all([
        getReportSummary(p),
        getReportTrend(p),
        getReportByPartner(p),
        getReportByCooperation(p),
        getReportByWinBid(p),
        getReportByFollowupStage(p),
      ])
      setSummary(s.data)
      setTrend(t.data)
      setPartners(pp.data)
      setCoop(cc.data)
      setWinBid(w.data)
      setFollowupByStage(f.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [])
  useEffect(() => {
    getAIModelConfigs().then(r => {
      const models = r.data || []
      setAiModels(models)
      const defaultModel = models.find(m => m.is_default) || models[0]
      if (defaultModel) setSelectedModelId(String(defaultModel.id))
    }).catch(() => {})
    getAIModelPresets().then(r => {
      setAiModelPresets(r.data || [])
    }).catch(() => {})
  }, [])

  const refreshModels = async () => {
    const r = await getAIModelConfigs()
    const models = r.data || []
    setAiModels(models)
    const defaultModel = models.find(m => m.is_default) || models[0]
    if (defaultModel && !selectedModelId) setSelectedModelId(String(defaultModel.id))
  }

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

  const handleFullExport = async () => {
    setFullExporting(true)
    try {
      const res = await exportFullReport()
      const blob = new Blob([res.data])
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const cd = res.headers['content-disposition'] || ''
      const m = /filename=([^;]+)/.exec(cd)
      a.download = m ? m[1].trim() : 'projects_full.xlsx'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert('全量导出失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setFullExporting(false)
    }
  }

  const toggleAIField = (field) => {
    setAiFields(prev => prev.includes(field) ? prev.filter(item => item !== field) : [...prev, field])
  }

  const handleAIAnalyze = async () => {
    setAiLoading(true)
    try {
      const res = await analyzeReportWithAI({
        model_id: selectedModelId ? Number(selectedModelId) : null,
        prompt: aiPrompt,
        keyword: keyword || null,
        project_type: projectType || null,
        project_name: projectName || null,
        responsible_sales: responsibleSales || null,
        win_bid_status: winBidStatusFilter || null,
        partner_company: partnerCompany || null,
        amount_min: amountMin === '' ? null : Number(amountMin),
        amount_max: amountMax === '' ? null : Number(amountMax),
        start_date: startDate || null,
        end_date: endDate || null,
        fields: aiFields,
        display_type: aiDisplayType,
      })
      setAiResult(res.data)
      setAssistantMessages([
        { role: 'assistant', content: `你好，我是小销。${res.data.summary_text || res.data.answer || res.data.message}` },
      ])
    } catch (err) {
      alert('AI 分析失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setAiLoading(false)
    }
  }

  const handleAskAssistant = async () => {
    if (!assistantQuestion.trim()) return
    const question = assistantQuestion.trim()
    setAssistantLoading(true)
    setAssistantMessages(prev => [...prev, { role: 'user', content: question }])
    setAssistantQuestion('')
    try {
      const res = await askReportAssistant({
        model_id: selectedModelId ? Number(selectedModelId) : null,
        question,
        keyword: keyword || null,
        project_type: projectType || null,
        project_name: projectName || null,
        responsible_sales: responsibleSales || null,
        win_bid_status: winBidStatusFilter || null,
        partner_company: partnerCompany || null,
        amount_min: amountMin === '' ? null : Number(amountMin),
        amount_max: amountMax === '' ? null : Number(amountMax),
        start_date: startDate || null,
        end_date: endDate || null,
        history: assistantMessages,
      })
      setAssistantMessages(prev => [...prev, { role: 'assistant', content: res.data.answer }])
    } catch (err) {
      setAssistantMessages(prev => [...prev, { role: 'assistant', content: '小销刚才没有回答成功，请稍后再试。' }])
      alert('小销回答失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setAssistantLoading(false)
    }
  }

  const handleReset = () => {
    setKeyword('')
    setProjectType('')
    setProjectName('')
    setResponsibleSales('')
    setWinBidStatusFilter('')
    setPartnerCompany('')
    setAmountMin('')
    setAmountMax('')
    setStartDate('')
    setEndDate('')
    setTimeout(fetchAll, 0)
  }

  const openCreateModel = () => {
    setEditingModel(null)
    setSelectedPresetKey('')
    setModelForm({
      name: '',
      model_type: 'local',
      provider: 'ollama',
      base_url: '',
      model_name: '',
      api_key: '',
      temperature: 0.2,
      max_tokens: '',
      timeout_seconds: 60,
      is_enabled: true,
      is_default: false,
      notes: '',
    })
    setShowModelModal(true)
  }

  const openCreatePresetModel = (preset) => {
    setEditingModel(null)
    setSelectedPresetKey(preset.key)
    setModelForm({
      name: preset.name,
      model_type: preset.model_type,
      provider: preset.provider,
      base_url: preset.base_url,
      model_name: preset.model_name,
      api_key: '',
      temperature: preset.recommended_temperature ?? 0.2,
      max_tokens: '',
      timeout_seconds: preset.recommended_timeout_seconds ?? 60,
      is_enabled: true,
      is_default: aiModels.length === 0,
      notes: preset.notes || '',
    })
    setShowModelModal(true)
  }

  const openEditModel = (model) => {
    setEditingModel(model)
    const matchedPreset = aiModelPresets.find(item => item.provider === model.provider && item.model_name === model.model_name && item.base_url === model.base_url)
    setSelectedPresetKey(matchedPreset?.key || '')
    setModelForm({
      name: model.name || '',
      model_type: model.model_type || 'local',
      provider: model.provider || 'openai_compatible',
      base_url: model.base_url || '',
      model_name: model.model_name || '',
      api_key: '',
      temperature: model.temperature ?? 0.2,
      max_tokens: model.max_tokens ?? '',
      timeout_seconds: model.timeout_seconds ?? 60,
      is_enabled: !!model.is_enabled,
      is_default: !!model.is_default,
      notes: model.notes || '',
    })
    setShowModelModal(true)
  }

  const handleSaveModel = async () => {
    if (!modelForm.name.trim()) { alert('请输入模型名称'); return }
    if (!modelForm.model_name.trim()) { alert('请输入模型标识'); return }
    setSavingModel(true)
    try {
      const payload = {
        ...modelForm,
        max_tokens: modelForm.max_tokens === '' ? null : Number(modelForm.max_tokens),
        temperature: Number(modelForm.temperature),
        timeout_seconds: Number(modelForm.timeout_seconds),
      }
      if (editingModel) {
        await updateAIModelConfig(editingModel.id, payload)
      } else {
        await createAIModelConfig(payload)
      }
      setShowModelModal(false)
      await refreshModels()
    } catch (err) {
      alert('保存模型失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setSavingModel(false)
    }
  }

  const handleDeleteModel = async (model) => {
    if (!confirm(`确定删除模型配置「${model.name}」吗？`)) return
    try {
      await deleteAIModelConfig(model.id)
      await refreshModels()
    } catch (err) {
      alert('删除模型失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleTestModel = async (model) => {
    setTestingModelId(model.id)
    try {
      const res = await testAIModelConfig(model.id, {
        prompt: '请只回复“连接成功”四个字。',
      })
      setModelTestResults(prev => ({ ...prev, [model.id]: { success: true, ...res.data } }))
    } catch (err) {
      const detail = err.response?.data?.detail
      setModelTestResults(prev => ({
        ...prev,
        [model.id]: typeof detail === 'object' && detail
          ? detail
          : { success: false, message: detail || err.message || '测试失败', latency_ms: 0 },
      }))
    } finally {
      setTestingModelId(null)
    }
  }

  const totalCount = summary?.total || 0
  const totalAmount = summary?.total_amount || 0
  const feeAmount = summary?.fee_amount || 0
  const enabledModelCount = aiModels.filter(m => m.is_enabled).length
  const defaultModel = aiModels.find(m => m.is_default) || aiModels[0] || null
  const presetCloudModels = aiModels.filter(model => aiModelPresets.some(preset => preset.provider === model.provider))
  const customLocalModels = aiModels.filter(model => !aiModelPresets.some(preset => preset.provider === model.provider))
  const isPresetMode = !!selectedPresetKey && !editingModel

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold">AI报表</h2>
        <p className="text-sm text-gray-500 mt-1">保留原有固定报表能力，并在这里统一承接 AI 分析、模型选择和全量导出。</p>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('standard')}
              className={`px-4 py-2 rounded text-sm ${activeTab === 'standard' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
            >
              标准报表
            </button>
            <button
              onClick={() => setActiveTab('ai')}
              className={`px-4 py-2 rounded text-sm ${activeTab === 'ai' ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
            >
              AI 分析
            </button>
            {user?.role === 'admin' && (
              <button
                onClick={() => setActiveTab('models')}
                className={`px-4 py-2 rounded text-sm ${activeTab === 'models' ? 'bg-emerald-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
              >
                模型配置
              </button>
            )}
          </div>
          <div className="text-xs text-gray-500">
            已启用模型 {enabledModelCount} 个，默认模型：{defaultModel?.name || '未配置'}
          </div>
        </div>
      </div>

      {activeTab === 'standard' && (
        <>
          <div className="bg-white rounded shadow p-4">
            <div className="grid grid-cols-4 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">关键字</label>
                <input
                  type="text" value={keyword} onChange={e => setKeyword(e.target.value)}
                  placeholder="项目名 / 合作单位 / 编号"
                  className="border rounded px-3 py-1.5 text-sm w-full"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">项目类型</label>
                <select value={projectType} onChange={e => setProjectType(e.target.value)}
                  className="border rounded px-3 py-1.5 text-sm w-full bg-white">
                  <option value="">全部</option>
                  {PROJECT_TYPE_OPTIONS.map(item => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">项目名称</label>
                <input
                  type="text" value={projectName} onChange={e => setProjectName(e.target.value)}
                  placeholder="按项目名称筛选"
                  className="border rounded px-3 py-1.5 text-sm w-full"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">责任销售</label>
                <input
                  type="text" value={responsibleSales} onChange={e => setResponsibleSales(e.target.value)}
                  placeholder="按责任销售筛选"
                  className="border rounded px-3 py-1.5 text-sm w-full"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">中标状态</label>
                <select value={winBidStatusFilter} onChange={e => setWinBidStatusFilter(e.target.value)}
                  className="border rounded px-3 py-1.5 text-sm w-full bg-white">
                  <option value="">全部</option>
                  {WIN_BID_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">金额范围</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number" min="0" value={amountMin} onChange={e => setAmountMin(e.target.value)}
                    placeholder="最小金额"
                    className="border rounded px-3 py-1.5 text-sm w-full"
                  />
                  <span className="text-gray-400 text-sm">-</span>
                  <input
                    type="number" min="0" value={amountMax} onChange={e => setAmountMax(e.target.value)}
                    placeholder="最大金额"
                    className="border rounded px-3 py-1.5 text-sm w-full"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">合作公司名称</label>
                <input
                  type="text" value={partnerCompany} onChange={e => setPartnerCompany(e.target.value)}
                  placeholder="按合作公司筛选"
                  className="border rounded px-3 py-1.5 text-sm w-full"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">投标起始日期</label>
                <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
                  className="border rounded px-3 py-1.5 text-sm w-full" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">投标截止日期</label>
                <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
                  className="border rounded px-3 py-1.5 text-sm w-full" />
              </div>
              <div className="col-span-4 flex flex-wrap items-center gap-2 pt-1">
                <button onClick={fetchAll} disabled={loading}
                  className="px-4 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50">
                  查询
                </button>
                <button onClick={handleReset}
                  className="px-4 py-1.5 border rounded text-sm hover:bg-gray-50">
                  重置
                </button>
                <div className="ml-auto flex items-center gap-2">
                  <button onClick={handleExport} disabled={exporting}
                    className="px-4 py-1.5 bg-green-500 text-white rounded text-sm hover:bg-green-600 disabled:opacity-50">
                    {exporting ? '导出中...' : '导出当前表格'}
                  </button>
                  <button onClick={handleFullExport} disabled={fullExporting}
                    className="px-4 py-1.5 bg-emerald-600 text-white rounded text-sm hover:bg-emerald-700 disabled:opacity-50">
                    {fullExporting ? '导出中...' : '全量导出'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4">
            <KpiCard label="项目总数" value={totalCount} unit="个" color="blue" />
            <KpiCard label="项目总金额" value={(totalAmount / 10000).toLocaleString(undefined, {maximumFractionDigits: 2})} unit="万元" color="green" />
            <KpiCard label="费用总额" value={(feeAmount / 10000).toLocaleString(undefined, {maximumFractionDigits: 2})} unit="万元" color="amber" />
            <KpiCard label="审批状态数" value={(summary?.by_status || []).length} unit="种" color="purple" />
          </div>

          <div className="bg-white rounded shadow p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">按审批状态分布</h3>
            <StatusBar data={summary?.by_status || []} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white rounded shadow p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">月度趋势（投标时间）</h3>
              <BarChart
                data={trend.map(t => ({ label: t.month, value: t.count, sub: t.amount }))}
                color="#3b82f6"
                valueFmt={(v) => `${v} 个`}
                subFmt={(s) => `${(s / 10000).toFixed(2)} 万元`}
              />
            </div>

            <div className="bg-white rounded shadow p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">合作模式分布</h3>
              <PieChart
                data={coop.map(c => ({ label: c.label, value: c.count }))}
                colors={COLORS}
              />
            </div>

            <div className="bg-white rounded shadow p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">中标状态分布</h3>
              <PieChart
                data={winBid.map(w => ({ label: w.label, value: w.count }))}
                colors={COLORS.slice(2)}
              />
            </div>

            <div className="bg-white rounded shadow p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">项目跟单 — 各阶段项目数</h3>
              <BarChart
                data={followupByStage.map(s => ({ label: s.stage, value: s.count }))}
                color="#3b82f6"
              />
              <div className="mt-3 text-xs text-gray-500">
                {followupByStage.map(s => (
                  <span key={s.stage} className="inline-block mr-4">
                    {s.stage}：{s.count} 个 / 预计 {s.expected_amount?.toLocaleString()} 万
                  </span>
                ))}
              </div>
            </div>

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
        </>
      )}

      {activeTab === 'ai' && (
        <div className="bg-white rounded shadow p-4">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h3 className="text-sm font-semibold text-gray-700">AI 分析</h3>
              <p className="text-xs text-gray-500 mt-1">基于当前筛选条件做数据预览分析。现阶段先返回结构化预览，后续可以继续接入真实大模型调用。</p>
            </div>
            <div className="text-xs text-gray-500">
              当前默认模型：{defaultModel?.name || '未配置'}
            </div>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <div className="col-span-1">
              <label className="block text-xs text-gray-500 mb-1">分析模型</label>
              <select value={selectedModelId} onChange={e => setSelectedModelId(e.target.value)}
                className="border rounded px-3 py-2 text-sm w-full bg-white">
                <option value="">自动选择默认模型</option>
                {aiModels.filter(model => model.is_enabled).map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name} · {model.model_type === 'local' ? '本地' : '云端'}
                  </option>
                ))}
              </select>
            </div>
            <div className="col-span-1">
              <label className="block text-xs text-gray-500 mb-1">展示方式</label>
              <select value={aiDisplayType} onChange={e => setAiDisplayType(e.target.value)}
                className="border rounded px-3 py-2 text-sm w-full bg-white">
                <option value="table">表格</option>
                <option value="bar_chart">柱状图</option>
                <option value="line_chart">趋势图</option>
                <option value="summary">摘要</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-1">分析要求</label>
              <textarea value={aiPrompt} onChange={e => setAiPrompt(e.target.value)}
                className="border rounded px-3 py-2 text-sm w-full h-20"
                placeholder="请输入希望 AI 如何分析、展示哪些数据" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-xs text-gray-500 mb-2">本次允许 AI 使用的字段</div>
            <div className="flex flex-wrap gap-2">
              {AI_FIELD_OPTIONS.map(([field, label]) => (
                <label key={field} className="inline-flex items-center gap-2 px-3 py-1.5 rounded border text-xs bg-gray-50">
                  <input type="checkbox" checked={aiFields.includes(field)} onChange={() => toggleAIField(field)} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <button onClick={handleAIAnalyze} disabled={aiLoading}
              className="px-4 py-2 bg-purple-600 text-white rounded text-sm hover:bg-purple-700 disabled:opacity-50">
              {aiLoading ? '分析中...' : '开始 AI 分析'}
            </button>
            <span className="text-xs text-gray-500">分析范围遵循当前登录账号已有的数据权限。</span>
          </div>

          {aiResult && (
            <div className="mt-4 border rounded-lg p-4 bg-gray-50">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-gray-700">AI 分析结果</div>
                  <div className="text-xs text-gray-500 mt-1">{aiResult.message}</div>
                </div>
                <div className="text-xs text-gray-500">
                  模型：{aiResult.model?.name || '未配置默认模型'}
                </div>
              </div>
              <div className="mt-3 text-xs text-gray-600">
                匹配数据量：<span className="font-semibold">{aiResult.total_rows}</span>
              </div>
              {!!aiResult.summary_text && (
                <div className="mt-3 rounded border border-purple-100 bg-purple-50 px-3 py-3 text-sm text-gray-700">
                  <div className="font-medium text-purple-700 mb-1">小销摘要</div>
                  <div>{aiResult.summary_text}</div>
                </div>
              )}
              <div className="mt-3 overflow-auto">
                <table className="w-full text-xs bg-white rounded overflow-hidden">
                  <thead className="bg-gray-100 text-gray-600">
                    <tr>
                      {aiResult.fields.map(field => (
                        <th key={field} className="px-3 py-2 text-left whitespace-nowrap">
                          {aiResult.field_labels?.[field] || AI_FIELD_LABELS[field] || field}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(aiResult.preview_rows || []).map((row, idx) => (
                      <tr key={idx} className="border-t">
                        {aiResult.fields.map(field => (
                          <td key={field} className="px-3 py-2 whitespace-nowrap">{formatAiCell(field, row[field])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!!aiResult.suggestions?.length && (
                <div className="mt-3 text-xs text-gray-600 space-y-1">
                  {aiResult.suggestions.map((item, idx) => (
                    <div key={idx}>- {item}</div>
                  ))}
                </div>
              )}

              <div className="mt-4 rounded-lg border bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-gray-700">小销智能助理</div>
                    <div className="text-xs text-gray-500 mt-1">可以继续问数据问题、让它帮你总结，或者让它换个角度解释当前结果。</div>
                  </div>
                  <div className="text-xs text-gray-500">
                    助理：小销
                  </div>
                </div>
                <div className="mt-3 space-y-3 max-h-72 overflow-auto rounded border bg-gray-50 p-3">
                  {assistantMessages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                        msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-white border text-gray-700'
                      }`}>
                        {msg.content}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <input
                    type="text"
                    value={assistantQuestion}
                    onChange={e => setAssistantQuestion(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        handleAskAssistant()
                      }
                    }}
                    placeholder="继续问小销，比如：中标情况怎么样？哪类项目最多？"
                    className="border rounded px-3 py-2 text-sm w-full"
                  />
                  <button
                    onClick={handleAskAssistant}
                    disabled={assistantLoading}
                    className="px-4 py-2 bg-purple-600 text-white rounded text-sm hover:bg-purple-700 disabled:opacity-50"
                  >
                    {assistantLoading ? '思考中...' : '发送'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'models' && (
        <div className="bg-white rounded shadow p-4">
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-semibold text-gray-700">预置国内云端模型</h3>
              <p className="text-xs text-gray-500 mt-1">系统已预先定义 Kimi、MiniMax、DeepSeek 的默认接入参数。点击后只需要填写 API Key，就可以直接运行和测速。</p>
              <div className="grid grid-cols-3 gap-4 mt-4">
                {aiModelPresets.map(preset => (
                  <div key={preset.key} className="border rounded-lg p-4 bg-gray-50">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-gray-800">{preset.name}</div>
                      <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700">预置</span>
                    </div>
                    <div className="text-xs text-gray-500 mt-2 space-y-1">
                      <div>默认模型：{preset.model_name}</div>
                      <div className="truncate" title={preset.base_url}>地址：{preset.base_url}</div>
                    </div>
                    <div className="text-xs text-gray-400 mt-3">{preset.description}</div>
                    <button onClick={() => openCreatePresetModel(preset)}
                      className="mt-4 w-full px-3 py-2 bg-emerald-600 text-white rounded text-sm hover:bg-emerald-700">
                      填写 Key 创建
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-gray-700">自定义本地模型</h3>
                  <p className="text-xs text-gray-500 mt-1">用于接入本地化模型服务，例如 Ollama 或内部 OpenAI 兼容接口。</p>
                </div>
                <button onClick={openCreateModel}
                  className="px-3 py-1.5 border rounded text-sm hover:bg-gray-50">
                  新建本地模型
                </button>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700">已配置模型</h3>
              <p className="text-xs text-gray-500 mt-1">每个模型都支持“测试连接”，会显示接口响应耗时，便于比较反应速度。</p>
              {aiModels.length === 0 ? (
                <div className="text-sm text-gray-400 mt-4">暂无模型配置，可先从上方预置模型开始，也可以新建本地模型。</div>
              ) : (
                <div className="space-y-5 mt-4">
                  <div>
                    <div className="text-xs font-medium text-gray-500 mb-2">云端预置模型</div>
                    {presetCloudModels.length === 0 ? (
                      <div className="text-sm text-gray-400">还没有配置预置云端模型。</div>
                    ) : (
                      <div className="space-y-2">
                        {presetCloudModels.map(model => (
                          <ModelConfigCard
                            key={model.id}
                            model={model}
                            testing={testingModelId === model.id}
                            testResult={modelTestResults[model.id]}
                            onEdit={() => openEditModel(model)}
                            onDelete={() => handleDeleteModel(model)}
                            onTest={() => handleTestModel(model)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                  <div>
                    <div className="text-xs font-medium text-gray-500 mb-2">本地自定义模型</div>
                    {customLocalModels.length === 0 ? (
                      <div className="text-sm text-gray-400">还没有配置本地模型。</div>
                    ) : (
                      <div className="space-y-2">
                        {customLocalModels.map(model => (
                          <ModelConfigCard
                            key={model.id}
                            model={model}
                            testing={testingModelId === model.id}
                            testResult={modelTestResults[model.id]}
                            onEdit={() => openEditModel(model)}
                            onDelete={() => handleDeleteModel(model)}
                            onTest={() => handleTestModel(model)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {showModelModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-gray-800">{editingModel ? '编辑模型配置' : '新建模型配置'}</h3>
                {isPresetMode && <div className="text-xs text-emerald-600 mt-1">已加载预置配置，只需要填写 API Key 就能使用。</div>}
              </div>
              <button onClick={() => setShowModelModal(false)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <input value={modelForm.name} onChange={e => setModelForm(f => ({ ...f, name: e.target.value }))}
                placeholder="模型名称" className="border rounded px-3 py-2 text-sm" />
              <input value={modelForm.model_name} onChange={e => setModelForm(f => ({ ...f, model_name: e.target.value }))}
                placeholder="模型标识，如 qwen2.5:7b" readOnly={isPresetMode}
                className={`border rounded px-3 py-2 text-sm ${isPresetMode ? 'bg-gray-50 text-gray-500' : ''}`} />
              <select value={modelForm.model_type} onChange={e => setModelForm(f => ({ ...f, model_type: e.target.value }))}
                disabled={isPresetMode}
                className={`border rounded px-3 py-2 text-sm bg-white ${isPresetMode ? 'bg-gray-50 text-gray-500' : ''}`}>
                <option value="local">本地模型</option>
                <option value="cloud">云端模型</option>
              </select>
              <input value={modelForm.provider} onChange={e => setModelForm(f => ({ ...f, provider: e.target.value }))}
                placeholder="提供商，如 ollama / openai_compatible" readOnly={isPresetMode}
                className={`border rounded px-3 py-2 text-sm ${isPresetMode ? 'bg-gray-50 text-gray-500' : ''}`} />
              <input value={modelForm.base_url} onChange={e => setModelForm(f => ({ ...f, base_url: e.target.value }))}
                placeholder="接入地址" readOnly={isPresetMode}
                className={`border rounded px-3 py-2 text-sm col-span-2 ${isPresetMode ? 'bg-gray-50 text-gray-500' : ''}`} />
              <input value={modelForm.api_key} onChange={e => setModelForm(f => ({ ...f, api_key: e.target.value }))}
                placeholder={editingModel ? '如需更新 API Key 请重新填写，留空则保持原值' : 'API Key（本地模型可留空）'}
                className="border rounded px-3 py-2 text-sm col-span-2" />
              <input type="number" step="0.1" min="0" max="2" value={modelForm.temperature}
                onChange={e => setModelForm(f => ({ ...f, temperature: e.target.value }))}
                placeholder="temperature" className="border rounded px-3 py-2 text-sm" />
              <input type="number" min="1" value={modelForm.max_tokens}
                onChange={e => setModelForm(f => ({ ...f, max_tokens: e.target.value }))}
                placeholder="max_tokens（选填）" className="border rounded px-3 py-2 text-sm" />
              <input type="number" min="5" max="600" value={modelForm.timeout_seconds}
                onChange={e => setModelForm(f => ({ ...f, timeout_seconds: e.target.value }))}
                placeholder="超时秒数" className="border rounded px-3 py-2 text-sm" />
              <input value={modelForm.notes} onChange={e => setModelForm(f => ({ ...f, notes: e.target.value }))}
                placeholder="备注（选填）" className="border rounded px-3 py-2 text-sm" />
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={modelForm.is_enabled}
                  onChange={e => setModelForm(f => ({ ...f, is_enabled: e.target.checked }))} />
                启用
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={modelForm.is_default}
                  onChange={e => setModelForm(f => ({ ...f, is_default: e.target.checked }))} />
                设为默认模型
              </label>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setShowModelModal(false)}
                className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50">
                取消
              </button>
              <button onClick={handleSaveModel} disabled={savingModel}
                className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50">
                {savingModel ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
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

function ModelConfigCard({ model, testing, testResult, onEdit, onDelete, onTest }) {
  return (
    <div className="bg-gray-50 border rounded px-3 py-3 text-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="font-medium text-gray-800">
            {model.name}
            {model.is_default && <span className="ml-2 text-xs text-purple-600">默认</span>}
            {!model.is_enabled && <span className="ml-2 text-xs text-gray-400">停用</span>}
          </div>
          <div className="text-xs text-gray-500 truncate mt-1">
            {model.model_type === 'local' ? '本地模型' : '云端模型'} · {model.provider} · {model.model_name}
            {model.base_url ? ` · ${model.base_url}` : ''}
          </div>
          {model.notes && (
            <div className="text-xs text-gray-400 mt-1">{model.notes}</div>
          )}
          {testResult && (
            <div className={`mt-2 text-xs ${testResult.success ? 'text-emerald-600' : 'text-red-500'}`}>
              {testResult.success ? '测试成功' : '测试失败'} · {testResult.latency_ms ?? 0} ms
              {testResult.message ? ` · ${testResult.message}` : ''}
              {testResult.response_preview ? ` · 返回：${testResult.response_preview}` : ''}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={onTest} className="text-emerald-600 hover:text-emerald-800 text-xs">
            {testing ? '测试中...' : '测试连接'}
          </button>
          <button onClick={onEdit} className="text-blue-600 hover:text-blue-800 text-xs">编辑</button>
          <button onClick={onDelete} className="text-red-500 hover:text-red-700 text-xs">删除</button>
        </div>
      </div>
    </div>
  )
}

function formatAiCell(field, value) {
  if (value === null || value === undefined || value === '') return '-'
  if (['project_amount', 'expected_amount', 'fee_amount', 'latest_followup_expected_amount'].includes(field)) {
    return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
  return String(value)
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
