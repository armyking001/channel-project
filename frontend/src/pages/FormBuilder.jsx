import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  getFormTemplate, createFormTemplate, updateFormTemplate,
  listStorageZones,
} from '../api'
import { channelProjectTemplate, selfProjectTemplate } from '../data/projectFormTemplate'
import { BUILTIN_TEMPLATE_NAMES } from '../data/projectFormTemplate'

// ============ 字段类型定义 ============
const FIELD_TYPES = [
  { type: 'text',     icon: '📝', label: '单行文本' },
  { type: 'textarea', icon: '📄', label: '多行文本' },
  { type: 'number',   icon: '🔢', label: '数字' },
  { type: 'date',     icon: '📅', label: '日期' },
  { type: 'select',   icon: '📋', label: '下拉选择' },
  { type: 'radio',    icon: '⚪', label: '单选' },
  { type: 'checkbox', icon: '☑️', label: '多选' },
  { type: 'file',     icon: '📎', label: '文件上传' },
]

const DEFAULT_FIELD_PROPS = {
  text:     { placeholder: '请输入' },
  textarea: { placeholder: '请输入' },
  number:   { placeholder: '请输入数字', min: null, max: null, unit: '' },
  date:     {},
  select:   { options: ['选项1', '选项2'] },
  radio:    { options: ['选项1', '选项2'] },
  checkbox: { options: ['选项1', '选项2'] },
  file:     { accept: '*', multiple: false },
}

let _fieldIdCounter = 1
function genFieldKey(label) {
  return `field_${Date.now()}_${_fieldIdCounter++}`
}

function createField(type) {
  const def = FIELD_TYPES.find(f => f.type === type)
  const label = def ? def.label : '字段'
  return {
    id: genFieldKey(),
    type,
    label: `${label}_${_fieldIdCounter}`,
    key: genFieldKey(label),
    required: false,
    ...JSON.parse(JSON.stringify(DEFAULT_FIELD_PROPS[type] || {})),
  }
}

const inputCls = "w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-blue-200 focus:border-blue-500 text-sm"

