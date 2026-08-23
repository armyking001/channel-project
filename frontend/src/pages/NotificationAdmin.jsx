import { useEffect, useState } from 'react'
import {
  sendAnnouncement,
  listNotificationChannels,
  upsertNotificationChannel,
  listNotificationTemplates,
  upsertNotificationTemplate,
  deleteNotificationTemplate,
  getNotificationGlobalConfig,
  updateNotificationGlobalConfig,
} from '../api'

const CHANNEL_TYPES = [
  { v: 'dingtalk_webhook', l: '钉钉群机器人 Webhook', cfgHint: '{ webhook: "https://oapi.dingtalk.com/robot/send?access_token=...", sign_secret: "SEC..."(可选) }' },
  { v: 'dingtalk_corp', l: '钉钉企业应用(工作通知)', cfgHint: '{ corp_id: "ding...", agent_id: "...", app_key: "...", app_secret: "..." }' },
  { v: 'sms_aliyun', l: '阿里云短信', cfgHint: '{ access_key_id, access_key_secret, sign_name, template_id }' },
  { v: 'sms_tencent', l: '腾讯云短信', cfgHint: '{ secret_id, secret_key, app_id, template_id, sign_name }' },
]

const TYPE_LABELS = {
  account_apply: '账号申请',
  account_approved: '账号通过',
  account_rejected: '账号驳回',
  password_reset: '密码重置',
  followup_viewed: '跟单被查看',
  project_pending: '项目待审批',
  project_approved: '项目审批通过',
  project_rejected: '项目审批驳回',
  system_announcement: '系统公告',
}

const CHANNEL_LABELS = {
  in_app: '站内',
  dingtalk: '钉钉',
  sms: '短信',
}

const PLACEHOLDER_DOC = {
  account_apply: 'actor_name(申请人姓名)、username(账号)',
  account_approved: 'actor_name(被审批人)、admin_name(审批人)',
  account_rejected: 'actor_name(被审批人)、admin_name(审批人)、reason(原因)',
  password_reset: 'actor_name(被重置人)、admin_name(操作管理员)',
  followup_viewed: 'actor_name(查看者)、reporter_name(跟单提交人)、project_name(项目名)',
  project_pending: 'actor_name(提交人)、approver_name(审批人)、project_name(项目名)、template_name(模板名)',
  project_approved: 'actor_name(项目创建人)、admin_name(审批人)、project_name(项目名)',
  project_rejected: 'actor_name(项目创建人)、admin_name(审批人)、project_name(项目名)、reason(原因)',
  system_announcement: 'actor_name(发公告的管理员)',
}

const DEFAULT_TITLE = {
  account_apply: '账号申请待审批',
  account_approved: '账号审批通过',
  account_rejected: '账号审批驳回',
  password_reset: '您的密码已被重置',
  followup_viewed: '您的跟单被查看',
  project_pending: '新项目待审批',
  project_approved: '项目审批通过',
  project_rejected: '项目审批驳回',
  system_announcement: '系统公告',
}

const DEFAULT_CONTENT = {
  account_apply: '{actor_name}({username}) 提交了账号申请,请尽快审批。',
  account_approved: '您的账号申请已由 {admin_name} 审批通过,可以登录系统了。',
  account_rejected: '您的账号申请被 {admin_name} 驳回{reason}。',
  password_reset: '{admin_name} 已将您的密码重置为新的临时密码,请尽快登录并修改。',
  followup_viewed: '{actor_name} 查看了您关于「{project_name}」的跟单记录。',
  project_pending: '{actor_name} 通过「{template_name}」提交了项目「{project_name}」,请尽快审批。',
  project_approved: '您的项目「{project_name}」已由 {admin_name} 审批通过。',
  project_rejected: '您的项目「{project_name}」被 {admin_name} 驳回{reason}。',
  system_announcement: '{actor_name} 发布了系统公告。',
}

