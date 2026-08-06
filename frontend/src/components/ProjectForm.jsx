import { useState, useEffect, useRef } from 'react'
import { createProject, updateProject, getUsers, previewFileStoragePath, listStorageFiles } from '../api'
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

// 去掉 https://host:port/ 或 http://host:port/ 前缀，只保留后面的路径部分
function stripUrlPrefix(url) {
  if (!url) return ''
  return url.replace(/^https?:\/\/[^/]+\/+/, '')
}

export default function ProjectForm({ project, onClose, onSaved, readOnly = false }) {
  const { user: currentUser } = useAuthStore()
  const isEdit = !!project
  const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'important_admin'
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
    approver_id: initial('approver_id') || '',
  })

  const [errors, setErrors] = useState({})

  const [tenderPreview, setTenderPreview] = useState('')
  const [bidPreview, setBidPreview] = useState('')
  const [uploadingTender, setUploadingTender] = useState(false)
  const [uploadingBid, setUploadingBid] = useState(false)

  // 文件列表
  const [tenderFiles, setTenderFiles] = useState([])
  const [bidFiles, setBidFiles] = useState([])
  // 重名覆盖确认
  const [pendingConflict, setPendingConflict] = useState(null) // { folderType, files, existingNames }
  const [pendingResolve, setPendingResolve] = useState(null) // Promise resolver

  useEffect(() => {
    if (project?.tender_folder) setTenderPreview(project.tender_folder)
    if (project?.bid_folder) setBidPreview(project.bid_folder)
  }, [project])

  // 拉取指定子目录下的文件列表（后端按 project_id 查真实存盘 folder）
  const fetchFiles = async (projectName, folderType, creator) => {
    if (!projectName && !project?.id) return
    try {
      const payload = {
        folder_type: folderType,
      }
      if (project?.id) payload.project_id = project.id
      else {
        // 新建项目（还没 id）：回退到 project_name + creator 拼装
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

  // 决定路径/列表用的"创建者"
  // 编辑模式：优先用 project.creator（后端 list 接口会返回）；如果缺失则降级用当前用户
  const creatorForPath = (isEdit && project?.creator) || currentUser

  // 统一的数据获取与刷新逻辑：监听核心依赖变化，避免并发请求竞争
  useEffect(() => {
    let isSubscribed = true
    if (!form.project_name) {
      setTenderPreview(''); setBidPreview('')
      setTenderFiles([]); setBidFiles([])
      return
    }

    // 同步设置初始预览路径
    if (project?.tender_folder) setTenderPreview(project.tender_folder)
    if (project?.bid_folder) setBidPreview(project.bid_folder)

    const t = setTimeout(async () => {
      const p = project?.creator || currentUser
      const creatorPayload = {
        creator_username: p?.username,
        creator_real_name: p?.real_name,
      }
      try {
        // 1. 获取预览路径
        const [resTender, resBid] = await Promise.all([
          previewFileStoragePath({ project_name: form.project_name, folder_type: 'tender', ...creatorPayload }).catch(() => ({})),
          previewFileStoragePath({ project_name: form.project_name, folder_type: 'bid', ...creatorPayload }).catch(() => ({})),
        ])
        if (isSubscribed) {
          setTenderPreview((resTender?.data ?? resTender)?.tender_folder || (resTender?.data ?? resTender)?.path || '')
          setBidPreview((resBid?.data ?? resBid)?.bid_folder || (resBid?.data ?? resBid)?.path || '')
        }

        // 2. 串行拉取文件列表，确保不会发生并发覆盖
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
  }, [form.project_name, project?.id, project?.tender_folder, project?.bid_folder])

  const [users, setUsers] = useState([])
  useEffect(() => {
    getUsers().then(res => {
      const list = Array.isArray(res) ? res : (res.data || [])
      // 后端已按角色返回候选审批人（上级链 + 系统管理员），这里不再过滤角色
      // 但需要排除自己（不能选自己为审批人）
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
    if (!form.approver_id) errs.approver_id = '审批人必填'
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
      approver_id: form.approver_id ? parseInt(form.approver_id) : null,
    }
    try {
      if (isEdit) await updateProject(project.id, data)
      else await createProject(data)
      onSaved?.(); onClose?.()
    } catch (err) {
      alert(err.response?.data?.detail || '操作失败')
    }
  }

  // 拦截选中：先做重名校验，弹出确认后才真正上传
  // 选择文件后：先向服务器实时查已有文件 → 再决定是否弹覆盖确认
  const handleFilesPicked = async (folderType, files) => {
    if (!files || files.length === 0) return
    if (!form.project_name && !project?.project_name) {
      alert('请先填写项目名称'); return
    }
    const projectName = form.project_name || project.project_name

    // 服务器实时查询已有文件（不再用前端 state）
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

  // 真正执行上传（被 handleFilesPicked 与 Modal 确认后调用）
  const doUpload = async (folderType, files, overwrite = false) => {
    if (!files || files.length === 0) return
    const fd = new FormData()
    fd.append('folder_type', folderType)
    fd.append('project_name', form.project_name || project.project_name)
    fd.append('creator_username', creatorForPath?.username || currentUser?.username || '')
    fd.append('creator_real_name', creatorForPath?.real_name || currentUser?.real_name || '')
    if (project?.id) fd.append('project_id', String(project.id))
    fd.append('overwrite', overwrite ? 'true' : 'false')
    for (const f of files) fd.append('files', f)
    const setter = folderType === 'tender' ? setUploadingTender : setUploadingBid
    setter(true)
    try {
      const res = await fetch('/api/file-storage/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
        body: fd,
      })
      const data = await res.json()
      if (!res.ok) {
        alert('上传失败: ' + (data.detail || res.status))
        return
      }
      await fetchFiles(form.project_name || project.project_name, folderType, creatorForPath)
      // 上传结果提示：成功 / 部分失败 / 完全失败 三种情况
      const okCount = data.uploaded?.length || 0
      const failCount = data.failed?.length || 0
      if (failCount === 0) {
        const tip = overwrite && okCount > 0 ? `成功覆盖 ${okCount} 个文件` : `成功上传 ${okCount} 个文件`
        alert(tip)
      } else {
        alert(`上传完成：成功 ${okCount}，失败 ${failCount}\n失败原因：${data.failed.map(f => f.error || f.name).join('; ')}`)
      }
    } catch (err) {
      alert('上传失败: ' + (err.message || '网络错误'))
    } finally {
      setter(false)
    }
  }

  // Modal 中点击"确认覆盖"——上传全部（含冲突）并 overwrite=true
  const confirmOverwrite = () => {
    if (!pendingConflict) return
    const { folderType, allFiles } = pendingConflict
    setPendingConflict(null)
    const ref = folderType === 'tender' ? fileTenderRef : fileBidRef
    if (ref?.current) ref.current.value = ''
    doUpload(folderType, allFiles, true)
  }

  // Modal 中点击"取消"——仅上传非冲突文件
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
          <span className="text-blue-600">⏳ 上传中...</span>
        ) : (
          <div className="space-y-1">
            <div className="text-base">📎 拖拽文件到此处</div>
            <div className="text-xs text-gray-400">或 <span className="text-blue-600">点击选择文件</span></div>
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
          // 不要在这里清空 value，留给 confirm/cancel 处理，避免覆盖弹窗还没出现就被清掉
          handleFilesPicked(folderType, list)
        }}
      />
    </div>
    )
  }

  // 文件列表（含详细资料：上传者/时间/大小/完整路径）
  const renderFileList = (fileList, folderType) => {
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

  return (
    <div className="w-[1100px] max-w-[95vw] bg-white">
      {/* 顶部标题栏 */}
      <div className="flex items-center justify-between px-8 py-5 border-b bg-gradient-to-r from-blue-50 to-white">
        <h3 className="text-xl font-bold text-gray-800">
          {readOnly ? '查看项目详情' : 
            (isEdit ? (isAdmin ? '编辑项目（管理员模式）' : '编辑项目（仅上传文件）') : '新建项目')}
        </h3>
        {(isEdit || readOnly) && (
          <span className="text-xs px-2 py-1 rounded border"
            style={{
              color: readOnly ? '#6b7280' : (isAdmin ? '#059669' : '#d97706'),
              background: readOnly ? '#f3f4f6' : (isAdmin ? '#ecfdf5' : '#fffbeb'),
              borderColor: readOnly ? '#d1d5db' : (isAdmin ? '#a7f3d0' : '#fde68a')
            }}>
            {readOnly ? '📖 只读查看模式' : 
              (isAdmin ? '🛡️ 管理员权限：可修改中标状态及上传文件' : '🔒 项目已建，字段锁定，仅可上传/查看文件')}
          </span>
        )}
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
      </div>

      <form onSubmit={handleSubmit} className="px-8 py-6">

        {/* 编辑模式：展示项目摘要 + 文件管理 */}
        {isEdit && (
          <div className="mb-5 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="text-sm font-bold text-blue-800 mb-3 flex items-center gap-2">
              📋 项目信息
              {isAdmin && <span className="text-xs text-green-600 bg-green-100 px-2 py-0.5 rounded-full">管理员可修改中标状态</span>}
            </div>
            <div className="grid grid-cols-3 gap-x-8 gap-y-2 text-sm">
              <div><span className="text-gray-500">项目名称：</span><span className="text-gray-800">{form.project_name}</span></div>
              <div><span className="text-gray-500">项目类型：</span><span className="text-gray-800">{form.project_type}</span></div>
              <div><span className="text-gray-500">预计金额：</span><span className="text-gray-800">{form.expected_amount} 万元</span></div>
              <div><span className="text-gray-500">合作公司：</span><span className="text-gray-800">{form.partner_company}</span></div>
              <div><span className="text-gray-500">联系人：</span><span className="text-gray-800">{form.contact_person}</span></div>
              <div><span className="text-gray-500">联系方式：</span><span className="text-gray-800">{form.contact_info}</span></div>
            </div>
            
            {/* 管理员可修改中标状态 */}
            {isAdmin && (
              <div className="mt-3 pt-3 border-t border-blue-200">
                <div className="flex items-center gap-3">
                  <label className="text-sm font-medium text-gray-700">中标状态（可修改）：</label>
                  <select 
                    value={form.win_bid_status}
                    onChange={e => setForm(f => ({ ...f, win_bid_status: e.target.value }))}
                    className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-green-200 focus:border-green-500"
                  >
                    <option value="in_progress">进行中</option>
                    <option value="yes">中标</option>
                    <option value="no">未中标</option>
                  </select>
                  <span className="text-xs text-gray-400">修改后保存生效</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 只读查看模式：显示所有字段 */}
        {readOnly && (
          <>
            {/* 区域 1: 项目基本信息 */}
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
                  <label className="block text-sm font-medium text-gray-500 mb-1">项目编号</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.project_code || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">项目类型</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.project_type || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">预计金额（万元）</label>
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

            {/* 区域 2: 合作基本情况 */}
            <div className="mb-5">
              <div className="bg-gray-100 border-l-4 border-gray-400 px-3 py-1.5 mb-3">
                <span className="text-sm font-bold text-gray-700">合作基本情况</span>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">公司名称</label>
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
                  <label className="block text-sm font-medium text-gray-500 mb-1">联系人</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.contact_person || '-'}</div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">联系方式</label>
                  <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded text-gray-800">{form.contact_info || '-'}</div>
                </div>
              </div>
            </div>

            {/* 区域 3: 合作模式与费用 */}
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

        {/* 新建模式表单 */}
        {!isEdit && !readOnly && (
          <>
            {/* 区域 1: 项目基本信息 */}
            <div className="mb-5">
              <div className="bg-green-50 border-l-4 border-green-500 px-3 py-1.5 mb-3">
                <span className="text-sm font-bold text-green-700">项目基本信息</span>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">项目名称<Star /></label>
                  <input type="text" value={form.project_name}
                    onChange={e => setForm(f => ({ ...f, project_name: e.target.value }))}
                    placeholder="请输入项目名称"
                    className={errors.project_name ? inputErrCls : inputCls} />
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">预计金额（万元）<Star /></label>
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

            {/* 区域 2: 合作基本情况 */}
            <div className="mb-5">
              <div className="bg-green-50 border-l-4 border-green-500 px-3 py-1.5 mb-3">
                <span className="text-sm font-bold text-green-700">合作基本情况</span>
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">公司名称<Star /></label>
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">联系人<Star /></label>
                  <input type="text" value={form.contact_person}
                    onChange={e => setForm(f => ({ ...f, contact_person: e.target.value }))}
                    placeholder="请输入联系人"
                    className={errors.contact_person ? inputErrCls : inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">联系方式<Star /></label>
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

            {/* 区域 3: 项目基本情况 */}
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

        {/* 区域 4: 文件管理（编辑+新建都显示） */}
        <div className="mb-5">
          <div className="bg-green-50 border-l-4 border-green-500 px-3 py-1.5 mb-3">
            <span className="text-sm font-bold text-green-700">文件管理</span>
          </div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">招标资料上传</label>
              {renderDropZone('tender', tenderPreview, uploadingTender, fileTenderRef)}
              {renderFileList(tenderFiles, 'tender')}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">投标文档及其他资料上传</label>
              {renderDropZone('bid', bidPreview, uploadingBid, fileBidRef)}
              {renderFileList(bidFiles, 'bid')}
            </div>
          </div>
        </div>

        {/* 区域 5: 审批人（仅新建） */}
        {!isEdit && (
          <div className="mb-5">
            <div className="bg-green-50 border-l-4 border-green-500 px-3 py-1.5 mb-3">
              <span className="text-sm font-bold text-green-700">审批人<Star /></span>
            </div>
            <div>
              <select value={form.approver_id}
                onChange={e => setForm(f => ({ ...f, approver_id: e.target.value }))}
                className={errors.approver_id ? inputErrCls : inputCls}>
                <option value="">请选择审批人</option>
                {users.map(u => (
                  <option key={u.id} value={u.id}>
                    {u.real_name} ({u.username}) - {u.role === 'admin' ? '系统管理员' : u.role === 'important_admin' ? '重要管理员' : u.role === 'important' ? '重要账号' : '普通账号'}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* 底部按钮 */}
        <div className="flex justify-end gap-3 pt-5 border-t mt-6">
          <button type="button" onClick={onClose}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition">
            {readOnly ? '关闭' : (isEdit ? '关闭' : '取消')}
          </button>
          {!readOnly && (isEdit ? (
            <button type="button" onClick={onClose}
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
      </form>

      {/* 重名覆盖确认弹窗（替代浏览器原生的 window.confirm） */}
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
    </div>
  )
}
