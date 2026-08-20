import { useState, useEffect, useMemo, useRef } from 'react'
import {
  createFormInstance, initFormFolders, uploadFormFiles, listFormFiles,
  deleteFormFile, getUsers, listStorageZones, default as api,
} from '../api'
import { useAuthStore } from '../stores/auth'

const inputCls = "w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-blue-200 focus:border-blue-500"
const inputErrCls = "w-full border border-red-400 rounded-md px-3 py-2 focus:ring-2 focus:ring-blue-200 focus:border-blue-500"

const Star = () => <span className="text-red-500 ml-1 font-bold">*</span>

const DEFAULT_SECTION = '其他'

const SECTION_BAR = "bg-green-50 border-l-4 border-green-500 px-3 py-1.5 mb-3"
const SECTION_TITLE = "text-sm font-bold text-green-700"

const TENDER_FILE_KEYS = ['tender_file', 'zhao_biao', 'tender']
const BID_FILE_KEYS = ['bid_file', 'tou_biao', 'bid']

export default function DynamicForm({ template, onClose, onSubmitted, instanceId, onInstanceSaved }) {
  const { user } = useAuthStore()
  const [values, setValues] = useState({})
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [fileNames, setFileNames] = useState({})
  const [selectedFiles, setSelectedFiles] = useState({})
  const fileInputRefs = useRef({})
  const [approverName, setApproverName] = useState('')
  const [approverId, setApproverId] = useState(null)
  const [users, setUsers] = useState([])
  const [tenderFiles, setTenderFiles] = useState([])
  const [bidFiles, setBidFiles] = useState([])
  // 路径预览
  const [tenderFolderPreview, setTenderFolderPreview] = useState('')
  const [bidFolderPreview, setBidFolderPreview] = useState('')
  // 存储区域（用于路径预览计算）
  const [storageZones, setStorageZones] = useState([])

  const fields = template.fields || []

  useEffect(() => {
    // 加载用户列表（用于审批人下拉）
    getUsers().then(res => {
      const list = Array.isArray(res) ? res : (res.data || [])
      const filtered = list.filter(u => u.id !== undefined && u.id !== user?.id)
      setUsers(filtered)
      // 默认审批人：用户的上级，没有则第一个管理员
      let defaultApproverId = user?.parent_id
      if (!defaultApproverId) {
        const admin = filtered.find(u => u.role === 'admin')
        defaultApproverId = admin?.id
      }
      if (defaultApproverId) {
        const approver = filtered.find(u => u.id === defaultApproverId)
        if (approver) {
          setApproverId(approver.id)
          setApproverName(`${approver.real_name} (${approver.username})`)
          return
        }
      }
      setApproverName('系统管理员')
    }).catch(() => setApproverName('系统管理员'))

    // 加载存储区域（仅用于路径预览计算，不让用户选择）
    listStorageZones().then(res => {
      const items = res.data?.items || []
      setStorageZones(items.filter(z => z.is_active))
    }).catch(() => {})
  }, [user])

  const loadExistingFiles = async () => {
    if (!instanceId) return
    try {
      const [tenderRes, bidRes] = await Promise.all([
        listFormFiles({ instance_id: instanceId, folder_type: 'tender' }),
        listFormFiles({ instance_id: instanceId, folder_type: 'bid' }),
      ])
      setTenderFiles(tenderRes.data.files || [])
      setBidFiles(bidRes.data.files || [])
    } catch (e) {
      console.error('加载已有文件失败', e)
    }
  }

  useEffect(() => {
    loadExistingFiles()
  }, [instanceId])

  // 计算文件路径预览（与渠道项目一致：账号+项目名+日期）
  useEffect(() => {
    if (storageZones.length === 0) return
    // 优先使用模板设置的区域（template.storage_zone_id），否则用第一个
    const tplZoneId = template.storage_zone_id
    const z = storageZones.find(x => x.id === tplZoneId) || storageZones[0]
    if (!z) return
    // 字段 key 是 FormBuilder 生成的 field_xxx_xxx 形式，按 label 反查字段值
    const findByLabel = (lbl) => {
      const f = fields.find(x => (x.label || '').trim() === lbl)
      return f ? values[f.key] : undefined
    }
    const responsibleSales = values.responsible_sales || findByLabel('责任销售') || user?.real_name || ''
    const projectName = values.project_name || findByLabel('项目名称') || findByLabel('项目名') || values.name || '项目名'
    const date = new Date().toISOString().slice(0, 10)
    const folderName = `${responsibleSales}+${projectName}+${date}`
    // 显示路径：包括 webdav_base_path（如「自营资料」/「渠道资料」）
    const basePath = (z.webdav_base_path || '').replace(/^\/+/, '')
    const subPath = z.sub_path || ''
    const parts = []
    if (basePath) parts.push(basePath)
    if (subPath) parts.push(subPath)
    parts.push(folderName)
    const displayPath = parts.join('/')
    setTenderFolderPreview(`${displayPath}/招标资料`)
    setBidFolderPreview(`${displayPath}/投标文档`)
  }, [storageZones, template.storage_zone_id, values, fields, user])

  const deleteExistingFile = async (folderType, fileName) => {
    if (!confirm(`确认删除文件 "${fileName}" 吗？`)) return
    try {
      await deleteFormFile({ instance_id: instanceId, folder_type: folderType, file_name: fileName })
      loadExistingFiles()
    } catch (e) {
      alert('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  const sections = useMemo(() => {
    const map = new Map()
    const order = []
    fields.forEach(f => {
      const sec = f.section || DEFAULT_SECTION
      if (!map.has(sec)) { map.set(sec, []); order.push(sec) }
      map.get(sec).push(f)
    })
    return order.map(name => [name, map.get(name)])
  }, [fields])

  const handleChange = (key, value) => {
    setValues(prev => ({ ...prev, [key]: value }))
    setErrors(prev => ({ ...prev, [key]: undefined }))
  }

  const handleFilePicked = (key, files) => {
    const arr = Array.from(files)
    const names = arr.map(f => f.name)
    setFileNames(prev => ({ ...prev, [key]: names }))
    setSelectedFiles(prev => ({ ...prev, [key]: arr }))
  }

  const removeFile = (key, idx) => {
    setFileNames(prev => {
      const list = [...(prev[key] || [])]
      list.splice(idx, 1)
      return { ...prev, [key]: list }
    })
    setSelectedFiles(prev => {
      const list = [...(prev[key] || [])]
      list.splice(idx, 1)
      return { ...prev, [key]: list }
    })
  }

  const validate = () => {
    const errs = {}
    fields.forEach(f => {
      const val = values[f.key]
      // 责任销售字段统一不强制必填（即使 DB 中标记 required=true）
      const isSales = (f.label || '').trim() === '责任销售'
      if (f.required && !isSales) {
        if (val === undefined || val === null || val === '' ||
            (Array.isArray(val) && val.length === 0)) {
          errs[f.key] = `${f.label}必填`
        }
      }
      if (f.type === 'number' && val !== undefined && val !== '' && val !== null) {
        const num = Number(val)
        if (isNaN(num)) errs[f.key] = '请输入有效数字'
        if (f.min != null && num < f.min) errs[f.key] = `不能小于${f.min}`
        if (f.max != null && num > f.max) errs[f.key] = `不能大于${f.max}`
      }
    })
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    try {
      // 后端会自动分配审批人和存储区域 + 创建 NAS 目录，前端无需再调 initFormFolders
      // 但后端需要根据 label（中文）反查"责任销售"/"项目名称"字段，所以前端做约定字段映射
      const submitData = { ...values }
      // 约定：如果表单中有 label 为「责任销售」/「项目名称」/「合作单位」的字段，
      // 把它们的值也写到约定的英文 key，让后端 create_instance 能正确读取
      fields.forEach(f => {
        const lbl = (f.label || '').trim()
        const v = values[f.key]
        if (lbl === '责任销售' && v) submitData.responsible_sales = v
        if ((lbl === '项目名称' || lbl === '项目名') && v) submitData.project_name = v
        if ((lbl === '合作单位' || lbl === '合作公司') && v) submitData.partner_company = v
        if (lbl === '项目类型' && v) submitData.project_type = v
      })
      const instanceRes = await createFormInstance({ template_id: template.id, data: submitData })
      const instanceId = instanceRes.data.id

      const tenderKey = fields.find(isTenderFile)?.key
      const bidKey = fields.find(isBidFile)?.key

      const uploadPromises = []
      if (tenderKey && selectedFiles[tenderKey]?.length) {
        uploadPromises.push(uploadFormFiles(instanceId, 'tender', selectedFiles[tenderKey]))
      }
      if (bidKey && selectedFiles[bidKey]?.length) {
        uploadPromises.push(uploadFormFiles(instanceId, 'bid', selectedFiles[bidKey]))
      }
      if (uploadPromises.length > 0) {
        await Promise.all(uploadPromises)
      }

      alert('提交成功')
      onInstanceSaved?.(instanceId)
      onSubmitted?.()
    } catch (err) {
      alert('提交失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setSubmitting(false)
    }
  }

  const isTenderFile = (f) => TENDER_FILE_KEYS.includes(f.key)
  const isBidFile = (f) => BID_FILE_KEYS.includes(f.key)

  const renderDropZone = (f, folderPreview) => {
    const names = fileNames[f.key] || []
    const isTender = isTenderFile(f)
    const existingList = isTender ? tenderFiles : bidFiles

    return (
      <div
        onDragOver={(e) => { e.preventDefault(); e.stopPropagation() }}
        onDrop={(e) => {
          e.preventDefault(); e.stopPropagation()
          handleFilePicked(f.key, Array.from(e.dataTransfer.files))
        }}
        onClick={() => fileInputRefs.current[f.key]?.click()}
        className="border-2 border-dashed border-gray-300 rounded-lg px-4 py-4 cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition min-h-[96px] flex flex-col justify-center text-center"
      >
        {folderPreview && (
          <div className="text-xs text-blue-600 mb-2 truncate font-mono flex items-center justify-center">
            <span className="mr-1">📁</span>
            <span>{folderPreview}</span>
          </div>
        )}
        {names.length > 0 || existingList.length > 0 ? (
          <div className="text-sm text-gray-600">
            {existingList.length > 0 && (
              <div className="mb-1">
                <span className="text-green-600 font-medium">{existingList.length} 个文件已上传</span>
              </div>
            )}
            {names.length > 0 && (
              <div>
                <span className="text-blue-600 font-medium">{names.length} 个新文件已选择</span>
              </div>
            )}
            <div className="text-xs text-gray-400 mt-1">点击添加更多文件</div>
          </div>
        ) : (
          <div className="text-sm text-gray-500">
            <span className="text-lg block mb-1">📎</span>
            拖拽文件到此处
            <div className="text-xs text-gray-400 mt-1">或点击选择文件</div>
          </div>
        )}
        <input
          ref={el => fileInputRefs.current[f.key] = el}
          type="file"
          multiple
          onChange={(e) => handleFilePicked(f.key, Array.from(e.target.files))}
          className="hidden"
        />
      </div>
    )
  }

  const renderFileList = (f) => {
    const names = fileNames[f.key] || []
    const isTender = isTenderFile(f)
    const existingList = isTender ? tenderFiles : bidFiles
    const folderType = isTender ? 'tender' : 'bid'
    const totalCount = names.length + existingList.length

    if (totalCount === 0) {
      return (
        <div className="mt-2 text-xs text-gray-400 text-center py-3 border border-dashed border-gray-200 rounded">
          暂无文件
        </div>
      )
    }
    return (
      <div className="mt-2 border border-gray-200 rounded-md bg-white">
        <div className="px-3 py-1.5 text-xs font-semibold text-gray-600 bg-gray-50 border-b border-gray-200 rounded-t-md flex items-center justify-between">
          <span>共 {totalCount} 个文件</span>
        </div>
        <div className="max-h-32 overflow-y-auto">
          {existingList.map((file, i) => (
            <div key={`existing-${i}`} className="px-3 py-1.5 text-xs text-gray-700 border-b border-gray-100 last:border-0 flex items-center justify-between hover:bg-gray-50">
              <span className="truncate text-green-700">📄 {file.name}</span>
              <div className="flex items-center gap-1 ml-2 shrink-0">
                <span className="text-[10px] text-gray-400">已上传</span>
                {instanceId && (
                  <button type="button" onClick={() => deleteExistingFile(folderType, file.name)}
                    className="text-gray-400 hover:text-red-500">✕</button>
                )}
              </div>
            </div>
          ))}
          {names.map((name, i) => (
            <div key={`new-${i}`} className="px-3 py-1.5 text-xs text-gray-700 border-b border-gray-100 last:border-0 flex items-center justify-between hover:bg-gray-50">
              <span className="truncate text-blue-700">📄 {name}</span>
              <div className="flex items-center gap-1 ml-2 shrink-0">
                <span className="text-[10px] text-blue-400">待上传</span>
                <button type="button" onClick={() => removeFile(f.key, i)}
                  className="text-gray-400 hover:text-red-500">✕</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  const renderField = (f) => {
    const val = values[f.key]
    const err = errors[f.key]
    const cls = err ? inputErrCls : inputCls

    // 占位符统一覆盖：责任销售字段统一文案（不修改数据库中的模板字段定义）
    let fieldPh = f.placeholder
    // 责任销售字段统一不强制必填（数据库中可能仍标记 required=true，统一忽略）
    const isSalesField = (f.label || '').trim() === '责任销售'
    if (isSalesField) {
      fieldPh = '如由销售本人建立，此处可不填'
    }

    if (f.type === 'file') {
      return (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {f.label}{f.required && !isSalesField && <Star />}
          </label>
          {renderDropZone(f)}
          {renderFileList(f)}
        </div>
      )
    }

    let input = null
    switch (f.type) {
      case 'text':
        input = <input type="text" value={val || ''} onChange={e => handleChange(f.key, e.target.value)} placeholder={fieldPh} className={cls} />
        break
      case 'textarea':
        input = <textarea value={val || ''} onChange={e => handleChange(f.key, e.target.value)} placeholder={fieldPh} rows={5} className={cls} />
        break
      case 'number':
        input = (
          <div className="flex items-center gap-2">
            <input type="number" step="0.01" value={val ?? ''} onChange={e => handleChange(f.key, e.target.value)} placeholder={fieldPh || '0.00'} className={cls} />
            {f.unit && <span className="text-sm text-gray-500 whitespace-nowrap">{f.unit}</span>}
          </div>
        )
        break
      case 'date':
        input = <input type="date" value={val || ''} onChange={e => handleChange(f.key, e.target.value)} className={cls} />
        break
      case 'select':
        input = (
          <select value={val || ''} onChange={e => handleChange(f.key, e.target.value)} className={cls}>
            <option value="">请选择</option>
            {(f.options || []).map((o, i) => <option key={i} value={o}>{o}</option>)}
          </select>
        )
        break
      case 'radio':
        input = (
          <div className="flex flex-wrap gap-4">
            {(f.options || []).map((o, i) => (
              <label key={i} className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
                <input type="radio" name={f.key} checked={val === o} onChange={() => handleChange(f.key, o)} />
                {o}
              </label>
            ))}
          </div>
        )
        break
      case 'checkbox':
        input = (
          <div className="flex flex-wrap gap-4">
            {(f.options || []).map((o, i) => (
              <label key={i} className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
                <input type="checkbox" checked={(val || []).includes(o)}
                  onChange={(e) => {
                    const arr = val || []
                    handleChange(f.key, e.target.checked ? [...arr, o] : arr.filter(x => x !== o))
                  }} />
                {o}
              </label>
            ))}
          </div>
        )
        break
      default:
        input = <input type="text" value={val || ''} onChange={e => handleChange(f.key, e.target.value)} className={cls} />
    }

    return (
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {f.label}{f.required && !isSalesField && <Star />}
        </label>
        {input}
        {err && <p className="text-red-500 text-xs mt-1">{err}</p>}
      </div>
    )
  }

  const renderFileManagementSection = ([secName, secFields]) => {
    const tenderField = secFields.find(isTenderFile)
    const bidField = secFields.find(isBidFile)
    const otherFileFields = secFields.filter(f => f !== tenderField && f !== bidField)

    return (
      <div key={secName} className="mb-5">
        <div className={SECTION_BAR}>
          <span className={SECTION_TITLE}>{secName}</span>
        </div>
        <div className="grid grid-cols-2 gap-x-8 gap-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">招标资料上传</label>
            {tenderField ? (
              <>
                {renderDropZone(tenderField, tenderFolderPreview)}
                {renderFileList(tenderField)}
              </>
            ) : (
              <div className="text-xs text-gray-400 text-center py-3 border border-dashed border-gray-200 rounded">
                暂无文件字段
              </div>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">投标文档及其他资料上传</label>
            {bidField ? (
              <>
                {renderDropZone(bidField, bidFolderPreview)}
                {renderFileList(bidField)}
              </>
            ) : (
              <div className="text-xs text-gray-400 text-center py-3 border border-dashed border-gray-200 rounded">
                暂无文件字段
              </div>
            )}
          </div>
        </div>
        {otherFileFields.length > 0 && (
          <div className="grid grid-cols-2 gap-x-8 gap-y-3 mt-3">
            {otherFileFields.map(f => (
              <div key={f.id}>
                {renderField(f)}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  const renderSection = ([secName, secFields]) => {
    const isFileSection = secFields.every(f => f.type === 'file')
    const isTextareaOnly = secFields.length === 1 && secFields[0].type === 'textarea'

    if (isFileSection) {
      return renderFileManagementSection([secName, secFields])
    }

    let layoutCls = 'grid grid-cols-2 gap-x-8 gap-y-3'
    if (isTextareaOnly || secName === '项目基本情况') {
      layoutCls = ''
    }

    return (
      <div key={secName} className="mb-5">
        <div className={SECTION_BAR}>
          <span className={SECTION_TITLE}>{secName}</span>
        </div>
        <div className={layoutCls}>
          {secFields.map(f => (
            <div key={f.id}>
              {renderField(f)}
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="w-full bg-white">
      {/* 顶部标题栏 — 与 ProjectForm 严格一致：仅标题 + 关闭按钮 */}
      <div className="flex items-center justify-between pb-4 mb-4 border-b">
        <h3 className="text-xl font-bold text-gray-800">
          {/* 内置模板按用途显示为「新建项目」 */}
          {template.name === '渠道项目登记表' || template.name === '自建项目登记表' || template.name === '自营项目登记表' ? '新建项目' : template.name}
          <span className="ml-2 text-[10px] font-normal text-gray-400">v2.1</span>
        </h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
      </div>

      <form onSubmit={handleSubmit}>
        {sections.map(renderSection)}

        {fields.length === 0 && (
          <div className="text-center text-gray-400 py-8">该表单没有字段</div>
        )}

        <div className="mb-5">
          <div className="bg-green-50 border-l-4 border-green-500 px-3 py-1.5 mb-3">
            <span className="text-sm font-bold text-green-700">审批人</span>
            <span className="text-xs text-gray-500 ml-2">（系统根据用户管理中的设置自动分配）</span>
          </div>
          <input
            type="text"
            value={approverName}
            readOnly
            className="w-full border border-gray-200 rounded-md px-3 py-2 bg-gray-50 text-gray-700"
          />
        </div>

        <div className="flex justify-end gap-3 pt-5 border-t mt-6">
          <button type="button" onClick={onClose}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition">
            取消
          </button>
          <button type="submit" disabled={submitting}
            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition shadow-sm">
            {submitting ? '提交中...' : '提交'}
          </button>
        </div>
      </form>
    </div>
  )
}
