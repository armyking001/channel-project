import { useState, useEffect } from 'react'
import {
  listStorageZones, createStorageZone, updateStorageZone,
  deleteStorageZone, testStorageZoneConnection,
  revealStorageZonePassword,
} from '../api'

const inputCls = "w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-500"

export default function StorageZones() {
  const [zones, setZones] = useState([])
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(null)  // null | 'new' | {id,...}
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await listStorageZones()
      setZones(r.data.items || [])
    } catch (e) {
      alert('加载失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (z) => {
    if (!confirm(`确定删除存储区域「${z.name}」吗？\n注：项目不会删除，但相关项目/表单将失去该区域关联。`)) return
    try {
      await deleteStorageZone(z.id)
      load()
    } catch (e) {
      alert('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleTest = async (z) => {
    setTesting(true)
    setTestResult(null)
    try {
      const r = await testStorageZoneConnection(z.id)
      setTestResult({ id: z.id, ok: r.data.ok, message: r.data.message })
      if (r.data.ok) {
        alert(`✅ 连接成功\n${r.data.message}`)
      } else {
        alert(`❌ 连接失败\n${r.data.message}`)
      }
    } catch (e) {
      alert('测试失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setTesting(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold">存储区域管理</h2>
        <button onClick={() => setEditing('new')}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm">
          + 新增存储区域
        </button>
      </div>

      <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-700">
        💡 存储区域用于定义文件保存位置（本地或远程 WebDAV/NAS）。
        在表单管理中编辑表单时，可为该表单指定一个存储区域，实现不同表单存储在不同的 NAS 位置。
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-8">加载中...</div>
      ) : zones.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center text-gray-400">
          暂无存储区域，点击右上角"新增存储区域"创建
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">名称</th>
                <th className="px-4 py-3 text-center text-gray-600 font-medium">存储模式</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">Base URL / 本地路径</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">用户名</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">起始路径</th>
                <th className="px-4 py-3 text-left text-gray-600 font-medium">子路径</th>
                <th className="px-4 py-3 text-center text-gray-600 font-medium">状态</th>
                <th className="px-4 py-3 text-center text-gray-600 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {zones.map(z => (
                <tr key={z.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{z.name}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                      z.mode === 'webdav' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
                    }`}>
                      {z.mode === 'webdav' ? '🌐 WebDAV' : '📁 本地'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                    {z.mode === 'webdav'
                      ? `${z.webdav_use_ssl ? 'https' : 'http'}://${z.webdav_url}${z.webdav_port ? ':' + z.webdav_port : ''}`
                      : z.local_path}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{z.webdav_username || '-'}</td>
                  <td className="px-4 py-3 text-gray-600 font-mono text-xs">{z.webdav_base_path || '/'}</td>
                  <td className="px-4 py-3 text-gray-600 font-mono text-xs">{z.sub_path || '-'}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      z.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      {z.is_active ? '启用' : '停用'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-center gap-2">
                      <button onClick={() => handleTest(z)} disabled={testing}
                        className="text-blue-600 hover:text-blue-800 text-xs disabled:opacity-50">
                        🔌 测试连接
                      </button>
                      <button onClick={() => setEditing(z)}
                        className="text-green-600 hover:text-green-800 text-xs">编辑</button>
                      <button onClick={() => handleDelete(z)}
                        className="text-red-500 hover:text-red-700 text-xs">删除</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <StorageZoneEditor
          zone={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load() }}
        />
      )}
    </div>
  )
}