export default function NotificationAdmin() {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [sending, setSending] = useState(false)
  const [channels, setChannels] = useState([])
  const [edit, setEdit] = useState(null)
  const [templates, setTemplates] = useState([])
  const [editingTpl, setEditingTpl] = useState(null)
  const [globalCfg, setGlobalCfg] = useState({ title_prefix: '【销售项目管理系统V2.0通知】', apply_in_app: false })
  const [tab, setTab] = useState('tpls')

  const load = async () => {
    try {
      const r = await listNotificationChannels()
      setChannels(r.data || [])
    } catch (_) {}
  }

  const loadTpls = async () => {
    try {
      const r = await listNotificationTemplates()
      setTemplates(r.data || [])
    } catch (_) {}
  }

  const loadGlobalCfg = async () => {
    try {
      const r = await getNotificationGlobalConfig()
      setGlobalCfg(r.data)
    } catch (_) {}
  }

  const saveGlobalCfg = async () => {
    try {
      await updateNotificationGlobalConfig({
        title_prefix: globalCfg.title_prefix,
        apply_in_app: globalCfg.apply_in_app,
      })
      alert('已保存')
      loadGlobalCfg()
    } catch (e) {
      alert('保存失败: ' + (e && e.response && e.response.data && e.response.data.detail || e.message))
    }
  }

  useEffect(() => { load(); loadTpls(); loadGlobalCfg() }, [])

  const submitAnnouncement = async () => {
    if (!title.trim() || !content.trim()) { alert('标题和内容不能为空'); return }
    if (!confirm('确定要群发给所有用户(' + title.trim() + ')吗?')) return
    setSending(true)
    try {
      const r = await sendAnnouncement({ title: title.trim(), content: content.trim() })
      alert(r.data.message)
      setTitle(''); setContent('')
    } catch (e) {
      alert('发送失败: ' + (e && e.response && e.response.data && e.response.data.detail || e.message))
    }
    setSending(false)
  }

  const openEdit = (ch) => {
    let cfg
    try { cfg = JSON.parse(ch.config || '{}') } catch (_) { cfg = {} }
    setEdit({ type: ch.type, name: ch.name, configText: JSON.stringify(cfg, null, 2), enabled: ch.enabled })
  }

  const newChannel = (ctype) => setEdit({ type: ctype, name: CHANNEL_TYPES.find(c => c.v === ctype).l, configText: '{}', enabled: true })

  const saveEdit = async () => {
    if (!edit) return
    let cfg
    try { cfg = JSON.parse(edit.configText) } catch (_) { alert('配置必须是合法 JSON'); return }
    try {
      await upsertNotificationChannel(edit.type, { name: edit.name, config: cfg, enabled: edit.enabled })
      setEdit(null)
      load()
    } catch (e) {
      alert('保存失败: ' + (e && e.message))
    }
  }

  const openEditTpl = (tpl, ntype, channel) => {
    setEditingTpl({
      type: ntype,
      channel,
      title_template: tpl?.title_template || DEFAULT_TITLE[ntype] || '',
      content_template: tpl?.content_template || DEFAULT_CONTENT[ntype] || '',
      enabled: tpl ? tpl.enabled : false,
      isNew: !tpl,
    })
  }

  const saveTpl = async () => {
    if (!editingTpl) return
    try {
      await upsertNotificationTemplate(editingTpl.type, editingTpl.channel, {
        title_template: editingTpl.title_template,
        content_template: editingTpl.content_template,
        enabled: editingTpl.enabled,
      })
      setEditingTpl(null)
      loadTpls()
    } catch (e) {
      alert('保存失败: ' + (e && e.response && e.response.data && e.response.data.detail || e.message))
    }
  }

  const removeTpl = async (ntype, channel) => {
    if (!confirm('确定要删除该文案模板吗?删除后会回退到默认文案。')) return
    try {
      await deleteNotificationTemplate(ntype, channel)
      loadTpls()
    } catch (e) {
      alert('删除失败: ' + (e && e.message))
    }
  }

  const tplKey = (type, channel) => `${type}__${channel}`

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-800">📣 通知管理(系统管理员)</h2>

      {/* Tab 切换 */}
      <div className="flex gap-2 border-b border-gray-200">
        <button
          onClick={() => setTab('tpls')}
          className={"px-4 py-2 text-sm font-medium border-b-2 " + (tab === 'tpls' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}
        >
          📝 通知文案模板
        </button>
        <button
          onClick={() => setTab('ann')}
          className={"px-4 py-2 text-sm font-medium border-b-2 " + (tab === 'ann' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}
        >
          📢 群发系统公告
        </button>
        <button
          onClick={() => setTab('chans')}
          className={"px-4 py-2 text-sm font-medium border-b-2 " + (tab === 'chans' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}
        >
          📡 通知通道配置
        </button>
      </div>

      {/* 通知文案模板 */}
      {tab === 'tpls' && (
        <div className="space-y-4">
          {/* 统一题头全局配置 */}
          <div className="bg-gradient-to-r from-blue-50 to-cyan-50 border border-blue-200 rounded-lg p-5">
            <h3 className="font-semibold text-lg mb-2 flex items-center gap-2">
              <span>🌐 通知统一题头(全局)</span>
              <span className="text-xs px-2 py-0.5 bg-blue-500 text-white rounded">改一次 · 所有通知生效</span>
            </h3>
            <p className="text-xs text-gray-600 mb-3">
              题头会自动加到所有钉钉 / 短信通知的开头(站内不加)。修改后下次发送即应用。
            </p>
            <div className="space-y-3">
              <label className="block">
                <span className="text-sm text-gray-700">题头文字(为空则不附加)</span>
                <input
                  value={globalCfg.title_prefix || ''}
                  onChange={e => setGlobalCfg({ ...globalCfg, title_prefix: e.target.value })}
                  className="mt-1 w-full border border-gray-300 rounded px-3 py-2"
                  maxLength={100}
                />
                <div className="mt-1 text-xs text-gray-500">
                  默认: <code className="bg-white px-1 rounded">【销售项目管理系统V2.0通知】</code>
                </div>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={!!globalCfg.apply_in_app}
                  onChange={e => setGlobalCfg({ ...globalCfg, apply_in_app: e.target.checked })}
                  className="w-4 h-4"
                />
                <span className="text-sm text-gray-700">同时加在站内通知上(默认关闭,避免重复)</span>
              </label>
              <div className="flex items-center gap-3">
                <button
                  onClick={saveGlobalCfg}
                  className="px-4 py-2 rounded bg-blue-500 text-white hover:bg-blue-600 text-sm"
                >
                  保存题头
                </button>
                <span className="text-xs text-gray-500">
                  下次触发通知时自动加在前部;已有模板中包含题头也不会重复添加。
                </span>
              </div>
            </div>
          </div>

          {/* 27 行模板列表 */}
          <div className="bg-white border border-gray-200 rounded-lg p-5">
            <h3 className="font-semibold text-lg mb-2">📝 各事件-通道文案(可选覆盖)</h3>
            <p className="text-xs text-gray-500 mb-3">
              每个事件 × 3 通道的文案,默认自动加上面那个全局题头。如果要修改某个事件的默认正文,可以单独覆盖。
              模板支持占位符(如 <code className="bg-gray-100 px-1 rounded">{'{actor_name}'}</code>)。
            </p>
            <table className="min-w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-200 bg-gray-50">
                  <th className="py-2 px-3">事件类型</th>
                  <th className="py-2 px-3">通道</th>
                  <th className="py-2 px-3">当前文案预览</th>
                  <th className="py-2 px-3">状态</th>
                  <th className="py-2 px-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(TYPE_LABELS).map(ntype => (
                  ['in_app', 'dingtalk', 'sms'].map(channel => {
                    const tpl = templates.find(t => t.type === ntype && t.channel === channel)
                    const enabled = tpl && tpl.enabled
                    const preview = (tpl && tpl.enabled)
                      ? `[${tpl.title_template}] ${(tpl.content_template || '').slice(0, 30)}${(tpl.content_template || '').length > 30 ? '...' : ''}`
                      : `默认: [${DEFAULT_TITLE[ntype]}] ${DEFAULT_CONTENT[ntype].slice(0, 30)}...`
                    return (
                      <tr key={tplKey(ntype, channel)} className="border-b border-gray-50">
                        <td className="py-2 px-3 font-medium">{TYPE_LABELS[ntype]}</td>
                        <td className="py-2 px-3">
                          <span className="px-2 py-0.5 text-xs rounded bg-gray-100">{CHANNEL_LABELS[channel]}</span>
                        </td>
                        <td className="py-2 px-3 text-gray-500 max-w-[400px] truncate" title={preview}>
                          {preview}
                        </td>
                        <td className="py-2 px-3">
                          {enabled
                            ? <span className="text-green-600">● 自定义启用</span>
                            : <span className="text-gray-400">○ 使用默认</span>}
                        </td>
                        <td className="py-2 px-3 text-right space-x-2">
                          <button
                            onClick={() => openEditTpl(tpl, ntype, channel)}
                            className="text-blue-600 hover:underline text-xs"
                          >
                            {tpl ? '编辑' : '自定义'}
                          </button>
                          {tpl && (
                            <button
                              onClick={() => removeTpl(ntype, channel)}
                              className="text-red-500 hover:underline text-xs"
                            >
                              删除
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 群发公告 */}
      {tab === 'ann' && (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-lg mb-3">📢 群发系统公告</h3>
          <div className="space-y-3">
            <input
              className="w-full border border-gray-300 rounded px-3 py-2"
              placeholder="公告标题"
              value={title}
              onChange={e => setTitle(e.target.value)}
              maxLength={200}
            />
            <textarea
              className="w-full border border-gray-300 rounded px-3 py-2 h-32"
              placeholder="公告内容(支持换行)"
              value={content}
              onChange={e => setContent(e.target.value)}
            />
            <button
              onClick={submitAnnouncement}
              disabled={sending}
              className={"px-4 py-2 rounded text-white " + (sending ? 'bg-gray-400' : 'bg-blue-500 hover:bg-blue-600')}
            >
              {sending ? '发送中...' : '发送群公告'}
            </button>
          </div>
        </div>
      )}

      {/* 通道配置 */}
      {tab === 'chans' && (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-lg mb-3">📡 通知通道配置</h3>
          <p className="text-xs text-gray-500 mb-3">每一类通道只保留一个生效配置;未启用的通道不会触发。</p>
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-100">
                <th className="py-2 px-3">类型</th>
                <th className="py-2 px-3">名称</th>
                <th className="py-2 px-3">状态</th>
                <th className="py-2 px-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {CHANNEL_TYPES.map(ct => {
                const row = channels.find(c => c.type === ct.v)
                return (
                  <tr key={ct.v} className="border-b border-gray-50">
                    <td className="py-2 px-3">{ct.l}</td>
                    <td className="py-2 px-3">{row ? row.name : '(未配置)'}</td>
                    <td className="py-2 px-3">
                      {row
                        ? (row.enabled
                          ? <span className="text-green-600">● 已启用</span>
                          : <span className="text-gray-400">○ 已停用</span>)
                        : <span className="text-gray-300">- 未配置 -</span>}
                    </td>
                    <td className="py-2 px-3 text-right">
                      <button
                        onClick={() => row ? openEdit(row) : newChannel(ct.v)}
                        className="text-blue-600 hover:underline text-xs"
                      >
                        {row ? '编辑' : '新增'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 通道编辑弹窗 */}
      {edit && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-[640px] max-w-[95vw] p-6 space-y-4">
            <h3 className="font-bold text-lg">
              {CHANNEL_TYPES.find(c => c.v === edit.type) ? CHANNEL_TYPES.find(c => c.v === edit.type).l : edit.type}
            </h3>
            <p className="text-xs text-gray-500">
              配置示例:{CHANNEL_TYPES.find(c => c.v === edit.type) ? CHANNEL_TYPES.find(c => c.v === edit.type).cfgHint : ''}
            </p>
            <label className="block">
              <span className="text-sm text-gray-700">名称</span>
              <input
                value={edit.name}
                onChange={e => setEdit(Object.assign({}, edit, { name: e.target.value }))}
                className="mt-1 w-full border border-gray-300 rounded px-3 py-2"
              />
            </label>
            <label className="block">
              <span className="text-sm text-gray-700">配置 (JSON)</span>
              <textarea
                value={edit.configText}
                onChange={e => setEdit(Object.assign({}, edit, { configText: e.target.value }))}
                className="mt-1 w-full border border-gray-300 rounded px-3 py-2 font-mono text-sm h-48"
              />
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={edit.enabled}
                onChange={e => setEdit(Object.assign({}, edit, { enabled: e.target.checked }))}
                className="w-4 h-4"
              />
              <span className="text-sm">启用</span>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setEdit(null)}
                className="px-4 py-2 rounded border border-gray-300 hover:bg-gray-50"
              >取消</button>
              <button
                onClick={saveEdit}
                className="px-4 py-2 rounded bg-blue-500 text-white hover:bg-blue-600"
              >保存</button>
            </div>
          </div>
        </div>
      )}

      {/* 模板编辑弹窗 */}
      {editingTpl && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-[760px] max-w-[95vw] p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <h3 className="font-bold text-lg">
              ✏️ 编辑文案模板 — {TYPE_LABELS[editingTpl.type]} / {CHANNEL_LABELS[editingTpl.channel]}
              {editingTpl.isNew && <span className="ml-2 text-xs px-2 py-0.5 bg-orange-100 text-orange-700 rounded">新增</span>}
            </h3>
            <div className="bg-gray-50 border border-gray-200 rounded p-3 text-xs text-gray-600">
              <div className="font-semibold mb-1">📖 可用占位符</div>
              <div>{PLACEHOLDER_DOC[editingTpl.type]}</div>
              <div className="mt-1 text-gray-400">未提供的占位符会渲染为空字符串。全局题头会自动加在钉钉/短信开头。</div>
            </div>
            <label className="block">
              <span className="text-sm text-gray-700">标题模板</span>
              <input
                value={editingTpl.title_template}
                onChange={e => setEditingTpl({ ...editingTpl, title_template: e.target.value })}
                className="mt-1 w-full border border-gray-300 rounded px-3 py-2"
                maxLength={200}
                placeholder={'默认: ' + DEFAULT_TITLE[editingTpl.type]}
              />
              <div className="mt-1 text-xs text-gray-400">
                默认: <code>{DEFAULT_TITLE[editingTpl.type]}</code>
              </div>
            </label>
            <label className="block">
              <span className="text-sm text-gray-700">正文模板</span>
              <textarea
                value={editingTpl.content_template}
                onChange={e => setEditingTpl({ ...editingTpl, content_template: e.target.value })}
                className="mt-1 w-full border border-gray-300 rounded px-3 py-2 font-mono text-sm h-32"
                maxLength={4000}
              />
              <div className="mt-1 text-xs text-gray-400">
                默认: <code>{DEFAULT_CONTENT[editingTpl.type]}</code>
              </div>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={editingTpl.enabled}
                onChange={e => setEditingTpl({ ...editingTpl, enabled: e.target.checked })}
                className="w-4 h-4"
              />
              <span className="text-sm">启用此模板(不勾选则继续走默认文案)</span>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setEditingTpl(null)}
                className="px-4 py-2 rounded border border-gray-300 hover:bg-gray-50"
              >取消</button>
              <button
                onClick={saveTpl}
                className="px-4 py-2 rounded bg-blue-500 text-white hover:bg-blue-600"
              >保存模板</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}