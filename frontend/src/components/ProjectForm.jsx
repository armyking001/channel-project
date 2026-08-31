import { useState, useEffect, useRef } from 'react'
import { createProject, updateProject, getUsers, previewFileStoragePath, listStorageFiles, rebuildProjectFolders } from '../api'
import { useAuthStore } from '../stores/auth'

const Star = () => <span className="text-red-500 ml-1 font-bold" title="必填项">*</span>

const PROJECT_TYPE_OPTIONS = [
  { value: '信息化', label: '信息化' },
  { value: '智能化', label: '智能化' },
  { value: '机电消防', label: '机电消防' },
  { value: '软件开放', label: '软件开放' },
  { value: '系统运维', label: '系统运维' },
  { value: 'XC/SM', label: 'XC/SM' },
  { value: '军队武警', label: '军队武警' },
  { value: '其他', label: '其他' },
]

const inputCls = "w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-blue-200 focus:border-blue-500"
const inputErrCls = "w-full border border-red-400 rounded-md px-3 py-2 focus:ring-2 focus:ring-blue-200 focus:border-blue-500"

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB']
  let i = 0; let n = bytes
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++ }
  return `${n.toFixed(n >= 100 ? 0 : n >= 10 ? 1 : 2)} ${u[i]}`
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function stripUrlPrefix(url) {
  if (!url) return ''
  return url.replace(/^https?:\/\/[^/]+\/+/, '')
}

const DIAG_BADGE = {
  ok:      { label: '✓ 正常', cls: 'bg-green-50 text-green-700 border-green-200' },
  wrong:   { label: '⚠ 路径错误', cls: 'bg-red-50 text-red-700 border-red-300' },
  empty:   { label: '⚠ 路径为空', cls: 'bg-red-50 text-red-700 border-red-300' },
  unknown: { label: '? 未关联',   cls: 'bg-gray-50 text-gray-500 border-gray-200' },
}