function StorageZoneEditor({ zone, onClose, onSaved }) {
  const isNew = !zone
  const [form, setForm] = useState({
    name: zone?.name || '',
    mode: zone?.mode || 'webdav',
    local_path: zone?.local_path || '',
    webdav_url: zone?.webdav_url || '',
    webdav_port: zone?.webdav_port || '',
    webdav_use_ssl: zone?.webdav_use_ssl !== false,
    webdav_username: zone?.webdav_username || '',
    webdav_password: '',  // 初始为空，点击眼睛后拉取明文
    webdav_base_path: zone?.webdav_base_path || '',
    sub_path: zone?.sub_path || '',
    description: zone?.description || '',
    sort_order: zone?.sort_order || 0,
  })
  const [saving, setSaving] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [revealedPwd, setRevealedPwd] = useState('')  // 拉取到的明文密码
  const [revealing, setRevealing] = useState(false)

  // 点击眼睛：拉取明文密码
  const toggleRevealPassword = async () => {
    if (showPassword) {
      // 取消显示
      setShowPassword(false)
      setRevealedPwd('')
      return
    }
    if (revealedPwd) {
      // 已经拉取过，直接显示
      setShowPassword(true)
      return
    }
    setRevealing(true)
    try {
      const r = await revealStorageZonePassword(zone.id)
      const pwd = r.data.password || ''
      setRevealedPwd(pwd)
      setShowPassword(true)
    } catch (e) {
      alert('获取密码失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setRevealing(false)
    }
  }

  // 显示值：眼睛打开时用拉取的明文，否则用表单值（用户可能改过）
  const passwordDisplayValue = showPassword
    ? (form.webdav_password !== '' ? form.webdav_password : revealedPwd)
    : form.webdav_password

  const setField = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = async () => {
    if (!form.name.trim()) { alert('请输入区域名称'); return }
    if (form.mode === 'webdav' && !form.webdav_url.trim()) { alert('WebDAV 模式必须填写服务器地址'); return }
    if (form.mode === 'local' && !form.local_path.trim()) { alert('本地模式必须填写路径'); return }

    setSaving(true)
    try {
      const payload = {
        ...form,
        webdav_port: form.webdav_port ? parseInt(form.webdav_port) : null,
        sort_order: parseInt(form.sort_order) || 0,
      }
      // 如果密码为空且是编辑，不发送密码字段（保留原密码）
      if (!isNew && !payload.webdav_password) {
        delete payload.webdav_password
      }
      if (isNew) {
        await createStorageZone(payload)
      } else {
        await updateStorageZone(zone.id, payload)
      }
      alert('保存成功')
      onSaved()
    } catch (e) {
      alert('保存失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full p-6 max-h-[92vh] overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold">{isNew ? '新增存储区域' : `编辑存储区域: ${zone.name}`}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>

        <div className="space-y-4">
          {/* 名称和模式 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">名称 <span className="text-red-500">*</span></label>
              <input type="text" value={form.name} onChange={e => setField('name', e.target.value)}
                placeholder="如：172nas / 测试资质 / 渠道资料库"
                className={inputCls} />
              <p className="text-xs text-gray-400 mt-1">唯一标识，表单调配时显示</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">存储模式</label>
              <div className="flex gap-4 pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="mode" value="webdav" checked={form.mode === 'webdav'}
                    onChange={() => setField('mode', 'webdav')} />
                  <span>🌐 WebDAV (NAS)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="mode" value="local" checked={form.mode === 'local'}
                    onChange={() => setField('mode', 'local')} />
                  <span>📁 本地磁盘</span>
                </label>
              </div>
            </div>
          </div>

          {/* WebDAV 配置 */}
          {form.mode === 'webdav' && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 space-y-3">
              <div className="text-sm font-bold text-purple-800">WebDAV 连接配置</div>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-gray-700 mb-1">服务器地址 <span className="text-red-500">*</span></label>
                  <input type="text" value={form.webdav_url} onChange={e => setField('webdav_url', e.target.value)}
                    placeholder="如：172.16.10.252" className={inputCls} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">端口</label>
                  <input type="number" value={form.webdav_port} onChange={e => setField('webdav_port', e.target.value)}
                    placeholder="5006" className={inputCls} />
                </div>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.webdav_use_ssl}
                  onChange={e => setField('webdav_use_ssl', e.target.checked)} />
                <span className="text-sm">使用 HTTPS (SSL)</span>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">用户名</label>
                  <input type="text" value={form.webdav_username} onChange={e => setField('webdav_username', e.target.value)}
                    placeholder="如：trae" className={inputCls} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    密码 {isNew && <span className="text-red-500">*</span>}
                    {!isNew && <span className="text-gray-400 text-xs">（已加密保存，点击右侧眼睛查看明文）</span>}
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={passwordDisplayValue}
                      onChange={e => setField('webdav_password', e.target.value)}
                      placeholder={isNew ? '请输入密码' : '点击眼睛查看或修改密码'}
                      className={inputCls + ' pr-10'} />
                    {!isNew && (
                      <button type="button" onClick={toggleRevealPassword}
                        disabled={revealing}
                        className="absolute inset-y-0 right-0 px-3 flex items-center text-gray-400 hover:text-blue-600 disabled:opacity-50"
                        title={showPassword ? '隐藏密码' : '查看密码'}>
                        {revealing ? '⏳' : showPassword ? '🙈' : '👁️'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">起始路径（基础路径）</label>
                <input type="text" value={form.webdav_base_path} onChange={e => setField('webdav_base_path', e.target.value)}
                  placeholder="如：/渠道资料" className={inputCls} />
                <p className="text-xs text-gray-400 mt-1">NAS WebDAV 服务下的根目录（如 /dav/渠道资料）</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">子路径（表单/项目存放位置）</label>
                <input type="text" value={form.sub_path} onChange={e => setField('sub_path', e.target.value)}
                  placeholder="如：自建项目 / 渠道项目（留空则直接放起始路径）" className={inputCls} />
                <p className="text-xs text-gray-400 mt-1">该区域下存放特定表单/项目的子目录</p>
              </div>
            </div>
          )}

          {/* 本地配置 */}
          {form.mode === 'local' && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
              <div className="text-sm font-bold text-gray-800">本地存储配置</div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">本地路径 <span className="text-red-500">*</span></label>
                <input type="text" value={form.local_path} onChange={e => setField('local_path', e.target.value)}
                  placeholder="如：D:\\项目文件\\渠道项目" className={inputCls} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">子路径</label>
                <input type="text" value={form.sub_path} onChange={e => setField('sub_path', e.target.value)}
                  placeholder="如：自建项目 / 渠道项目（留空则直接放本地路径）" className={inputCls} />
              </div>
            </div>
          )}

          {/* 备注和排序 */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">备注说明</label>
              <textarea value={form.description} onChange={e => setField('description', e.target.value)}
                rows={2} placeholder="选填" className={inputCls} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">排序</label>
              <input type="number" value={form.sort_order} onChange={e => setField('sort_order', e.target.value)}
                className={inputCls} />
              <p className="text-xs text-gray-400 mt-1">数字越小越靠前</p>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6 pt-4 border-t">
          <button onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50">
            取消
          </button>
          <button onClick={handleSave} disabled={saving}
            className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}