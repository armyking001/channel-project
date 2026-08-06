import { useState, useEffect, useRef } from 'react'
import {
  getFileStorageConfig, updateFileStorageConfig,
  testFileStorageConnection,
  previewFileStoragePath, getProjects,
} from '../api'

export default function FileStorage() {
  const [cfg, setCfg] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [msg, setMsg] = useState(null)

  // 表单
  const [mode, setMode] = useState('local')
  const [localPath, setLocalPath] = useState('')
  const [webdavUrl, setWebdavUrl] = useState('')
  const [webdavPort, setWebdavPort] = useState('')
  const [webdavUseSsl, setWebdavUseSsl] = useState(true)
  const [webdavUsername, setWebdavUsername] = useState('')
  const [webdavPassword, setWebdavPassword] = useState('')
  const [webdavBasePath, setWebdavBasePath] = useState('')
  const [template, setTemplate] = useState('{real_name}+{project_name}+{date}')

  // 缺省配置常量（一键填充 NAS 模板）
  // 注意：这些只是 UI 提示用占位符（不是凭据），实际密码由用户在表单中输入
  const DEFAULT_WEBDAV = {
    url: '',       // 请填写 NAS 地址，如 192.168.1.100
    port: '5006',  // WebDAV 默认端口
    useSsl: true,
    basePath: '/',  // 远程根路径，请按实际 NAS 配置修改
    username: '',  // NAS 登录账号
  }

  // 拖拽上传区
  const [projectName, setProjectName] = useState('')
  const [folderType, setFolderType] = useState('tender')
  const [previewPath, setPreviewPath] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadLog, setUploadLog] = useState([])
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)
  const [existingProjects, setExistingProjects] = useState([])

  useEffect(() => {
    load()
    getProjects().then(r => {
      const list = Array.isArray(r.data) ? r.data : (Array.isArray(r) ? r : [])
      setExistingProjects(list)
    }).catch(() => {})
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const res = await getFileStorageConfig()
      setCfg(res.data)
      setMode(res.data.mode)
      setLocalPath(res.data.local_path || '')
      setWebdavUrl(res.data.webdav_url || '')
      setWebdavPort(res.data.webdav_port ? String(res.data.webdav_port) : '')
      setWebdavUseSsl(res.data.webdav_use_ssl !== false)
      setWebdavUsername(res.data.webdav_username || '')
      setWebdavPassword(res.data.webdav_password ? '******' : '')
      setWebdavBasePath(res.data.webdav_base_path || '')
      setTemplate(res.data.template || '{real_name}+{project_name}+{date}')
    } catch (e) {
      setMsg({ type: 'error', text: '加载配置失败: ' + (e.response?.data?.detail || e.message) })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setMsg(null)
    try {
      const data = {
        mode,
        local_path: localPath || null,
        webdav_url: webdavUrl || null,
        webdav_port: webdavPort ? parseInt(webdavPort, 10) : null,
        webdav_use_ssl: webdavUseSsl,
        webdav_username: webdavUsername || null,
        webdav_password: webdavPassword || null,
        webdav_base_path: webdavBasePath || null,
        template: template || '{real_name}+{project_name}+{date}',
      }
      const res = await updateFileStorageConfig(data)
      setCfg(res.data)
      setMsg({ type: 'success', text: '✓ 配置已保存' })
    } catch (e) {
      setMsg({ type: 'error', text: '保存失败: ' + (e.response?.data?.detail || e.message) })
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setMsg(null)
    try {
      const res = await testFileStorageConnection()
      const ok = res.data.message.startsWith('✓')
      setMsg({ type: ok ? 'success' : 'error', text: res.data.message })
    } catch (e) {
      setMsg({ type: 'error', text: '测试失败: ' + (e.response?.data?.detail || e.message) })
    } finally {
      setTesting(false)
    }
  }

  // 路径预览
  useEffect(() => {
    if (!projectName.trim()) { setPreviewPath(''); return }
    const t = setTimeout(async () => {
      try {
        const res = await previewFileStoragePath({ project_name: projectName, folder_type: folderType })
        setPreviewPath(res.data[folderType === 'tender' ? 'tender_folder' : 'bid_folder'] || '')
      } catch {
        setPreviewPath('')
      }
    }, 300)
    return () => clearTimeout(t)
  }, [projectName, folderType])

  const handleFiles = async (fileList) => {
    if (!projectName.trim()) {
      setUploadLog(l => [{ ok: false, text: '✗ 请先输入项目名称' }, ...l])
      return
    }
    if (!fileList || fileList.length === 0) return
    setUploading(true)
    const fd = new FormData()
    fd.append('folder_type', folderType)
    fd.append('project_name', projectName)
    for (const f of fileList) fd.append('files', f)
    try {
      const resp = await fetch('/api/file-storage/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
        body: fd,
      })
      const data = await resp.json()
      if (!resp.ok) {
        setUploadLog(l => [{ ok: false, text: `✗ 上传失败: ${data.detail || resp.status}` }, ...l])
      } else {
        const succ = (data.uploaded || []).length
        const fail = (data.failed || []).length
        setUploadLog(l => [{
          ok: fail === 0,
          text: `${fail === 0 ? '✓' : '⚠'} ${data.folder}：成功 ${succ} 个${fail ? `，失败 ${fail} 个` : ''}`
        }, ...l])
      }
    } catch (e) {
      setUploadLog(l => [{ ok: false, text: `✗ 网络错误: ${e.message}` }, ...l])
    } finally {
      setUploading(false)
    }
  }

  if (loading) {
    return <div className="text-gray-500">加载中...</div>
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">📁 文件管理</h1>
        <p className="text-sm text-gray-500 mt-1">
          定义项目文件存储位置。建项目时将按"账号+项目名称+建立时间"模板自动生成文件夹，
          并创建"招标资料/"与"投标文档/"两个子目录，供项目建立时引用。
        </p>
      </div>

      {msg && (
        <div className={`px-4 py-3 rounded ${
          msg.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {msg.text}
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6 space-y-6">
        {/* 存储模式 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">存储模式</label>
          <div className="flex gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="radio" name="mode" value="local" checked={mode === 'local'} onChange={() => setMode('local')} />
              <span>🗄️ 本地磁盘</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="radio" name="mode" value="webdav" checked={mode === 'webdav'} onChange={() => setMode('webdav')} />
              <span>🌐 WebDAV (NAS)</span>
            </label>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            当前模式：<span className="font-semibold">{mode === 'local' ? '本地' : 'WebDAV'}</span>
          </p>
        </div>

        {/* 本地配置 */}
        {mode === 'local' && (
          <div className="border-l-4 border-blue-500 bg-blue-50 p-4 rounded">
            <h3 className="font-semibold mb-2">本地磁盘配置</h3>
            <label className="block text-sm font-medium text-gray-700 mb-1">项目根目录（绝对路径）</label>
            <input
              value={localPath}
              onChange={e => setLocalPath(e.target.value)}
              placeholder="例如：D:\项目文件\渠道项目"
              className="w-full border rounded px-3 py-2"
            />
            <p className="text-xs text-gray-500 mt-1">
              建项目时将在此目录下创建：<code className="bg-white px-1 rounded">{template}</code>
              <span className="text-gray-400 ml-2">可用变量: {'{username} / {real_name} / {project_name} / {date}'}</span>
            </p>
          </div>
        )}

        {/* WebDAV 配置 */}
        {mode === 'webdav' && (
          <div className="border-l-4 border-purple-500 bg-purple-50 p-4 rounded space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">WebDAV 配置</h3>
              <button
                type="button"
                onClick={() => {
                  setWebdavUrl(DEFAULT_WEBDAV.url)
                  setWebdavPort(DEFAULT_WEBDAV.port)
                  setWebdavUseSsl(DEFAULT_WEBDAV.useSsl)
                  setWebdavBasePath(DEFAULT_WEBDAV.basePath)
                  if (!webdavUsername) setWebdavUsername(DEFAULT_WEBDAV.username)
                  setMsg({ type: 'success', text: '✓ 已填充 NAS 缺省配置，请输入密码后测试' })
                }}
                className="text-xs px-3 py-1 bg-white border border-purple-300 text-purple-700 rounded hover:bg-purple-50"
              >
                📋 一键填充 NAS 缺省配置
              </button>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">服务器地址</label>
                <input
                  value={webdavUrl}
                  onChange={e => setWebdavUrl(e.target.value)}
                  placeholder="如：192.168.1.100"
                  className="w-full border rounded px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">端口</label>
                <input
                  value={webdavPort}
                  onChange={e => setWebdavPort(e.target.value.replace(/\D/g, ''))}
                  placeholder="5006"
                  className="w-full border rounded px-3 py-2"
                />
              </div>
              <div className="col-span-3 flex items-center gap-2 text-sm">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={webdavUseSsl}
                    onChange={e => setWebdavUseSsl(e.target.checked)}
                  />
                  <span>使用 HTTPS（SSL）</span>
                </label>
                <span className="text-gray-400 ml-2 text-xs">URL 将拼成：{webdavUseSsl ? 'https' : 'http'}://{webdavUrl || 'host'}{webdavPort ? ':' + webdavPort : ''}</span>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                <input
                  value={webdavUsername}
                  onChange={e => setWebdavUsername(e.target.value)}
                  placeholder="admin"
                  className="w-full border rounded px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">密码</label>
                <input
                  type="password"
                  value={webdavPassword}
                  onChange={e => setWebdavPassword(e.target.value)}
                  placeholder={cfg?.webdav_password === '******' ? '留空保留原密码' : '请输入密码'}
                  className="w-full border rounded px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">协议</label>
                <div className="w-full border rounded px-3 py-2 bg-gray-50 text-gray-600 text-sm">
                  WebDAV
                </div>
              </div>
              <div className="col-span-3">
                <label className="block text-sm font-medium text-gray-700 mb-1">基础路径（NAS 上存放项目的子目录）</label>
                <input
                  value={webdavBasePath}
                  onChange={e => setWebdavBasePath(e.target.value)}
                  placeholder="/渠道资料"
                  className="w-full border rounded px-3 py-2"
                />
              </div>
            </div>
          </div>
        )}

        {/* 模板 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">文件夹命名模板</label>
          <input
            value={template}
            onChange={e => setTemplate(e.target.value)}
            className="w-full border rounded px-3 py-2 font-mono"
          />
          <p className="text-xs text-gray-500 mt-1">
            预览示例：<code className="bg-gray-100 px-1 rounded">{renderPreview(template, 'admin', '测试项目A')}</code>
          </p>
        </div>

        {/* 操作按钮 */}
        <div className="flex justify-end gap-3 pt-4 border-t">
          <button onClick={handleTest} disabled={testing}
            className="px-5 py-2 border border-blue-500 text-blue-600 rounded hover:bg-blue-50 disabled:opacity-50">
            {testing ? '测试中...' : '🔌 测试连通性'}
          </button>
          <button onClick={handleSave} disabled={saving}
            className="px-5 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
            {saving ? '保存中...' : '保存配置'}
          </button>
        </div>
      </div>

      {/* 拖拽上传区 */}
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <div>
          <h2 className="text-lg font-bold mb-1">📤 拖拽文件上传</h2>
          <p className="text-xs text-gray-500">根据上方配置，将文件上传到对应项目目录的"招标资料"或"投标文档"子目录。</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">目标项目</label>
            <input
              list="projects-list"
              value={projectName}
              onChange={e => setProjectName(e.target.value)}
              placeholder="输入或选择项目名称"
              className="w-full border rounded px-3 py-2"
            />
            <datalist id="projects-list">
              {existingProjects.map(p => (
                <option key={p.id} value={p.project_name} />
              ))}
            </datalist>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">子目录</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="folder_type" value="tender" checked={folderType === 'tender'} onChange={() => setFolderType('tender')} />
                <span>📄 招标资料</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="folder_type" value="bid" checked={folderType === 'bid'} onChange={() => setFolderType('bid')} />
                <span>📑 投标文档</span>
              </label>
            </div>
          </div>
        </div>

        {previewPath && (
          <div className="text-xs bg-gray-50 px-3 py-2 rounded border">
            📁 将上传到：<code className="text-blue-700">{previewPath}</code>
          </div>
        )}

        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => {
            e.preventDefault()
            setDragOver(false)
            handleFiles(Array.from(e.dataTransfer.files))
          }}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition ${
            dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={e => handleFiles(Array.from(e.target.files))}
          />
          {uploading ? (
            <div className="text-blue-600 text-lg">⏳ 上传中...</div>
          ) : (
            <>
              <div className="text-4xl mb-2">📎</div>
              <div className="text-gray-700 font-medium">拖拽文件到此处</div>
              <div className="text-sm text-gray-500 mt-1">或点击选择文件 · 支持多选</div>
            </>
          )}
        </div>

        {uploadLog.length > 0 && (
          <div className="bg-gray-50 border rounded p-3 max-h-40 overflow-auto space-y-1">
            {uploadLog.map((l, i) => (
              <div key={i} className={`text-xs ${l.ok ? 'text-green-700' : 'text-red-700'}`}>{l.text}</div>
            ))}
          </div>
        )}
      </div>

      {/* 说明 */}
      <div className="bg-gray-50 border border-gray-200 rounded p-4 text-sm text-gray-600">
        <h3 className="font-semibold mb-2">📌 使用说明</h3>
        <ol className="list-decimal list-inside space-y-1">
          <li>选择存储模式（本地 / WebDAV），填写对应路径与凭据</li>
          <li>点击"测试连通性"验证路径可达且可写</li>
          <li>保存配置</li>
          <li>新建项目时，系统将自动按模板创建文件夹与"招标资料/""投标文档/"子目录</li>
          <li>拖拽文件到上方区域即可上传；也可在新建项目表单内上传对应资料</li>
        </ol>
      </div>
    </div>
  )
}

function renderPreview(tpl, username, projectName) {
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const date = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  return tpl
    .replace('{username}', username)
    .replace('{real_name}', username)
    .replace('{project_name}', projectName)
    .replace('{date}', date)
}