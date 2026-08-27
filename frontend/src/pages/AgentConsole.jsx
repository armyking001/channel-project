import { useEffect, useMemo, useState } from 'react'
import { getProjects } from '../api'
import { analyzeProject, queryAgent } from '../api/agents'

const ANALYZE_OPTIONS = [
  { key: 'reliability', label: '项目可靠性' },
  { key: 'sales_activity', label: '销售积极性' },
]

export default function AgentConsole() {
  const [projects, setProjects] = useState([])
  const [loadingProjects, setLoadingProjects] = useState(false)
  const [projectId, setProjectId] = useState('')
  const [topK, setTopK] = useState(5)
  const [analyzeTypes, setAnalyzeTypes] = useState(['reliability', 'sales_activity'])
  const [question, setQuestion] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [querying, setQuerying] = useState(false)
  const [analyzeResult, setAnalyzeResult] = useState(null)
  const [queryResult, setQueryResult] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function loadProjects() {
      setLoadingProjects(true)
      try {
        const res = await getProjects({ page: 1, page_size: 100 })
        if (!cancelled) {
          const items = res.data?.items || []
          setProjects(items)
          if (items.length && !projectId) {
            setProjectId(String(items[0].id))
          }
        }
      } catch (err) {
        if (!cancelled) {
          alert('加载项目列表失败：' + (err.response?.data?.detail || err.message))
        }
      } finally {
        if (!cancelled) {
          setLoadingProjects(false)
        }
      }
    }
    loadProjects()
    return () => { cancelled = true }
  }, [])

  const selectedProject = useMemo(
    () => projects.find(item => String(item.id) === String(projectId)),
    [projects, projectId]
  )

  const toggleAnalyzeType = (key) => {
    setAnalyzeTypes(prev => {
      if (prev.includes(key)) {
        const next = prev.filter(item => item !== key)
        return next.length ? next : prev
      }
      return [...prev, key]
    })
  }

  const handleAnalyze = async () => {
    if (!projectId) return
    setAnalyzing(true)
    try {
      const res = await analyzeProject(Number(projectId), analyzeTypes, Number(topK))
      setAnalyzeResult(res.data)
    } catch (err) {
      alert('AI 分析失败：' + (err.response?.data?.detail || err.message))
    } finally {
      setAnalyzing(false)
    }
  }

  const handleQuery = async () => {
    if (!projectId || !question.trim()) return
    setQuerying(true)
    try {
      const res = await queryAgent(Number(projectId), question.trim(), Number(topK))
      setQueryResult(res.data)
    } catch (err) {
      alert('Agent 问答失败：' + (err.response?.data?.detail || err.message))
    } finally {
      setQuerying(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold">AI Agent 控制台</h2>
        <p className="text-sm text-gray-500 mt-1">选择一个项目后，可以直接做项目可靠性分析，或围绕项目资料继续提问。</p>
      </div>

      <div className="bg-white rounded shadow p-4 space-y-4">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">项目</label>
            <select
              value={projectId}
              onChange={e => setProjectId(e.target.value)}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
              disabled={loadingProjects}
            >
              {!projects.length && <option value="">暂无项目</option>}
              {projects.map(item => (
                <option key={item.id} value={item.id}>
                  {item.project_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">检索条数</label>
            <input
              type="number"
              min="1"
              max="20"
              value={topK}
              onChange={e => setTopK(e.target.value)}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">当前项目</label>
            <div className="border rounded px-3 py-2 text-sm bg-gray-50 min-h-[42px] flex items-center">
              {selectedProject ? `${selectedProject.project_name} / ${selectedProject.project_code || '未编号'}` : '未选择'}
            </div>
          </div>
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-2">分析维度</label>
          <div className="flex flex-wrap gap-3">
            {ANALYZE_OPTIONS.map(item => (
              <label key={item.key} className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={analyzeTypes.includes(item.key)}
                  onChange={() => toggleAnalyzeType(item.key)}
                />
                <span>{item.label}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleAnalyze}
            disabled={analyzing || !projectId}
            className="px-4 py-2 rounded bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {analyzing ? '分析中...' : '开始分析'}
          </button>
        </div>
      </div>

      <div className="bg-white rounded shadow p-4 space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">项目问答</h3>
          <p className="text-xs text-gray-500 mt-1">让 Agent 结合当前项目资料、跟单记录和表单信息回答你的问题。</p>
        </div>
        <div className="flex gap-3">
          <input
            type="text"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleQuery()
              }
            }}
            placeholder="例如：当前项目推进最大的风险是什么？"
            className="border rounded px-3 py-2 text-sm flex-1"
          />
          <button
            onClick={handleQuery}
            disabled={querying || !projectId || !question.trim()}
            className="px-4 py-2 rounded bg-purple-600 text-white text-sm hover:bg-purple-700 disabled:opacity-50"
          >
            {querying ? '提问中...' : '提问'}
          </button>
        </div>
      </div>

      {analyzeResult && (
        <div className="bg-white rounded shadow p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded border border-blue-100 bg-blue-50 p-4">
              <div className="text-xs text-blue-700">项目可靠性评分</div>
              <div className="text-3xl font-bold text-blue-700 mt-2">{analyzeResult.reliability_score}</div>
            </div>
            <div className="rounded border border-green-100 bg-green-50 p-4">
              <div className="text-xs text-green-700">销售积极性评分</div>
              <div className="text-3xl font-bold text-green-700 mt-2">{analyzeResult.sales_activity_score}</div>
            </div>
          </div>

          <div>
            <div className="text-sm font-semibold text-gray-700 mb-2">关键发现</div>
            <div className="space-y-3">
              {(analyzeResult.findings || []).map((item, index) => (
                <div key={index} className="rounded border p-3">
                  <div className="font-medium text-sm text-gray-800">{item.title}</div>
                  <div className="text-sm text-gray-600 mt-1">{item.detail}</div>
                  <div className="text-xs text-gray-500 mt-2">评分：{item.score ?? '-'}</div>
                  <ul className="mt-2 space-y-1 text-xs text-gray-500">
                    {(item.evidences || []).map((evidence, idx) => (
                      <li key={idx}>[{evidence.source_type}] {evidence.snippet}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="text-sm font-semibold text-gray-700 mb-2">建议</div>
            <ul className="list-disc pl-5 space-y-1 text-sm text-gray-600">
              {(analyzeResult.recommendations || []).map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>

          <div>
            <div className="text-sm font-semibold text-gray-700 mb-2">证据片段</div>
            <div className="space-y-2">
              {(analyzeResult.evidences || []).map((item, index) => (
                <div key={index} className="rounded border bg-gray-50 p-3 text-sm text-gray-600">
                  <div className="text-xs text-gray-500 mb-1">{item.source_type} / {item.source_id || '-'}</div>
                  <div>{item.snippet}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {queryResult && (
        <div className="bg-white rounded shadow p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-gray-700">Agent 回答</div>
            <div className="text-xs text-gray-500">可信度：{queryResult.score}</div>
          </div>
          <div className="rounded border bg-gray-50 p-3 text-sm text-gray-700">{queryResult.answer}</div>
          <div>
            <div className="text-xs font-medium text-gray-500 mb-2">引用来源</div>
            <div className="space-y-2">
              {(queryResult.sources || []).map((item, index) => (
                <div key={index} className="rounded border p-3 text-sm text-gray-600">
                  <div className="text-xs text-gray-500 mb-1">{item.source_type} / {item.source_id || '-'}</div>
                  <div>{item.snippet}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