// ============ 主组件 ============
export default function FormBuilder() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isEdit = !!id

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [fields, setFields] = useState([])
  const [storageZoneId, setStorageZoneId] = useState(null)  // 选中的存储区域
  const [storageZones, setStorageZones] = useState([])
  const [selectedKey, setSelectedKey] = useState(null)
  const [saving, setSaving] = useState(false)
  const [dragIdx, setDragIdx] = useState(null)

  // 加载存储区域列表
  useEffect(() => {
    listStorageZones().then(r => {
      const zones = r.data.items || []
      setStorageZones(zones)
    }).catch(() => {})
  }, [])

  // 加载已有模板
  useEffect(() => {
    if (!isEdit) return
    getFormTemplate(id).then(r => {
      const t = r.data
      setName(t.name)
      setDescription(t.description || '')
      setFields(t.fields || [])
      setStorageZoneId(t.storage_zone_id || null)
    }).catch(() => alert('加载模板失败'))
  }, [id])

  // ===== 分区管理 =====
  const sections = useMemo(() => {
    const map = new Map()
    const order = []
    fields.forEach(f => {
      const sec = f.section || '其他'
      if (!map.has(sec)) { map.set(sec, []); order.push(sec) }
      map.get(sec).push(f)
    })
    return order.map(name => [name, map.get(name)])
  }, [fields])

  const addSection = () => {
    const newName = prompt('请输入新分区名称：', '新分区')
    if (!newName || !newName.trim()) return
    // 添加一个空字段占位（至少保证分区显示）
    const f = createField('text')
    f.section = newName.trim()
    f.label = '示例字段'
    setFields(prev => [...prev, f])
  }

  const renameSection = (oldName) => {
    const newName = prompt(`将分区「${oldName}」重命名为：`, oldName)
    if (!newName || !newName.trim() || newName.trim() === oldName) return
    setFields(prev => prev.map(f => f.section === oldName ? { ...f, section: newName.trim() } : f))
  }

  const removeSection = (secName) => {
    if (!confirm(`确定删除整个分区「${secName}」吗？\n该分区下的所有字段会被移除。`)) return
    setFields(prev => prev.filter(f => f.section !== secName))
  }

  // 添加字段（添加到指定分区）
  const addFieldToSection = (secName, type) => {
    const f = createField(type)
    if (secName) f.section = secName
    setFields(prev => [...prev, f])
    setSelectedKey(f.key)
  }

  // 删除字段
  const removeField = (key) => {
    setFields(prev => prev.filter(f => f.key !== key))
    if (selectedKey === key) setSelectedKey(null)
  }

  // 移动字段（在分区之间或分区内的位置）
  const moveField = (from, to) => {
    if (from === to || from < 0 || to < 0 || from >= fields.length || to >= fields.length) return
    setFields(prev => {
      const arr = [...prev]
      ;[arr[from], arr[to]] = [arr[to], arr[from]]
      return arr
    })
  }

  // 更新字段属性
  const updateField = (key, updates) => {
    setFields(prev => prev.map(f => f.key === key ? { ...f, ...updates } : f))
  }

  // 拖拽排序
  const onDragStart = (idx) => setDragIdx(idx)
  const onDragOver = (e) => e.preventDefault()
  const onDrop = (idx) => {
    if (dragIdx !== null && dragIdx !== idx) {
      moveField(dragIdx, idx)
    }
    setDragIdx(null)
  }

  // 保存
  const handleSave = async () => {
    if (!name.trim()) { alert('请输入表单名称'); return }
    if (fields.length === 0) { alert('请至少添加一个字段'); return }
    const keys = fields.map(f => f.key)
    const dupKeys = keys.filter((k, i) => keys.indexOf(k) !== i)
    if (dupKeys.length > 0) { alert(`字段标识重复: ${dupKeys.join(', ')}`); return }

    setSaving(true)
    try {
      const payload = {
        name, description, fields,
        storage_zone_id: storageZoneId || null,
      }
      if (isEdit) {
        await updateFormTemplate(id, payload)
      } else {
        await createFormTemplate(payload)
      }
      alert('保存成功')
      navigate('/admin/forms')
    } catch (e) {
      alert('保存失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSaving(false)
    }
  }

  const selectedField = selectedKey ? fields.find(f => f.key === selectedKey) : null
  const isBuiltin = BUILTIN_TEMPLATE_NAMES.includes(name)

  return (
    <div className="flex flex-col h-full">
      {/* 顶部工具栏 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/admin/forms')}
            className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded">
            ← 返回
          </button>
          <h2 className="text-lg font-bold">{isEdit ? '编辑表单' : '新建表单'}</h2>
          {isBuiltin && (
            <span className="px-2 py-0.5 rounded text-xs font-bold bg-blue-100 text-blue-700">
              系统内置
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!isEdit && (
            <>
              <button onClick={() => {
                if (fields.length > 0 && !confirm('将覆盖当前已添加的字段，确定从【渠道项目模板】加载？')) return
                setName(channelProjectTemplate.name)
                setDescription(channelProjectTemplate.description)
                setFields(channelProjectTemplate.fields.map(f => ({ ...f })))
                setSelectedKey(null)
              }}
                className="px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">
                📋 从渠道项目模板加载
              </button>
              <button onClick={() => {
                if (fields.length > 0 && !confirm('将覆盖当前已添加的字段，确定从【自建项目模板】加载？')) return
                setName(selfProjectTemplate.name)
                setDescription(selfProjectTemplate.description)
                setFields(selfProjectTemplate.fields.map(f => ({ ...f })))
                setSelectedKey(null)
              }}
                className="px-3 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700">
                📋 从自建项目模板加载
              </button>
            </>
          )}
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 text-sm">
            {saving ? '保存中...' : '保存模板'}
          </button>
        </div>
      </div>

      {/* 表单名称 + 存储区域 */}
      <div className="mb-4 flex gap-3">
        <input
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="表单名称（如：合同登记表）"
          className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm"
        />
        <input
          type="text"
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="表单描述（选填）"
          className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm"
        />
        <select
          value={storageZoneId || ''}
          onChange={e => setStorageZoneId(e.target.value ? parseInt(e.target.value) : null)}
          className="w-56 border border-gray-300 rounded-md px-3 py-2 text-sm bg-white"
        >
          <option value="">📁 默认存储区域</option>
          {storageZones.map(z => (
            <option key={z.id} value={z.id}>
              {z.mode === 'webdav' ? '🌐' : '📁'} {z.name} {z.mode === 'webdav' && z.webdav_url ? `(${z.webdav_url})` : ''}
            </option>
          ))}
        </select>
      </div>
      {storageZoneId && (
        <div className="mb-3 -mt-2 text-xs text-cyan-700">
          💡 该表单将保存到所选存储区域，文件名规则: <span className="font-mono">{'{responsible_sales}+{project_name}+{date}'}</span>
          {(() => {
            const z = storageZones.find(x => x.id === storageZoneId)
            if (!z) return null
            return (
              <span className="ml-2 text-gray-500">
                · {z.mode === 'webdav' ? `${z.webdav_use_ssl ? 'https' : 'http'}://${z.webdav_url}${z.webdav_port ? ':' + z.webdav_port : ''}${z.webdav_base_path || ''}` : z.local_path}
                {z.sub_path && ` / ${z.sub_path}`}
              </span>
            )
          })()}
        </div>
      )}

      {/* 三栏布局：字段类型 | 表单预览（分区两列） | 属性编辑 */}
      <div className="flex gap-4 flex-1 overflow-hidden">

        {/* 左栏：字段类型 */}
        <div className="w-48 bg-white rounded-lg border border-gray-200 p-3 overflow-auto">
          <h3 className="text-xs font-bold text-gray-500 uppercase mb-3">字段类型</h3>
          <div className="space-y-2">
            {FIELD_TYPES.map(ft => (
              <button
                key={ft.type}
                onClick={() => {
                  // 添加到当前选中字段所在的分区；否则加到最后一个分区
                  let targetSec = '其他'
                  if (selectedField?.section) targetSec = selectedField.section
                  else if (sections.length > 0) targetSec = sections[sections.length - 1][0]
                  addFieldToSection(targetSec, ft.type)
                }}
                className="w-full flex items-center gap-2 px-3 py-2 border border-gray-200 rounded hover:bg-blue-50 hover:border-blue-300 transition text-sm text-left"
              >
                <span className="text-lg">{ft.icon}</span>
                <span>{ft.label}</span>
              </button>
            ))}
          </div>
          <div className="mt-4 pt-3 border-t">
            <button onClick={addSection}
              className="w-full px-3 py-2 border-2 border-dashed border-gray-300 rounded text-sm text-gray-600 hover:border-blue-500 hover:text-blue-600 hover:bg-blue-50 transition">
              + 添加分区
            </button>
          </div>
        </div>

        {/* 中栏：表单预览（分区+两列网格，所见即所得） */}
        <div className="flex-1 bg-white rounded-lg border border-gray-200 p-4 overflow-auto">
          <h3 className="text-xs font-bold text-gray-500 uppercase mb-3">
            表单预览 <span className="text-gray-400 normal-case">（点击字段选中编辑属性）</span>
          </h3>
          {fields.length === 0 ? (
            <div className="flex items-center justify-center h-64 text-gray-400 text-sm border-2 border-dashed border-gray-200 rounded-lg">
              ← 从左侧选择字段类型添加到表单
            </div>
          ) : (
            <div className="space-y-4">
              {sections.map(([secName, secFields], secIdx) => {
                const globalStartIdx = fields.findIndex(f => f.key === secFields[0].key)
                return (
                  <div key={secName} className="border border-gray-200 rounded-lg p-3 bg-white">
                    {/* 分区标题栏（红框位置，可编辑） */}
                    <div className="flex items-center justify-between mb-3 bg-green-50 border-l-4 border-green-500 px-3 py-1.5 rounded-r">
                      <div
                        onClick={() => renameSection(secName)}
                        className="text-sm font-bold text-green-700 cursor-pointer hover:bg-green-100 px-2 py-0.5 rounded flex items-center gap-2"
                        title="点击重命名分区"
                      >
                        {secName}
                        <span className="text-xs text-gray-500 font-400">（{secFields.length} 个字段）</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button onClick={() => renameSection(secName)}
                          className="text-xs text-blue-600 hover:text-blue-800 px-2">重命名</button>
                        <button onClick={() => removeSection(secName)}
                          className="text-xs text-red-500 hover:text-red-700 px-2">删除分区</button>
                      </div>
                    </div>

                    {/* 两列网格 */}
                    <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                      {secFields.map(f => {
                        const globalIdx = fields.findIndex(x => x.key === f.key)
                        const isFileSection = secName === '文件管理'
                        // 文件管理特殊处理：保持两列但每列只放一个文件字段
                        if (isFileSection && f.type === 'file') {
                          return (
                            <div key={f.key} className="col-span-1">
                              <FieldEditorCard
                                field={f}
                                index={globalIdx}
                                total={fields.length}
                                selected={selectedKey === f.key}
                                dragIdx={dragIdx}
                                onClick={() => setSelectedKey(f.key)}
                                onDragStart={() => onDragStart(globalIdx)}
                                onDragOver={onDragOver}
                                onDrop={() => onDrop(globalIdx)}
                                onRemove={() => removeField(f.key)}
                                onMoveUp={() => moveField(globalIdx, globalIdx - 1)}
                                onMoveDown={() => moveField(globalIdx, globalIdx + 1)}
                              />
                            </div>
                          )
                        }
                        if (isFileSection) return null
                        return (
                          <div key={f.key}>
                            <FieldEditorCard
                              field={f}
                              index={globalIdx}
                              total={fields.length}
                              selected={selectedKey === f.key}
                              dragIdx={dragIdx}
                              onClick={() => setSelectedKey(f.key)}
                              onDragStart={() => onDragStart(globalIdx)}
                              onDragOver={onDragOver}
                              onDrop={() => onDrop(globalIdx)}
                              onRemove={() => removeField(f.key)}
                              onMoveUp={() => moveField(globalIdx, globalIdx - 1)}
                              onMoveDown={() => moveField(globalIdx, globalIdx + 1)}
                            />
                          </div>
                        )
                      })}
                    </div>

                    {/* 在分区底部加一个「+ 在此分区添加字段」提示 */}
                    <div className="mt-2 flex gap-2 flex-wrap border-t border-gray-100 pt-2">
                      {FIELD_TYPES.map(ft => (
                        <button key={ft.type}
                          onClick={() => addFieldToSection(secName, ft.type)}
                          className="text-xs px-2 py-1 border border-gray-200 rounded hover:bg-blue-50 hover:border-blue-300 transition text-gray-600">
                          + {ft.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )
              })}
              <button onClick={addSection}
                className="w-full px-3 py-3 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-600 hover:border-blue-500 hover:text-blue-600 hover:bg-blue-50 transition">
                + 添加新分区
              </button>
            </div>
          )}
        </div>

        {/* 右栏：属性编辑 */}
        <div className="w-72 bg-white rounded-lg border border-gray-200 p-4 overflow-auto">
          <h3 className="text-xs font-bold text-gray-500 uppercase mb-3">属性编辑</h3>
          {selectedField ? (
            <FieldPropsEditor
              field={selectedField}
              onChange={(updates) => updateField(selectedField.key, updates)}
            />
          ) : (
            <div className="text-gray-400 text-sm text-center mt-8">
              点击中间区域的字段<br />来编辑属性
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ============ 字段编辑卡片（所见即所得：实际渲染效果） ============
function FieldEditorCard({ field, index, total, selected, dragIdx, onClick, onDragStart, onDragOver, onDrop, onRemove, onMoveUp, onMoveDown }) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onClick={onClick}
      className={`border rounded-lg p-3 cursor-pointer transition bg-white ${
        selected ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200' : 'border-gray-200 hover:border-gray-300'
      } ${dragIdx === index ? 'opacity-50' : ''}`}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-gray-400 cursor-move">⣿</span>
          <span className="text-xs text-gray-400">{index + 1}.</span>
          <span className="text-sm font-medium">{field.label}</span>
          {field.required && <span className="text-red-500 text-xs">*</span>}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={(e) => { e.stopPropagation(); onMoveUp() }}
            disabled={index === 0}
            className="text-gray-400 hover:text-gray-700 disabled:opacity-30 px-1 text-xs">↑</button>
          <button onClick={(e) => { e.stopPropagation(); onMoveDown() }}
            disabled={index === total - 1}
            className="text-gray-400 hover:text-gray-700 disabled:opacity-30 px-1 text-xs">↓</button>
          <button onClick={(e) => { e.stopPropagation(); onRemove() }}
            className="text-red-400 hover:text-red-600 px-1 text-xs">✕</button>
        </div>
      </div>
      {/* 实际字段预览（所见即所得） */}
      <FieldRenderer field={field} />
    </div>
  )
}

// 实际渲染字段（与 DynamicForm 中完全一致）
function FieldRenderer({ field }) {
  switch (field.type) {
    case 'text':
      return <input type="text" placeholder={field.placeholder} className={inputCls} disabled />
    case 'textarea':
      return <textarea placeholder={field.placeholder} rows={3} className={inputCls} disabled />
    case 'number':
      return (
        <div className="flex items-center gap-2">
          <input type="number" placeholder={field.placeholder || '0.00'} className={inputCls} disabled />
          {field.unit && <span className="text-sm text-gray-500 whitespace-nowrap">{field.unit}</span>}
        </div>
      )
    case 'date':
      return <input type="date" className={inputCls} disabled />
    case 'select':
      return (
        <select className={inputCls} disabled>
          <option value="">请选择</option>
          {(field.options || []).map((o, i) => <option key={i}>{o}</option>)}
        </select>
      )
    case 'radio':
      return (
        <div className="flex flex-wrap gap-4">
          {(field.options || []).map((o, i) => (
            <label key={i} className="flex items-center gap-1.5 text-sm text-gray-700">
              <input type="radio" disabled /> {o}
            </label>
          ))}
        </div>
      )
    case 'checkbox':
      return (
        <div className="flex flex-wrap gap-4">
          {(field.options || []).map((o, i) => (
            <label key={i} className="flex items-center gap-1.5 text-sm text-gray-700">
              <input type="checkbox" disabled /> {o}
            </label>
          ))}
        </div>
      )
    case 'file':
      return (
        <div className="border-2 border-dashed border-gray-300 rounded-lg px-4 py-4 cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition min-h-[80px] flex flex-col justify-center text-center">
          <div className="text-sm text-gray-500">
            <span className="text-lg block mb-1">📎</span>
            拖拽文件到此处
            <div className="text-xs text-gray-400 mt-1">或点击选择文件 {field.multiple ? '（可多选）' : ''}</div>
          </div>
        </div>
      )
    default:
      return null
  }
}

// ============ 属性编辑组件 ============
function FieldPropsEditor({ field, onChange }) {
  const labelCls = "block text-xs font-bold text-gray-500 mb-1"
  const inputClsLocal = "w-full border border-gray-300 rounded-md px-2 py-1.5 text-sm mb-3"

  return (
    <div>
      <div className="text-xs text-gray-400 mb-3 pb-2 border-b">
        类型：<span className="font-mono text-purple-600">{field.type}</span> · 分区：
        <span className="font-mono text-purple-600">{field.section || '其他'}</span>
      </div>

      <label className={labelCls}>字段标签</label>
      <input
        type="text"
        value={field.label}
        onChange={e => onChange({ label: e.target.value })}
        className={inputClsLocal}
        placeholder="显示给用户的标签名"
      />

      <label className={labelCls}>字段标识 (key)</label>
      <input
        type="text"
        value={field.key}
        onChange={e => onChange({ key: e.target.value })}
        className={inputClsLocal}
        placeholder="英文标识，用于数据存储"
      />

      <label className={labelCls}>所属分区</label>
      <input
        type="text"
        value={field.section || ''}
        onChange={e => onChange({ section: e.target.value })}
        className={inputClsLocal}
        placeholder="如：项目基本信息、合作基本情况、文件管理"
        list="section-presets"
      />
      <datalist id="section-presets">
        <option value="项目基本信息" />
        <option value="合作基本情况" />
        <option value="项目基本情况" />
        <option value="文件管理" />
      </datalist>

      <label className="flex items-center gap-2 mb-3 cursor-pointer">
        <input
          type="checkbox"
          checked={field.required || false}
          onChange={e => onChange({ required: e.target.checked })}
          className="rounded"
        />
        <span className="text-sm">必填</span>
      </label>

      {(field.type === 'text' || field.type === 'textarea' || field.type === 'number') && (
        <>
          <label className={labelCls}>占位提示</label>
          <input
            type="text"
            value={field.placeholder || ''}
            onChange={e => onChange({ placeholder: e.target.value })}
            className={inputClsLocal}
          />
        </>
      )}

      {field.type === 'number' && (
        <>
          <label className={labelCls}>单位</label>
          <input
            type="text"
            value={field.unit || ''}
            onChange={e => onChange({ unit: e.target.value })}
            className={inputClsLocal}
            placeholder="如：万元、个、天"
          />
        </>
      )}

      {(field.type === 'select' || field.type === 'radio' || field.type === 'checkbox') && (
        <>
          <label className={labelCls}>选项列表</label>
          <div className="space-y-2 mb-3">
            {(field.options || []).map((opt, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type="text"
                  value={opt}
                  onChange={e => {
                    const newOpts = [...field.options]
                    newOpts[i] = e.target.value
                    onChange({ options: newOpts })
                  }}
                  className="flex-1 border border-gray-300 rounded-md px-2 py-1 text-sm"
                />
                <button
                  onClick={() => {
                    const newOpts = field.options.filter((_, j) => j !== i)
                    onChange({ options: newOpts })
                  }}
                  className="text-red-400 hover:text-red-600 px-1 text-xs"
                >✕</button>
              </div>
            ))}
            <button
              onClick={() => onChange({ options: [...(field.options || []), `选项${(field.options || []).length + 1}`] })}
              className="text-sm text-blue-600 hover:text-blue-800"
            >+ 添加选项</button>
          </div>
        </>
      )}

      {field.type === 'file' && (
        <>
          <label className="flex items-center gap-2 mb-3 cursor-pointer">
            <input
              type="checkbox"
              checked={field.multiple || false}
              onChange={e => onChange({ multiple: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm">允许多文件</span>
          </label>
          <label className={labelCls}>允许的文件类型</label>
          <select
            value={field.accept || '*'}
            onChange={e => onChange({ accept: e.target.value })}
            className={inputClsLocal}
          >
            <option value="*">所有文件</option>
            <option value="image/*">仅图片</option>
            <option value=".pdf">仅 PDF</option>
            <option value=".doc,.docx">仅 Word</option>
            <option value=".xls,.xlsx">仅 Excel</option>
          </select>
        </>
      )}
    </div>
  )
}
