import { useState, useEffect, useMemo, useRef } from 'react'
import {
  createFormInstance, updateFormInstance, initFormFolders, uploadFormFiles, listFormFiles,
  deleteFormFile, getUsers, listStorageZones, getFormInstance, default as api,
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

export default function DynamicForm({ template, onClose, onSubmitted, instanceId, projectId = null, onInstanceSaved, readOnly = false, isAdmin = false }) {
  const { user } = useAuthStore()
  // emoji 用 String.fromCharCode 注入，避免源码字面量被工具截断
  const EMOJI_BOOK = String.fromCharCode(0x1F4D6)
  const EMOJI_SHIELD = String.fromCharCode(0x1F6E1) + String.fromCharCode(0xFE0F)
  const EMOJI_LOCK = String.fromCharCode(0x1F512)

  // ★ 编辑模式：项目信息卡 + 中标状态
  const [projectInfo, setProjectInfo] = useState(null)
  const [winBidDraft, setWinBidDraft] = useState("in_progress")

  useEffect(() => {
    if (!instanceId) return
    ;(async () => {
      try {
        const r = await getFormInstance(instanceId)
        const v = r.data?.data || {}
        // 根据模板名选择正确的 fallback label
        const isSelf = (template.name || '').includes('自营')
        const info = {
          project_name: v.project_name || v["项目名称"] || "-",
          project_type: v.project_type || v["项目类型"] || "-",
          expected_amount: v.expected_amount || v["预计金额"] || v["预计落单金额（万元）"] || "-",
          partner_company: v.partner_company || v["公司名称"] || v["客户单位名称"] || "-",
          contact_person: v.contact_person || v["联系人"] || v["业主方联系人"] || "-",
          contact_info: v.contact_info || v["联系方式"] || v["业主方联系方式"] || "-"
        }
        setProjectInfo(info)
        // 填充所有表单字段到 values 状态
        setValues(v)
        // 优先从 Project 表加载中标状态，其次从实例数据
        if (projectId) {
          try {
            const projRes = await api.get(`/projects/${projectId}`)
            setWinBidDraft(projRes.data?.win_bid_status || "in_progress")
          } catch {
            setWinBidDraft(v.win_bid_status || "in_progress")
          }
        } else {
          setWinBidDraft(v.win_bid_status || "in_progress")
        }
      } catch (e) {
        console.warn("[DynamicForm] loadInstance failed:", e)
      }
    })()
  }, [instanceId, projectId])
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
    if (readOnly) return
    if (!validate()) return
    setSubmitting(true)
    try {
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

      let targetInstanceId = instanceId

      if (targetInstanceId) {
        // ★ 编辑模式：更新已有实例
        await updateFormInstance(targetInstanceId, { data: submitData })

        // 保存中标状态到 Project 表
        if (projectId) {
          await api.put(`/projects/${projectId}`, { win_bid_status: winBidDraft })
        }
      } else {
        // ★ 新建模式：创建新实例
        const instanceRes = await createFormInstance({ template_id: template.id, data: submitData })
        targetInstanceId = instanceRes.data.id
      }

      const tenderKey = fields.find(isTenderFile)?.key
      const bidKey = fields.find(isBidFile)?.key

      const uploadPromises = []
      if (tenderKey && selectedFiles[tenderKey]?.length) {
        uploadPromises.push(uploadFormFiles(targetInstanceId, 'tender', selectedFiles[tenderKey]))
      }
      if (bidKey && selectedFiles[bidKey]?.length) {
        uploadPromises.push(uploadFormFiles(targetInstanceId, 'bid', selectedFiles[bidKey]))
      }
      if (uploadPromises.length > 0) {
        await Promise.all(uploadPromises)
      }

      alert('提交成功')
      onInstanceSaved?.(targetInstanceId)
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

    // 只读模式：不显示上传区域，仅显示文件夹路径
    if (readOnly) {
      return (
        <div className="border border-gray-200 rounded-lg px-4 py-4 bg-gray-50 min-h-[60px] flex flex-col justify-center">
          {folderPreview && (
            <div className="text-xs text-blue-600 truncate font-mono flex items-center justify-center">
              <span className="mr-1">📁</span>
              <span>{folderPreview}</span>
            </div>
          )}
          {existingList.length === 0 && (
            <div className="text-xs text-gray-400 text-center mt-1">只读模式，不可上传文件</div>
          )}
        </div>
      )
    }

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
                {instanceId && !readOnly && (
                  <button type="button" onClick={() => deleteExistingFile(folderType, file.name)}
                    className="text-gray-400 hover:text-red-500">✕</button>
                )}
              </div>
            </div>
          ))}
          {names.map((name, i) => (
            <div key={`new-${i}`} className="px-3 py-1.5 text-xs text-gray-700 border-b border-gray-100 last:border-0 flex items-center justify-between hover:bg-gray-50">
              <span className="truncate text-blue-700">📄 {name}</span>
              {!readOnly && (
                <div className="flex items-center gap-1 ml-2 shrink-0">
                  <span className="text-[10px] text-blue-400">待上传</span>
                  <button type="button" onClick={() => removeFile(f.key, i)}
                    className="text-gray-400 hover:text-red-500">✕</button>
                </div>
              )}
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

    // 只读模式：显示纯文本值
    if (readOnly) {
      let displayVal = val
      if (val === undefined || val === null || val === '') {
        displayVal = <span className="text-gray-300">（未填写）</span>
      } else if (f.type === 'number') {
        displayVal = f.unit ? `${val} ${f.unit}` : val
      } else if (f.type === 'date' && val) {
        displayVal = val
      } else if (f.type === 'select' || f.type === 'radio') {
        displayVal = val
      } else if (f.type === 'checkbox') {
        displayVal = (val || []).length > 0 ? (val || []).join('、') : <span className="text-gray-300">（未填写）</span>
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
      return (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {f.label}{f.required && !isSalesField && <Star />}
          </label>
          <div className="w-full border border-gray-200 rounded-md px-3 py-2 bg-gray-50 text-gray-700 text-sm min-h-[38px]">
            {displayVal}
          </div>
        </div>
      )
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

  const sn = (template.name || '')
  const isSelf = sn.includes('自营')
  const lblAmount = isSelf ? '预计落单金额' : '预计金额'
  const lblCompany = isSelf ? '客户单位名称' : '公司名称'
  const lblContact = isSelf ? '业主方联系人' : '联系人'
  const lblPhone = isSelf ? '业主方联系方式' : '联系方式'

  return (
    <div className="w-full bg-white">
      {/* 顶部标题栏 — 与 ProjectForm 严格一致：标题 + 状态徽章 + 关闭按钮 */}
      <div className="flex items-center justify-between pb-4 mb-4 border-b">
        <h3 className="text-xl font-bold text-gray-800">
          {(template.name === '渠道项目登记表' || template.name === '自建项目登记表' || template.name === '自营项目登记表') ? (instanceId ? (readOnly ? '查看项目详情' : (isAdmin ? '编辑项目（管理员模式）' : '编辑项目（仅上传文件）')) : '新建项目') : template.name}
          <span className="ml-2 text-[10px] font-normal text-gray-400">v2.1</span>
        </h3>
        {(instanceId || readOnly) && (
          <span className="text-xs px-2 py-1 rounded border"
            style={{
              color: readOnly ? '#6b7280' : (isAdmin ? '#059669' : '#d97706'),
              background: readOnly ? '#f3f4f6' : (isAdmin ? '#ecfdf5' : '#fffbeb'),
              borderColor: readOnly ? '#d1d5db' : (isAdmin ? '#a7f3d0' : '#fde68a')
            }}>
            {readOnly ? EMOJI_BOOK+' 只读查看模式' : (isAdmin ? EMOJI_SHIELD+' 管理员权限：可修改中标状态及上传文件' : EMOJI_LOCK+' 项目已建，字段锁定，仅可上传/查看文件')}
          </span>
        )}
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
      </div>

      <form onSubmit={handleSubmit}>

        {/* 编辑模式：顶部蓝色「项目信息」只读区 + 中标状态行（与渠道 ProjectForm 一致） */}
        {instanceId && !readOnly && (
          <div className="mb-5 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="text-sm font-bold text-blue-800 mb-3 flex items-center gap-2">
              <span>【项目信息】</span>
              <span className="text-xs text-green-600 bg-green-100 px-2 py-0.5 rounded-full">管理员可修改中标状态</span>
            </div>
            <div className="grid grid-cols-3 gap-x-8 gap-y-2 text-sm">
              <div><span className="text-gray-500">项目名称：</span><span className="text-gray-800">{projectInfo?.project_name || "-"}</span></div>
              <div><span className="text-gray-500">项目类型：</span><span className="text-gray-800">{projectInfo?.project_type || "-"}</span></div>
              <div><span className="text-gray-500">{lblAmount}：</span><span className="text-gray-800">{projectInfo?.expected_amount || "-"} 万元</span></div>
              <div><span className="text-gray-500">{lblCompany}：</span><span className="text-gray-800">{projectInfo?.partner_company || "-"}</span></div>
              <div><span className="text-gray-500">{lblContact}：</span><span className="text-gray-800">{projectInfo?.contact_person || "-"}</span></div>
              <div><span className="text-gray-500">{lblPhone}：</span><span className="text-gray-800">{projectInfo?.contact_info || "-"}</span></div>
            </div>
            <div className="mt-3 pt-3 border-t border-blue-200">
              <div className="flex items-center gap-3 flex-wrap">
                <label className="text-sm font-medium text-gray-700">中标状态（可修改）：</label>
                <select
                  value={winBidDraft || "in_progress"}
                  onChange={e => setWinBidDraft(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-1.5 text-sm bg-white"
                >
                  <option value="in_progress">进行中</option>
                  <option value="yes">中标</option>
                  <option value="no">未中标</option>
                </select>
                <span className="text-xs text-gray-500">首次修改后保存生效，后续修改需填写理由并验证密码</span>
              </div>
            </div>
          </div>
        )}

        {/* 查看模式：顶部蓝色「项目信息」只读区 + 中标状态（只读） */}
        {instanceId && readOnly && (
          <div className="mb-5 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="text-sm font-bold text-blue-800 mb-3">【项目信息】</div>
            <div className="grid grid-cols-3 gap-x-8 gap-y-2 text-sm">
              <div><span className="text-gray-500">项目名称：</span><span className="text-gray-800">{projectInfo?.project_name || "-"}</span></div>
              <div><span className="text-gray-500">项目类型：</span><span className="text-gray-800">{projectInfo?.project_type || "-"}</span></div>
              <div><span className="text-gray-500">{lblAmount}：</span><span className="text-gray-800">{projectInfo?.expected_amount || "-"} 万元</span></div>
              <div><span className="text-gray-500">{lblCompany}：</span><span className="text-gray-800">{projectInfo?.partner_company || "-"}</span></div>
              <div><span className="text-gray-500">{lblContact}：</span><span className="text-gray-800">{projectInfo?.contact_person || "-"}</span></div>
              <div><span className="text-gray-500">{lblPhone}：</span><span className="text-gray-800">{projectInfo?.contact_info || "-"}</span></div>
            </div>
            <div className="mt-3 pt-3 border-t border-blue-200">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-sm font-medium text-gray-700">中标状态：</span>
                <span className={`text-sm font-semibold ${winBidDraft === 'yes' ? 'text-green-600' : winBidDraft === 'no' ? 'text-red-500' : 'text-yellow-600'}`}>
                  {winBidDraft === 'yes' ? '中标' : winBidDraft === 'no' ? '未中标' : '进行中'}
                </span>
              </div>
            </div>
          </div>
        )}

        {sections.map(renderSection)}

        {fields.length === 0 && (
          <div className="text-center text-gray-400 py-8">该表单没有字段</div>
        )}

        {!readOnly && (
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
        )}

        <div className="flex justify-end gap-3 pt-5 border-t mt-6">
          <button type="button" onClick={onClose}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition">
            {readOnly ? "关闭" : "取消"}
          </button>
          {!readOnly && (
          <button type="submit" disabled={submitting}
            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition shadow-sm">
            {submitting ? '提交中...' : '提交'}
          </button>
          )}
        </div>
      </form>
    </div>
  )
}