export default function ProjectForm({ project, onClose, onSaved, onDelete, readOnly = false, withdrawMode = false, diagnoseResult = null, onRebuilt = null, onFilesUploaded = null }) {
  const { user: currentUser } = useAuthStore()
  const isEdit = !!project
  const isAdmin = currentUser?.role === 'admin'
  const isSelfProject = project?.source === 'self'
  const lblAmount = isSelfProject ? '预计落单金额' : '预计金额'
  const lblCompany = isSelfProject ? '客户单位名称' : '公司名称'
  const lblContact = isSelfProject ? '业主方联系人' : '联系人'
  const lblPhone = isSelfProject ? '业主方联系方式' : '联系方式'
  const fileTenderRef = useRef(null)
  const fileBidRef = useRef(null)

  const initial = (key, fallback = '') => {
    if (!project) return fallback
    const v = project[key]
    return v ?? fallback
  }

  const [form, setForm] = useState({
    project_name: initial('project_name'),
    project_code: initial('project_code'),
    project_type: initial('project_type', '其他'),
    responsible_sales: initial('responsible_sales'),
    expected_amount: isEdit ? ((project.expected_amount ?? 0)).toString() : '',
    tender_time: initial('tender_time'),
    bid_time: initial('bid_time'),
    owner_contact_person: initial('owner_contact_person'),
    owner_contact_info: initial('owner_contact_info'),
    partner_company: initial('partner_company'),
    company_address: initial('company_address'),
    main_qualification: initial('main_qualification'),
    legal_representative: initial('legal_representative'),
    contact_person: initial('contact_person'),
    contact_info: initial('contact_info'),
    cooperation_mode: initial('cooperation_mode', 'long_term'),
    fee_mode: initial('fee_mode', 'mutual'),
    fee_amount: initial('fee_amount', ''),
    is_sm: initial('is_sm', 'no'),
    win_bid_status: initial('win_bid_status', 'in_progress'),
    project_overview: initial('project_overview'),
    storage_zone_id: initial('storage_zone_id') || 1,
  })

  const [errors, setErrors] = useState({})

  const [winBidUnlocked, setWinBidUnlocked] = useState(false)
  const [showWinBidModal, setShowWinBidModal] = useState(false)
  const [winBidReason, setWinBidReason] = useState('')
  const [winBidPassword, setWinBidPassword] = useState('')
  const [winBidModalError, setWinBidModalError] = useState('')

  const [tenderPreview, setTenderPreview] = useState('')
  const [bidPreview, setBidPreview] = useState('')
  const [uploadingTender, setUploadingTender] = useState(false)
  const [uploadingBid, setUploadingBid] = useState(false)
  // 上传进度状态: { tender: { percent, currentFile, done, total }, bid: {...} }
  const [uploadProgress, setUploadProgress] = useState({ tender: null, bid: null })

  const [tenderFiles, setTenderFiles] = useState([])
  const [bidFiles, setBidFiles] = useState([])
  const [pendingConflict, setPendingConflict] = useState(null)

  // ★ 重建按钮状态
  const [rebuilding, setRebuilding] = useState(false)
  const [rebuildMsg, setRebuildMsg] = useState('')
  // ★ 用户点击「不重建」后关闭提示（仅本次会话内）
  const [diagDismissed, setDiagDismissed] = useState(false)

  // ★ 存储区域：渠道项目直接用「渠道项目登记表」模板的 storage_zone_id（后端自动解析）
  // 编辑模式：保留原项目的 storage_zone_id
  // 自营项目（DynamicForm 路径）：DynamicForm 自己处理 zone

  useEffect(() => {
    if (project?.tender_folder) setTenderPreview(project.tender_folder)
    if (project?.bid_folder) setBidPreview(project.bid_folder)
  }, [project])

  // 当项目切换时，重置 dismiss 状态
  useEffect(() => {
    setDiagDismissed(false)
    setRebuildMsg('')
  }, [project?.id])

  const fetchFiles = async (projectName, folderType, creator) => {
    if (!projectName && !project?.id) return
    try {
      const payload = { folder_type: folderType }
      if (project?.id) payload.project_id = project.id
      else {
        payload.project_name = projectName
        if (creator) {
          payload.creator_username = creator.username
          payload.creator_real_name = creator.real_name
        } else if (currentUser) {
          payload.creator_username = currentUser.username
          payload.creator_real_name = currentUser.real_name
        }
      }
      const raw = await listStorageFiles(payload)
      const res = raw?.data ?? raw
      if (folderType === 'tender') setTenderFiles(res?.files || [])
      else setBidFiles(res?.files || [])
    } catch (e) {
      console.error('[fetchFiles] error:', e)
      if (folderType === 'tender') setTenderFiles([])
      else setBidFiles([])
    }
  }

  const creatorForPath = (isEdit && project?.creator) || currentUser

  useEffect(() => {
    let isSubscribed = true
    if (!form.project_name) {
      setTenderPreview(''); setBidPreview('')
      setTenderFiles([]); setBidFiles([])
      return
    }

    if (project?.tender_folder) setTenderPreview(project.tender_folder)
    if (project?.bid_folder) setBidPreview(project.bid_folder)

    const t = setTimeout(async () => {
      const p = project?.creator || currentUser
      const creatorPayload = {
        creator_username: p?.username,
        creator_real_name: p?.real_name,
      }
      const hasName = !!(form.project_name && form.project_name.trim())
      if (!hasName) {
        if (isSubscribed) {
          const placeholder = '请先填写项目名称'
          setTenderPreview(placeholder)
          setBidPreview(placeholder)
        }
        return
      }
      const salesForPreview = (form.responsible_sales || '').trim() || (currentUser?.real_name || currentUser?.username || '')
      try {
        const previewExtra = {
          source: project?.source || 'channel',
        }
        const [resTender, resBid] = await Promise.all([
          previewFileStoragePath({ project_name: form.project_name, folder_type: 'tender', responsible_sales: salesForPreview, ...creatorPayload, ...previewExtra }).catch(() => ({})),
          previewFileStoragePath({ project_name: form.project_name, folder_type: 'bid', responsible_sales: salesForPreview, ...creatorPayload, ...previewExtra }).catch(() => ({})),
        ])
        if (isSubscribed) {
          setTenderPreview((resTender?.data ?? resTender)?.tender_folder || (resTender?.data ?? resTender)?.path || '')
          setBidPreview((resBid?.data ?? resBid)?.bid_folder || (resBid?.data ?? resBid)?.path || '')
        }

        if (isSubscribed) {
          await fetchFiles(form.project_name, 'tender', p)
          await fetchFiles(form.project_name, 'bid', p)
        }
      } catch (e) {
        console.error('[useEffect] data load err:', e)
      }
    }, 300)
    return () => {
      isSubscribed = false
      clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.project_name, form.responsible_sales, project?.id, project?.tender_folder, project?.bid_folder])

  const [users, setUsers] = useState([])
  useEffect(() => {
    getUsers().then(res => {
      const list = Array.isArray(res) ? res : (res.data || [])
      setUsers(list.filter(u => u.id !== undefined))
    }).catch(() => {})
  }, [])

  const validate = () => {
    const errs = {}
    if (!form.project_name?.trim()) errs.project_name = '项目名称必填'
    if (!form.project_type) errs.project_type = '项目类型必填'
    if (form.expected_amount === '' || form.expected_amount === null || form.expected_amount === undefined) {
      errs.expected_amount = '预计金额必填'
    } else if (isNaN(parseFloat(form.expected_amount)) || parseFloat(form.expected_amount) < 0) {
      errs.expected_amount = '预计金额需为非负数字'
    }
    if (!form.partner_company?.trim()) errs.partner_company = '公司名称必填'
    if (!form.contact_person?.trim()) errs.contact_person = '联系人必填'
    if (!form.contact_info?.trim()) errs.contact_info = '联系方式必填'
    setErrors(errs)
    if (Object.keys(errs).length) {
      const firstKey = Object.keys(errs)[0]
      alert('请填写必填项（带 ★ 字段）：' + errs[firstKey])
      return false
    }
    return true
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    const data = {
      ...form,
      project_name: form.project_name.trim(),
      project_type: form.project_type,
      responsible_sales: form.responsible_sales?.trim() || '',
      project_code: form.project_code?.trim() || '',
      partner_company: form.partner_company?.trim() || '',
      owner_contact_person: form.owner_contact_person?.trim() || '',
      owner_contact_info: form.owner_contact_info?.trim() || '',
      company_address: form.company_address?.trim() || '',
      main_qualification: form.main_qualification?.trim() || '',
      legal_representative: form.legal_representative?.trim() || '',
      contact_person: form.contact_person?.trim() || '',
      contact_info: form.contact_info?.trim() || '',
      project_overview: form.project_overview?.trim() || '',
      fee_amount: form.fee_mode === 'charged' ? (parseFloat(form.fee_amount) || 0) * 10000 : null,
      expected_amount: (parseFloat(form.expected_amount) || 0),
      project_amount: (parseFloat(form.expected_amount) || 0) * 10000,
      // ★ 存储区域：渠道项目走默认老单例（后端会按 FormTemplate 自动选 zone）
      // 编辑模式不变（保留原项目的 storage_zone_id）
      // 自营项目（source='self'）从 form.storage_zone_id 取
      source: 'channel',
    }
    if (isAdmin && isEdit && project?.win_bid_status_set_at && winBidUnlocked) {
      data.win_bid_change_reason = winBidReason.trim()
      data.admin_password_verify = winBidPassword
    }
    try {
      if (isEdit) await updateProject(project.id, data)
      else await createProject(data)
      onSaved?.(); onClose?.()
    } catch (err) {
      alert(err.response?.data?.detail || '操作失败')
    }
  }

  const handleFilesPicked = async (folderType, files) => {
    if (!files || files.length === 0) return
    if (!form.project_name && !project?.project_name) {
      alert('请先填写项目名称'); return
    }
    const projectName = form.project_name || project.project_name

    let existingNames = new Set()
    try {
      const listPayload = { folder_type: folderType }
      if (project?.id) listPayload.project_id = project.id
      else {
        listPayload.project_name = projectName
        const creator = creatorForPath || currentUser
        if (creator) {
          listPayload.creator_username = creator.username
          listPayload.creator_real_name = creator.real_name
        }
      }
      const raw = await listStorageFiles(listPayload)
      const res = raw?.data ?? raw
      existingNames = new Set((res?.files || []).map(f => f.name))
    } catch (e) {
      console.error('[handleFilesPicked] list-files error:', e)
    }

    const conflicts = files.filter(f => existingNames.has(f.name))
    const nonConflicts = files.filter(f => !existingNames.has(f.name))

    if (conflicts.length === 0) {
      doUpload(folderType, files)
      return
    }

    setPendingConflict({
      folderType,
      conflicts: conflicts.map(f => ({ name: f.name, size: f.size })),
      nonConflicts,
      allFiles: files,
    })
  }

  const doUpload = async (folderType, files, overwrite = false) => {
    if (!files || files.length === 0) return
    const setter = folderType === 'tender' ? setUploadingTender : setUploadingBid
    setter(true)
    // 单文件 1GB 上限（与后端 _MAX_FILE_SIZE_DEFAULT 对齐）
    const MAX_FILE_SIZE = 1024 * 1024 * 1024
    const oversized = files.filter(f => f.size > MAX_FILE_SIZE)
    if (oversized.length) {
      alert(`以下文件超过 1GB 单文件上限，请压缩后分批上传:\n${oversized.map(f => `• ${f.name} (${(f.size/1024/1024).toFixed(1)}MB)`).join('\n')}`)
      setter(false)
      return
    }
    // 分批:每批 ≤ 3 个,避免单次 form-data 体积过大触发 413
    const BATCH_SIZE = 3
    const batches = []
    for (let i = 0; i < files.length; i += BATCH_SIZE) batches.push(files.slice(i, i + BATCH_SIZE))

    const allUploaded = []
    const allFailed = []
    const totalFiles = files.length

    try {
      for (let bi = 0; bi < batches.length; bi++) {
        const batch = batches[bi]
        const fd = new FormData()
        fd.append('folder_type', folderType)
        fd.append('project_name', form.project_name || project.project_name)
        fd.append('creator_username', creatorForPath?.username || currentUser?.username || '')
        fd.append('creator_real_name', creatorForPath?.real_name || currentUser?.real_name || '')
        if (project?.id) fd.append('project_id', String(project.id))
        fd.append('overwrite', overwrite ? 'true' : 'false')
        for (const f of batch) fd.append('files', f)

        const result = await new Promise((resolve) => {
          const xhr = new XMLHttpRequest()
          const batchStartIdx = bi * BATCH_SIZE
          xhr.upload.onprogress = (e) => {
            if (!e.lengthComputable) return
            // 当前文件进度 = 当前 batch 内已传字节 / 当前 batch 总大小
            const batchDoneBytes = e.loaded
            const batchTotal = e.total
            const batchPercent = Math.round((batchDoneBytes / batchTotal) * 100)
            // 总体进度 = (已完成的批次文件数 + 当前批次百分比) / 总文件数
            const overallPercent = Math.min(100, Math.round(
              ((batchStartIdx + batchDoneBytes / batchTotal * batch.length) / totalFiles) * 100
            ))
            const currentFile = batch[batch.length - 1]?.name || ''
            setUploadProgress(p => ({ ...p, [folderType]: {
              percent: overallPercent,
              currentFile,
              batchPercent,
              done: batchStartIdx + Math.ceil(batch.length * batchDoneBytes / batchTotal),
              total: totalFiles,
              batchIndex: bi + 1,
              batchCount: batches.length,
            }}))
          }
          xhr.onload = () => {
            try {
              const data = JSON.parse(xhr.responseText)
              resolve({ ok: xhr.status >= 200 && xhr.status < 300, data, status: xhr.status })
            } catch (_) {
              resolve({ ok: false, data: { detail: xhr.responseText || `HTTP ${xhr.status}` }, status: xhr.status })
            }
          }
          xhr.onerror = () => resolve({ ok: false, data: { detail: '网络错误' }, status: 0 })
          xhr.onabort = () => resolve({ ok: false, data: { detail: '已取消' }, status: 0 })
          xhr.open('POST', '/api/file-storage/upload')
          xhr.setRequestHeader('Authorization', 'Bearer ' + (localStorage.getItem('token') || ''))
          xhr.send(fd)
        })

        if (!result.ok) {
          const detail = result.data?.detail || `HTTP ${result.status}`
          alert(`第 ${bi+1}/${batches.length} 批上传失败: ${detail}`)
          allFailed.push({ batch: bi + 1, error: detail })
          // 413 时给出更友好提示
          if (result.status === 413) {
            alert('提示: 服务端拒绝了请求体过大(413)。\n可能原因:\n1) 单文件超过 1GB 上限\n2) Nginx / 反向代理 body 限制过小\n请检查系统部署的 client_max_body_size 配置。')
          }
          break
        } else {
          if (Array.isArray(result.data?.uploaded)) allUploaded.push(...result.data.uploaded)
          if (Array.isArray(result.data?.failed)) allFailed.push(...result.data.failed)
        }
      }

      setUploadProgress(p => ({ ...p, [folderType]: null }))
      await fetchFiles(form.project_name || project.project_name, folderType, creatorForPath)
      const okCount = allUploaded.length
      const failCount = allFailed.filter(f => !f.batch).length
      if (allFailed.filter(f => f.batch).length === 0) {
        const tip = overwrite && okCount > 0 ? `成功覆盖 ${okCount} 个文件` : `成功上传 ${okCount} 个文件`
        if (failCount > 0) {
          alert(`上传完成：成功 ${okCount}，失败 ${failCount}\n失败原因：${allFailed.filter(f => !f.batch).map(f => f.error || f.name).join('; ')}`)
        } else if (okCount > 0) {
          // 不弹 alert 避免打断,只在控制台输出
          console.log(tip)
        }
        if (okCount > 0) onFilesUploaded?.()
      }
    } catch (err) {
      alert('上传失败: ' + (err.message || '网络错误'))
      setUploadProgress(p => ({ ...p, [folderType]: null }))
    } finally {
      setter(false)
    }
  }

  const confirmOverwrite = () => {
    if (!pendingConflict) return
    const { folderType, allFiles } = pendingConflict
    setPendingConflict(null)
    const ref = folderType === 'tender' ? fileTenderRef : fileBidRef
    if (ref?.current) ref.current.value = ''
    doUpload(folderType, allFiles, true)
  }

  const cancelOverwrite = () => {
    if (!pendingConflict) return
    const { folderType, nonConflicts } = pendingConflict
    setPendingConflict(null)
    const ref = folderType === 'tender' ? fileTenderRef : fileBidRef
    if (ref?.current) ref.current.value = ''
    if (nonConflicts && nonConflicts.length > 0) {
      doUpload(folderType, nonConflicts)
    }
  }

  const makeDropHandlers = (folderType) => ({
    onDragOver: (e) => { e.preventDefault(); e.stopPropagation() },
    onDragEnter: (e) => { e.preventDefault(); e.stopPropagation() },
    onDrop: (e) => {
      e.preventDefault(); e.stopPropagation()
      handleFilesPicked(folderType, Array.from(e.dataTransfer.files))
    },
  })

  const renderDropZone = (folderType, preview, uploading, inputRef) => {
    const displayPath = stripUrlPrefix(preview)
    return (
      <div
        {...makeDropHandlers(folderType)}
        onClick={() => inputRef.current?.click()}
        className="border-2 border-dashed border-gray-300 rounded-lg px-4 py-4 cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition min-h-[96px] flex flex-col justify-center"
      >
        {displayPath && (
          <div className="text-[11px] text-gray-500 mb-2 truncate text-center" title={displayPath}>
            <span className="inline-block px-2 py-0.5 bg-blue-50 text-blue-700 rounded border border-blue-100">
              📁 {displayPath.length > 60 ? '...' + displayPath.slice(-60) : displayPath}
            </span>
          </div>
        )}
        <div className="text-center text-sm text-gray-500">
          {uploading ? (
            <div className="space-y-2">
              <div className="text-blue-600 text-sm">
                ⏳ 上传中... {uploadProgress[folderType]?.percent ?? 0}%
              </div>
              {uploadProgress[folderType] && (
                <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-blue-500 h-full transition-all duration-200"
                    style={{ width: `${uploadProgress[folderType]?.percent ?? 0}%` }}
                  />
                </div>
              )}
              {uploadProgress[folderType]?.currentFile && (
                <div className="text-[10px] text-gray-500 truncate" title={uploadProgress[folderType].currentFile}>
                  {uploadProgress[folderType].currentFile}
                </div>
              )}
              {uploadProgress[folderType]?.batchCount > 1 && (
                <div className="text-[10px] text-gray-400">
                  批次 {uploadProgress[folderType].batchIndex}/{uploadProgress[folderType].batchCount}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-1">
              <div className="text-base">📎 拖拽文件到此处</div>
              <div className="text-xs text-gray-400">或 <span className="text-blue-600">点击选择文件</span></div>
              <div className="text-[10px] text-gray-400">单文件最大 1GB，超大文件请压缩分批上传</div>
            </div>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            const list = Array.from(e.target.files)
            handleFilesPicked(folderType, list)
          }}
        />
      </div>
    )
  }

  const renderFileList = (fileList, folderType, readOnly = false) => {
    if (!fileList || fileList.length === 0) {
      return (
        <div className="mt-2 text-xs text-gray-400 text-center py-3 border border-dashed border-gray-200 rounded">
          暂无文件
        </div>
      )
    }
    return (
      <div className="mt-2 border border-gray-200 rounded-md bg-white">
        <div className="px-3 py-1.5 text-xs font-semibold text-gray-600 bg-gray-50 border-b border-gray-200 rounded-t-md flex items-center justify-between">
          <span>📚 已上传文件（共 {fileList.length} 个）</span>
          {!readOnly && (
          <button
            type="button"
            onClick={async () => {
              try {
                const p = creatorForPath
                const payload = { project_name: form.project_name || project?.project_name, folder_type: folderType }
                const existingDir = folderType === 'tender' ? project?.tender_folder : project?.bid_folder
                if (existingDir) payload.target_dir = existingDir
                if (p) { payload.creator_username = p.username; payload.creator_real_name = p.real_name }
                else if (currentUser) { payload.creator_username = currentUser.username; payload.creator_real_name = currentUser.real_name }
                const raw = await listStorageFiles(payload)
                const res = raw?.data ?? raw
                const files = res?.files || []
                alert(`[refresh] ${folderType} 返回 ${files.length} 个文件\n${files.map(f=>f.name).join('\n')}`)
                if (folderType === 'tender') setTenderFiles(files)
                else setBidFiles(files)
              } catch (e) {
                alert('refresh failed: ' + e.message)
              }
            }}
            className="text-blue-600 hover:text-blue-800 text-xs font-normal"
            title="刷新文件列表"
          >
            🔄 刷新
          </button>
          )}
        </div>
        <ul className="divide-y divide-gray-100 max-h-56 overflow-y-auto">
          {fileList.map(f => {
            const dateStr = (f.upload_time || f.mtime) ? formatTime(f.upload_time || f.mtime) : ''
            return (
              <li key={f.path} className="px-3 py-2 text-xs hover:bg-blue-50 group" title={stripUrlPrefix(f.path)}>
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate flex-1 text-gray-800 font-medium" title={f.name}>
                    📄 {f.name}
                  </span>
                  <span className="text-gray-500 flex-shrink-0">{formatSize(f.size)}</span>
                </div>
                <div className="mt-1 flex items-center gap-3 text-gray-500 text-[11px]">
                  <span className="font-medium text-blue-700">📅 {dateStr || '时间未知'}</span>
                  <span>👤 {f.uploader || f.uploader_username || '未知'}</span>
                </div>
              </li>
            )
          })}
        </ul>
      </div>
    )
  }

  // ★ 诊断面板（编辑模式 + readOnly 都显示；新建模式不显示）
  const renderDiagnosePanel = () => {
    if (!isEdit) return null
    if (!diagnoseResult) return null
    const tender = diagnoseResult.tender || {}
    const bid = diagnoseResult.bid || {}
    const tenderBad = tender.status === 'wrong' || tender.status === 'empty'
    const bidBad = bid.status === 'wrong' || bid.status === 'empty'
    const anyBad = tenderBad || bidBad
    const unknown = tender.status === 'unknown' && bid.status === 'unknown'

    if (!anyBad && !unknown) {
      return (
        <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded text-xs text-green-700">
          ✓ 存储路径正常：招标资料 + 投标文档均可访问。
        </div>
      )
    }
    if (unknown) {
      return (
        <div className="mb-3 p-3 bg-gray-50 border border-gray-200 rounded text-xs text-gray-600">
          ℹ 当前项目未关联 storage_zone，无法校验文件路径。请先在「存储区域」管理中给表单绑定一个区域。
        </div>
      )
    }
    if (diagDismissed) {
      return (
        <div className="mb-3 p-3 bg-gray-50 border border-gray-200 rounded text-xs text-gray-600">
          ⓘ 已忽略路径错误提示。如需重新检查请关闭重开对话框。
        </div>
      )
    }
    return (
      <div className="mb-3 p-3 bg-red-50 border-2 border-red-300 rounded">
        <div className="text-sm font-bold text-red-700 mb-2">
          ⚠ 存储路径错误（系统扫描到的问题）
        </div>
        <ul className="text-xs text-red-700 space-y-1 mb-3">
          {tenderBad && (
            <li>• <b>招标资料</b>：{tender.msg || '目录不可访问'}
              {project?.tender_folder && (
                <span className="ml-2 text-red-500 font-mono text-[11px]">{stripUrlPrefix(project.tender_folder)}</span>
              )}
            </li>
          )}
          {bidBad && (
            <li>• <b>投标文档</b>：{bid.msg || '目录不可访问'}
              {project?.bid_folder && (
                <span className="ml-2 text-red-500 font-mono text-[11px]">{stripUrlPrefix(project.bid_folder)}</span>
              )}
            </li>
          )}
        </ul>
        <div className="text-xs text-red-600 mb-3">
          系统不会自动修改 DB。你可以：
          <ol className="list-decimal ml-5 mt-1 space-y-0.5">
            <li>让管理员按上面显示的路径在 NAS 上手动建好对应目录（自建路径），然后点击「不重建」即可使用；</li>
            <li>或点击「重建」让系统按 DB 中保存的路径自动 MKCOL 创建子目录。</li>
          </ol>
        </div>
        <div className="flex gap-2">
          {isAdmin && project?.id && (
            <button
              type="button"
              disabled={rebuilding}
              onClick={async () => {
                if (!confirm(`确定要重建项目「${project.project_name}」的 WebDAV 目录吗？\n将按 DB 中保存的 tender_folder / bid_folder 调用 MKCOL。`)) return
                setRebuilding(true)
                setRebuildMsg('')
                try {
                  const res = await rebuildProjectFolders({ project_id: project.id })
                  const data = res?.data ?? res
                  setRebuildMsg(data?.message || '✓ 重建完成')
                  onRebuilt?.()
                } catch (e) {
                  setRebuildMsg('✗ 重建失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
                } finally {
                  setRebuilding(false)
                }
              }}
              className={`px-4 py-1.5 text-xs rounded text-white transition shadow-sm ${rebuilding ? 'bg-amber-400 cursor-wait' : 'bg-amber-600 hover:bg-amber-700'}`}
            >
              {rebuilding ? '⏳ 重建中...' : '🔧 重建'}
            </button>
          )}
          <button
            type="button"
            onClick={() => setDiagDismissed(true)}
            className="px-4 py-1.5 text-xs rounded border border-gray-400 text-gray-700 hover:bg-gray-100 transition"
          >
            不重建（我已自建路径）
          </button>
        </div>
        {rebuildMsg && (
          <div className="mt-2 text-xs text-red-700 font-medium">{rebuildMsg}</div>
        )}
      </div>
    )
  }

  return (
    <div className="w-full bg-white">
      <div className="flex items-center justify-between pb-4 mb-4 border-b">
        <h3 className="text-xl font-bold text-gray-800">
          {readOnly ? '查看项目详情' :
            (withdrawMode ? '撤回修改' :
              (isEdit ? (isAdmin ? '编辑项目（管理员模式）' : '编辑项目（仅上传文件）') : '新建项目'))}
        </h3>
        {(isEdit || readOnly) && (
          <span className="text-xs px-2 py-1 rounded border"
            style={{
              color: readOnly ? '#6b7280' : (withdrawMode ? '#7c3aed' : (isAdmin ? '#059669' : '#d97706')),
              background: readOnly ? '#f3f4f6' : (withdrawMode ? '#f5f3ff' : (isAdmin ? '#ecfdf5' : '#fffbeb')),
              borderColor: readOnly ? '#d1d5db' : (withdrawMode ? '#ddd6fe' : (isAdmin ? '#a7f3d0' : '#fde68a'))
            }}>
            {readOnly ? '📖 只读查看模式' :
              (withdrawMode ? '🔄 项目已撤回，可修改除项目名称外的所有字段' :
                (isAdmin ? '🛡️ 管理员权限：可修改中标状态及上传文件' : '🔒 项目已建，字段锁定，仅可上传/查看文件'))}
          </span>
        )}
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
      </div>

      <form onSubmit={handleSubmit}>

        {isEdit && !readOnly && (
          <div className="mb-5 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="text-sm font-bold text-blue-800 mb-3 flex items-center gap-2">
              📋 项目信息
              {isAdmin && <span className="text-xs text-green-600 bg-green-100 px-2 py-0.5 rounded-full">管理员可修改中标状态</span>}
            </div>
            <div className="grid grid-cols-3 gap-x-8 gap-y-2 text-sm">
              <div><span className="text-gray-500">项目名称：</span><span className="text-gray-800">{form.project_name}</span></div>
              <div><span className="text-gray-500">项目类型：</span><span className="text-gray-800">{form.project_type}</span></div>
              <div><span className="text-gray-500">{lblAmount}：</span><span className="text-gray-800">{form.expected_amount} 万元</span></div>
              <div><span className="text-gray-500">{lblCompany}：</span><span className="text-gray-800">{form.partner_company}</span></div>
              <div><span className="text-gray-500">{lblContact}：</span><span className="text-gray-800">{form.contact_person}</span></div>
              <div><span className="text-gray-500">{lblPhone}：</span><span className="text-gray-800">{form.contact_info}</span></div>
            </div>

            {isAdmin && (
              <div className="mt-3 pt-3 border-t border-blue-200">
                <div className="flex items-center gap-3 flex-wrap">
                  <label className="text-sm font-medium text-gray-700">
                    中标状态{project?.win_bid_status_set_at ? (winBidUnlocked ? '（已解锁，可再次修改）' : '（已锁定）') : '（可修改）'}：
                  </label>
                  {project?.win_bid_status_set_at && !winBidUnlocked ? (
                    <>
                      <span className="text-sm font-semibold text-gray-700">
                        {form.win_bid_status === 'in_progress' ? '进行中' : form.win_bid_status === 'yes' ? '中标' : '未中标'}
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          setWinBidReason('')
                          setWinBidPassword('')
                          setWinBidModalError('')
                          setShowWinBidModal(true)
                        }}
                        className="px-3 py-1 text-xs bg-amber-500 hover:bg-amber-600 text-white rounded-md transition shadow-sm"
                      >
                        🔓 修改中标状态
                      </button>
                    </>
                  ) : (
                    <select
                      value={form.win_bid_status}
                      onChange={e => setForm(f => ({ ...f, win_bid_status: e.target.value }))}
                      className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-green-200 focus:border-green-500"
                    >
                      <option value="in_progress">进行中</option>
                      <option value="yes">中标</option>
                      <option value="no">未中标</option>
                    </select>
                  )}
                  <span className="text-xs text-gray-400">
                    {project?.win_bid_status_set_at
                      ? `首次设置于 ${project.win_bid_status_set_at?.slice(0, 16)?.replace('T', ' ')}${winBidUnlocked ? '（已通过验证解锁）' : '（再次修改需验证密码）'}`
                      : '首次修改后保存生效，后续修改需填写理由并验证密码'}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {readOnly && (
          <>
            <div className="mb-5">
              <div className="bg-gray-100 border-l-4 border-gray-400 px-3 py-1.5 mb-3">
                <span className="text-sm font-bold text-gray-700">项目基本信息</span>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">项目名称</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.project_name || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">责任销售</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.responsible_sales || '（未指定，使用创建者姓名）'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">项目编号</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.project_code || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">项目类型</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.project_type || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">{lblAmount}（万元）</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.expected_amount || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">招标时间</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.tender_time || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">投标时间</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.bid_time || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">业主联系人</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.owner_contact_person || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">业主联系方式</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.owner_contact_info || '-'}</div>
                </div>
              </div>
            </div>

            <div className="mb-5">
              <div className="bg-gray-100 border-l-4 border-gray-400 px-3 py-1.5 mb-3">
                <span className="text-sm font-bold text-gray-700">合作基本情况</span>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">{lblCompany}</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.partner_company || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">公司地址</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.company_address || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">主要资质</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.main_qualification || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">法定代表</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.legal_representative || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">{lblContact}</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.contact_person || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">{lblPhone}</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.contact_info || '-'}</div>
                </div>
              </div>
            </div>

            <div className="mb-5">
              <div className="bg-gray-100 border-l-4 border-gray-400 px-3 py-1.5 mb-3">
                <span className="text-sm font-bold text-gray-700">合作模式与费用</span>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">合作模式</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.cooperation_mode === 'long_term' ? '长期合作' : '短期合作'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">费用模式</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.fee_mode === 'mutual' ? '互免' : '收费'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">费用金额（元）</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.fee_amount || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">是否SM</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.is_sm === 'yes' ? '是' : '否'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">中标状态</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">
                    {form.win_bid_status === 'in_progress' ? '进行中' : form.win_bid_status === 'yes' ? '中标' : '未中标'}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {!readOnly && (!isEdit || withdrawMode) && (
          <>
            <div className="mb-5">
              <div className={`${withdrawMode ? 'bg-purple-50 border-purple-500' : 'bg-green-50 border-green-500'} border-l-4 px-3 py-1.5 mb-3`}>
                <span className={`text-sm font-bold ${withdrawMode ? 'text-purple-700' : 'text-green-700'}`}>项目基本信息</span>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    项目名称<Star />
                    {withdrawMode && <span className="ml-2 text-xs text-gray-400">（撤回后不可修改）</span>}
                  </label>
                  {withdrawMode ? (
                    <div className="px-3 py-2 bg-gray-100 border border-gray-200 rounded text-gray-700 cursor-not-allowed">
                      {form.project_name}
                    </div>
                  ) : (
                    <input type="text" value={form.project_name}
                      onChange={e => setForm(f => ({ ...f, project_name: e.target.value }))}
                      placeholder="请输入项目名称"
                      className={errors.project_name ? inputErrCls : inputCls} />
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    责任销售
                    {withdrawMode && <span className="ml-2 text-xs text-gray-400">（撤回后可修改）</span>}
                  </label>
                  <input type="text" value={form.responsible_sales || ''}
                    onChange={e => setForm(f => ({ ...f, responsible_sales: e.target.value }))}
                    placeholder="如由销售本人建立，此处可不填"
                    className={errors.responsible_sales ? inputErrCls : inputCls} />
                  {errors.responsible_sales && <p className="text-xs text-red-500 mt-1">{errors.responsible_sales}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">项目编号</label>
                  <input type="text" value={form.project_code}
                    onChange={e => setForm(f => ({ ...f, project_code: e.target.value }))}
                    placeholder="选填"
                    className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">项目类型<Star /></label>
                  <select value={form.project_type}
                    onChange={e => setForm(f => ({ ...f, project_type: e.target.value }))}
                    className={errors.project_type ? inputErrCls : inputCls}>
                    {PROJECT_TYPE_OPTIONS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{lblAmount}（万元）<Star /></label>
                  <input type="number" step="0.01" value={form.expected_amount}
                    onChange={e => setForm(f => ({ ...f, expected_amount: e.target.value }))}
                    placeholder="0.00"
                    className={errors.expected_amount ? inputErrCls : inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">招标时间</label>
                  <input type="date" value={form.tender_time || ''}
                    onChange={e => setForm(f => ({ ...f, tender_time: e.target.value }))}
                    className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">投标时间</label>
                  <input type="date" value={form.bid_time || ''}
                    onChange={e => setForm(f => ({ ...f, bid_time: e.target.value }))}
                    className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">业主联系人</label>
                  <input type="text" value={form.owner_contact_person}
                    onChange={e => setForm(f => ({ ...f, owner_contact_person: e.target.value }))}
                    placeholder="选填"
                    className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">联系方式</label>
                  <input type="text" value={form.owner_contact_info}
                    onChange={e => setForm(f => ({ ...f, owner_contact_info: e.target.value }))}
                    placeholder="选填"
                    className={inputCls} />
                </div>
              </div>
            </div>

            <div className="mb-5">
              <div className="bg-green-50 border-l-4 border-green-500 px-3 py-1.5 mb-3">
                <span className="text-sm font-bold text-green-700">合作基本情况</span>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{lblCompany}<Star /></label>
                  <input type="text" value={form.partner_company}
                    onChange={e => setForm(f => ({ ...f, partner_company: e.target.value }))}
                    placeholder="请输入公司名称"
                    className={errors.partner_company ? inputErrCls : inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">公司地址</label>
                  <input type="text" value={form.company_address}
                    onChange={e => setForm(f => ({ ...f, company_address: e.target.value }))}
                    placeholder="选填"
                    className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">主要资质</label>
                  <input type="text" value={form.main_qualification}
                    onChange={e => setForm(f => ({ ...f, main_qualification: e.target.value }))}
                    placeholder="选填"
                    className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">法定代表</label>
                  <input type="text" value={form.legal_representative}
                    onChange={e => setForm(f => ({ ...f, legal_representative: e.target.value }))}
                    placeholder="选填"
                    className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{lblContact}<Star /></label>
                  <input type="text" value={form.contact_person}
                    onChange={e => setForm(f => ({ ...f, contact_person: e.target.value }))}
                    placeholder="请输入联系人"
                    className={errors.contact_person ? inputErrCls : inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{lblPhone}<Star /></label>
                  <input type="text" value={form.contact_info}
                    onChange={e => setForm(f => ({ ...f, contact_info: e.target.value }))}
                    placeholder="请输入联系方式"
                    className={errors.contact_info ? inputErrCls : inputCls} />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">合作模式</label>
                  <select value={form.cooperation_mode}
                    onChange={e => setForm(f => ({ ...f, cooperation_mode: e.target.value }))}
                    className={inputCls}>
                    <option value="long_term">长期合作</option>
                    <option value="short_term">短期合作</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">费用模式</label>
                  <select value={form.fee_mode}
                    onChange={e => setForm(f => ({ ...f, fee_mode: e.target.value }))}
                    className={inputCls}>
                    <option value="mutual">互免</option>
                    <option value="charged">收费</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">中标状态</label>
                  <select value={form.win_bid_status}
                    onChange={e => setForm(f => ({ ...f, win_bid_status: e.target.value }))}
                    className={inputCls}>
                    <option value="in_progress">进行中</option>
                    <option value="yes">中标</option>
                    <option value="no">未中标</option>
                  </select>
                </div>

                {form.fee_mode === 'charged' && (
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">费用金额（元）</label>
                    <input type="number" step="0.01" value={form.fee_amount}
                      onChange={e => setForm(f => ({ ...f, fee_amount: e.target.value }))}
                      className={inputCls} />
                  </div>
                )}
              </div>
            </div>

            <div className="mb-5">
              <div className="bg-green-50 border-l-4 border-green-500 px-3 py-1.5 mb-3">
                <span className="text-sm font-bold text-green-700">项目基本情况</span>
              </div>
              <div>
                <textarea value={form.project_overview}
                  onChange={e => setForm(f => ({ ...f, project_overview: e.target.value }))}
                  rows={5}
                  placeholder="选填"
                  className={inputCls} />
              </div>
            </div>
          </>
        )}

        {/* 区域 4: 文件管理（编辑+新建显示完整上传；查看模式只显示已有文件，不允许上传/删除） */}
        <div className="mb-5">
          <div className="bg-green-50 border-l-4 border-green-500 px-3 py-1.5 mb-3 flex items-center justify-between">
            <span className="text-sm font-bold text-green-700">文件管理</span>
            {/* 诊断行内小徽章（编辑模式） */}
            {!readOnly && isEdit && diagnoseResult && (() => {
              const tender = diagnoseResult.tender || {}
              const bid = diagnoseResult.bid || {}
              const tenderBad = tender.status === 'wrong' || tender.status === 'empty'
              const bidBad = bid.status === 'wrong' || bid.status === 'empty'
              if (!tenderBad && !bidBad) {
                return <span className="text-xs text-green-700">✓ 路径正常</span>
              }
              return <span className="text-xs text-red-700 font-semibold">⚠ 路径异常（详见下方）</span>
            })()}
          </div>

          {/* ★ 诊断面板：仅编辑模式渲染（重建/不重建按钮） */}
          {!readOnly && renderDiagnosePanel()}

          <div className="grid grid-cols-2 gap-x-8 gap-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                招标资料{readOnly ? '' : '上传'}
              </label>
              {!readOnly && renderDropZone('tender', tenderPreview, uploadingTender, fileTenderRef)}
              {renderFileList(tenderFiles, 'tender', readOnly)}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                投标文档及其他资料{readOnly ? '' : '上传'}
              </label>
              {!readOnly && renderDropZone('bid', bidPreview, uploadingBid, fileBidRef)}
              {renderFileList(bidFiles, 'bid', readOnly)}
            </div>
          </div>
        </div>

        {(!isEdit || withdrawMode) && (
          <div className="mb-5">
            <div className={`${withdrawMode ? 'bg-purple-50 border-purple-500' : 'bg-green-50 border-green-500'} border-l-4 px-3 py-1.5 mb-3`}>
              <span className={`text-sm font-bold ${withdrawMode ? 'text-purple-700' : 'text-green-700'}`}>审批人</span>
              <span className="text-xs text-gray-500 ml-2">（系统根据用户管理中的设置自动分配）</span>
            </div>
            <div>
              <input
                type="text"
                value={
                  project?.approver?.real_name
                    ? `${project.approver.real_name} (${project.approver.username})`
                    : (() => {
                        const approver = users.find(u => u.id === currentUser?.parent_id)
                        return approver
                          ? `${approver.real_name} (${approver.username})`
                          : '系统管理员'
                      })()
                }
                readOnly
                className="w-full border border-gray-200 rounded-md px-3 py-2 bg-gray-50 text-gray-700"
              />
            </div>
          </div>
        )}

        <div className="flex justify-between gap-3 pt-5 border-t mt-6">
          {!readOnly && withdrawMode && onDelete && (
            <button type="button" onClick={async () => {
              if (!confirm('确定删除此项目吗？\n注：NAS 上的项目目录和文件不会被删除。')) return
              try {
                await onDelete()
              } catch (err) {
                alert('删除失败：' + (err?.message || '未知错误'))
              }
            }} className="px-6 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition shadow-sm">
              删除项目
            </button>
          )}
          <div className="flex gap-3 ml-auto">
            <button type="button" onClick={onClose}
              className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition">
              {readOnly ? '关闭' : (withdrawMode ? '取消' : (isEdit ? '关闭' : '取消'))}
            </button>
            {!readOnly && (withdrawMode ? (
              <button type="submit"
                className="px-6 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition shadow-sm">
                继续编辑（保存修改）
              </button>
            ) : isEdit ? (
              <button type="submit"
                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition shadow-sm">
                完成
              </button>
            ) : (
              <button type="submit"
                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition shadow-sm">
                保存
              </button>
            ))}
          </div>
        </div>
      </form>

      {pendingConflict && (
        <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4"
             onClick={(e) => { if (e.target === e.currentTarget) cancelOverwrite() }}>
          <div className="bg-white rounded-lg shadow-2xl max-w-md w-full p-5">
            <div className="text-base font-bold text-gray-800 mb-3">
              ⚠️ 检测到 {pendingConflict.conflicts.length} 个同名文件已存在
            </div>
            <ul className="max-h-48 overflow-y-auto border border-amber-200 bg-amber-50 rounded p-3 text-xs space-y-1">
              {pendingConflict.conflicts.map((c, i) => (
                <li key={i} className="flex justify-between text-amber-800">
                  <span className="truncate">• {c.name}</span>
                  <span className="ml-2 text-gray-500">{formatSize(c.size)}</span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-gray-500 mt-3">
              点击「确认覆盖」将覆盖这些同名文件，其余 {pendingConflict.nonConflicts.length} 个不会冲突的文件将自动上传。
              点击「取消」则仅上传非冲突文件。
            </p>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={cancelOverwrite}
                className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50">
                取消
              </button>
              <button onClick={confirmOverwrite}
                className="px-4 py-2 bg-amber-600 text-white rounded hover:bg-amber-700">
                确认覆盖
              </button>
            </div>
          </div>
        </div>
      )}

      {showWinBidModal && (
        <div className="fixed inset-0 z-[70] bg-black/50 flex items-center justify-center p-4"
             onClick={(e) => { if (e.target === e.currentTarget) setShowWinBidModal(false) }}>
          <div className="bg-white rounded-lg shadow-2xl max-w-md w-full p-6">
            <div className="text-lg font-bold text-gray-800 mb-1 flex items-center gap-2">
              🔓 解锁中标状态修改
            </div>
            <p className="text-xs text-gray-500 mb-4">
              项目「{project?.project_name}」的中标状态已设置过，再次修改需填写理由并验证管理员密码。
            </p>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                修改理由<span className="text-red-500 ml-1">*</span>
              </label>
              <textarea
                value={winBidReason}
                onChange={e => setWinBidReason(e.target.value)}
                placeholder="请说明修改中标状态的原因（如：客户变更结果、录入错误等）"
                rows={3}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-amber-200 focus:border-amber-500 resize-none"
              />
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                管理员密码<span className="text-red-500 ml-1">*</span>
              </label>
              <input
                type="password"
                value={winBidPassword}
                onChange={e => setWinBidPassword(e.target.value)}
                placeholder="请输入您的登录密码进行身份验证"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-amber-200 focus:border-amber-500"
              />
            </div>

            {winBidModalError && (
              <div className="mb-4 text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
                {winBidModalError}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowWinBidModal(false)}
                className="px-5 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => {
                  if (!winBidReason.trim()) {
                    setWinBidModalError('请填写修改理由')
                    return
                  }
                  if (!winBidPassword) {
                    setWinBidModalError('请输入管理员密码')
                    return
                  }
                  setWinBidModalError('')
                  setWinBidUnlocked(true)
                  setShowWinBidModal(false)
                }}
                className="px-5 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 transition shadow-sm"
              >
                确认解锁
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
