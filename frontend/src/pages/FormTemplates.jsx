import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getFormTemplates, deleteFormTemplate, updateFormTemplate, getFormInstances, deleteFormInstance } from '../api'
import DynamicForm from '../components/DynamicForm'
import { BUILTIN_TEMPLATE_NAMES } from '../data/projectFormTemplate'

export default function FormTemplates() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('templates')
  const [templates, setTemplates] = useState([])
  const [instances, setInstances] = useState([])
  const [loading, setLoading] = useState(false)
  const [previewTemplate, setPreviewTemplate] = useState(null)  // 预览/填写模式
  const [templateToDelete, setTemplateToDelete] = useState(null)  // 删除确认

  const load = async () => {
    setLoading(true)
    try {
      const [tplRes, instRes] = await Promise.all([
        getFormTemplates(),
        getFormInstances({ page: 1, page_size: 50 }),
      ])
      // 内置模板优先排在前面
      const sorted = (tplRes.data || []).slice().sort((a, b) => {
        const aBuiltin = BUILTIN_TEMPLATE_NAMES.includes(a.name)
        const bBuiltin = BUILTIN_TEMPLATE_NAMES.includes(b.name)
        if (aBuiltin && !bBuiltin) return -1
        if (!aBuiltin && bBuiltin) return 1
        return a.id - b.id
      })
      setTemplates(sorted)
      setInstances(instRes.data.items)
    } catch (e) {
      alert('加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (tpl) => {
    // 内置模板禁止删除
    if (BUILTIN_TEMPLATE_NAMES.includes(tpl.name)) {
      alert(`「${tpl.name}」是系统内置表单模板，不能删除`)
      return
    }
    setTemplateToDelete(tpl)
  }

  const confirmDelete = async () => {
    if (!templateToDelete) return
    try {
      await deleteFormTemplate(templateToDelete.id)
      setTemplateToDelete(null)
      load()
    } catch (e) {
      alert('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleDeleteInstance = async (id) => {
    if (!confirm('确定删除该表单记录？')) return
    try {
      await deleteFormInstance(id)
      load()
    } catch (e) {
      alert('删除失败')
    }
  }

  const handleToggleActive = async (tpl) => {
    if (BUILTIN_TEMPLATE_NAMES.includes(tpl.name)) {
      alert(`「${tpl.name}」是系统内置表单模板，不能停用`)
      return
    }
    try {
      await updateFormTemplate(tpl.id, { is_active: !tpl.is_active })
      load()
    } catch (e) {
      alert('操作失败')
    }
  }

  // 预览/填写模式
  if (previewTemplate) {
    return (
      <DynamicForm
        template={previewTemplate}
        onClose={() => setPreviewTemplate(null)}
        onSubmitted={() => { setPreviewTemplate(null); load() }}
      />
    )
  }

  return (
    <div>
      {/* 顶部 */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold">表单管理</h2>
        {tab === 'templates' && (
          <button onClick={() => navigate('/admin/forms/builder')}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm">
            + 新建表单
          </button>
        )}
      </div>

      {/* Tab 切换 */}
      <div className="flex gap-2 mb-4 border-b">
        <button
          onClick={() => setTab('templates')}
          className={`px-4 py-2 text-sm font-medium border-b-2 ${
            tab === 'templates' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'
          }`}
        >
          表单模板 ({templates.length})
        </button>
        <button
          onClick={() => setTab('instances')}
          className={`px-4 py-2 text-sm font-medium border-b-2 ${
            tab === 'instances' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'
          }`}
        >
          表单记录 ({instances.length})
        </button>
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-8">加载中...</div>
      ) : tab === 'templates' ? (
        /* 表单模板列表 */
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-gray-600 font-medium whitespace-nowrap min-w-[10rem]">表单名称</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">描述</th>
                <th className="px-4 py-3 text-center text-gray-600 font-medium">字段数</th>
                <th className="px-4 py-3 text-center text-gray-600 font-medium">状态</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">创建人</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">创建时间</th>
                <th className="px-4 py-3 text-center text-gray-600 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {templates.length === 0 ? (
                <tr><td colSpan={7} className="text-center text-gray-400 py-8">
                  暂无表单模板，点击右上角"新建表单"创建
                </td></tr>
              ) : templates.map(t => {
                const isBuiltin = BUILTIN_TEMPLATE_NAMES.includes(t.name)
                return (
                  <tr key={t.id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium whitespace-nowrap min-w-[10rem]">
                      <span>{t.name}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{t.description || '-'}</td>
                    <td className="px-4 py-3 text-center">{t.fields?.length || 0}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        t.is_active
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-500'
                      }`}>
                        {t.is_active ? '启用' : '停用'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{t.creator?.real_name || '-'}</td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(t.created_at + 'Z').toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <button onClick={() => setPreviewTemplate(t)}
                          className="text-green-600 hover:text-green-800 text-xs">填写</button>
                        <button onClick={() => navigate(`/admin/forms/builder/${t.id}`)}
                          className="text-blue-600 hover:text-blue-800 text-xs">编辑</button>
                        {!isBuiltin && (
                          <>
                            <button onClick={() => handleToggleActive(t)}
                              className="text-amber-600 hover:text-amber-800 text-xs">
                              {t.is_active ? '停用' : '启用'}
                            </button>
                            <button onClick={() => handleDelete(t)}
                              className="text-red-500 hover:text-red-700 text-xs">删除</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        /* 表单记录列表 */
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">ID</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">表单名称</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">数据摘要</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">提交人</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">提交时间</th>
                <th className="px-4 py-3 text-center text-gray-600 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {instances.length === 0 ? (
                <tr><td colSpan={6} className="text-center text-gray-400 py-8">
                  暂无表单记录
                </td></tr>
              ) : instances.map(inst => (
                <tr key={inst.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-400">#{inst.id}</td>
                  <td className="px-4 py-3 font-medium">{inst.template?.name || '-'}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs max-w-md truncate">
                    {Object.entries(inst.data || {}).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join(', ')}
                    {Object.keys(inst.data || {}).length > 3 ? ' ...' : ''}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{inst.creator?.real_name || '-'}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(inst.created_at + 'Z').toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => handleDeleteInstance(inst.id)}
                      className="text-red-500 hover:text-red-700 text-xs">删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 删除确认弹窗 */}
      {templateToDelete && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-5">
            <h3 className="text-base font-bold text-gray-800 mb-3">⚠️ 确认删除表单模板</h3>
            <p className="text-sm text-gray-600 mb-3">
              确定要删除「<span className="font-bold text-gray-800">{templateToDelete.name}</span>」吗？
            </p>
            <p className="text-xs text-red-600 mb-4">
              此操作不可删除！所有使用此模板创建的表单记录也会被删除。
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setTemplateToDelete(null)}
                className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50">
                取消
              </button>
              <button onClick={confirmDelete}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
