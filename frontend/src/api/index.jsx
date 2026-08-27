import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const isAdminPath = (error.config?.url || '').match(
      /\/(storage-zones|forms\/templates|users|admin)/
    )
    if (status === 401 || (status === 403 && isAdminPath)) {
      const path = window.location.pathname
      const onLoginPage = path === '/login' || path.startsWith('/login')
      const currentToken = localStorage.getItem('token')
      if (currentToken && !onLoginPage) {
        console.warn(`[auth] ${status} on ${error.config?.url} -> force re-login`)
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        const ret = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.href = `/login?return=${ret}`
      }
    }
    return Promise.reject(error)
  }
)

// 认证
export const login = (data) => api.post('/auth/login', data)
export const getMe = () => api.get('/auth/me')
export const applyAccount = (real_name) => api.post('/auth/apply-account', { real_name })
export const changePassword = (data) => api.post('/auth/change-password', data)

// 用户管理
export const getUsers = (include_inactive = false) => api.get('/users', { params: { include_inactive } })
export const createUser = (data) => api.post('/users', data)
export const updateUser = (id, data) => api.put(`/users/${id}`, data)
export const deleteUser = (id) => api.delete(`/users/${id}`)
export const rejectUser = (id) => api.put(`/users/${id}/reject`)
export const hardDeleteUser = (id) => api.delete(`/users/${id}/hard`)
export const resetPassword = (id, data) => api.put(`/users/${id}/reset-password`, data)

// 项目管理
export const getProjects = (params) => api.get('/projects', { params })
export const getProject = (id) => api.get(`/projects/${id}`)
export const createProject = (data) => api.post('/projects', data)
export const updateProject = (id, data) => api.put(`/projects/${id}`, data)
export const deleteProject = (id) => api.delete(`/projects/${id}`)
export const submitProject = (id) => api.post(`/projects/${id}/submit`)
export const approveProject = (id, data) => api.post(`/projects/${id}/approve`, data)
export const rejectProject = (id, data) => api.post(`/projects/${id}/reject`, data)
export const withdrawProject = (id) => api.post(`/projects/${id}/withdraw`)
export const getApprovalLogs = (id) => api.get(`/projects/${id}/logs`)

// 审批管理
export const getApprovalPending = (params) => api.get('/approvals/pending', { params })
export const getApprovalHistory = (params) => api.get('/approvals/history', { params })
export const getApprovalSummary = () => api.get('/approvals/summary')
export const fastApprove = (id) => api.post(`/approvals/${id}/approve`)
export const fastReject = (id) => api.post(`/approvals/${id}/reject`)

// 系统管理（仅 admin）
export const restartService = () => api.post('/system/restart')

// 报表管理
export const getReportSummary = (params) => api.get('/reports/summary', { params })
export const getReportTrend = (params) => api.get('/reports/trend', { params })
export const getReportByPartner = (params) => api.get('/reports/by-partner', { params })
export const getReportByCooperation = (params) => api.get('/reports/by-cooperation', { params })
export const getReportByWinBid = (params) => api.get('/reports/by-win-bid', { params })
export const exportReport = (params) => api.get('/reports/export', { params, responseType: 'blob' })
export const getReportByFollowupStage = (params) => api.get('/reports/by-followup-stage', { params })
export const exportFullReport = () => api.get('/reports/export-full', { responseType: 'blob' })
export const getAIModelConfigs = () => api.get('/forms/ai-models')
export const getAIModelPresets = () => api.get('/forms/ai-model-presets')
export const analyzeReportWithAI = (data) => api.post('/reports/ai-analyze', data)
export const askReportAssistant = (data) => api.post('/reports/ai-assistant', data)
export const createAIModelConfig = (data) => api.post('/forms/ai-models', data)
export const updateAIModelConfig = (id, data) => api.put(`/forms/ai-models/${id}`, data)
export const deleteAIModelConfig = (id) => api.delete(`/forms/ai-models/${id}`)
export const testAIModelConfig = (id, data) => api.post(`/forms/ai-models/${id}/test`, data)

// Agent 系统提示词
export const listAgentPrompts = (params) => api.get('/agent-prompts', { params })
export const getActiveAgentPrompt = (role_key = 'default') => api.get('/agent-prompts/active', { params: { role_key } })
export const createAgentPrompt = (data) => api.post('/agent-prompts', data)
export const updateAgentPrompt = (id, data) => api.put(`/agent-prompts/${id}`, data)
export const deleteAgentPrompt = (id) => api.delete(`/agent-prompts/${id}`)
export const seedAgentPrompts = () => api.post('/agent-prompts/seed')

// 项目跟单
export const getFollowupStageOptions = () => api.get('/project-followups/stage-options')
export const getFollowupTemplate = () => api.get('/project-followups/template')
export const getFollowableProjects = () => api.get('/project-followups/followable-projects')
export const listFollowups = (params) => api.get('/project-followups', { params })
export const exportFollowups = (params) => api.get('/project-followups/export', { params, responseType: 'blob' })
export const getFollowupTimeline = (project_id) => api.get('/project-followups/timeline', { params: { project_id } })
export const getFollowupSummary = () => api.get('/project-followups/summary')
export const createFollowup = (data) => api.post('/project-followups', data)
export const updateFollowup = (id, data) => api.put(`/project-followups/${id}`, data)
export const deleteFollowup = (id) => api.delete(`/project-followups/${id}`)

// 文件管理
export const getFileStorageConfig = () => api.get('/file-storage/config')
export const updateFileStorageConfig = (data) => api.put('/file-storage/config', data)
export const testFileStorageConnection = () => api.post('/file-storage/test-connection')
export const previewFileStoragePath = (data) => api.post('/file-storage/preview-path', data)
export const listStorageFiles = (data) => api.post('/file-storage/list-files', data)
// ★ 诊断所有项目的存储路径（不修改 DB）
export const diagnoseFileStorage = () => api.post('/file-storage/diagnose-all')
// ★ 重建指定项目的 WebDAV 目录（仅 admin）
export const rebuildProjectFolders = (data) => api.post('/file-storage/rebuild-project-folders', data).then(r => r.data)

// 导出
export const exportProjects = (params) => api.get('/export/projects', { params, responseType: 'blob' })

// 审计记录
export const getAuditLogs = (params) => api.get('/audit', { params })
export const exportAuditLogs = (params) => api.get('/audit/export', { params, responseType: 'blob' })

// 表单生成器
export const getFormTemplates = () => api.get('/forms/templates')
export const getFormTemplate = (id) => api.get(`/forms/templates/${id}`)
export const createFormTemplate = (data) => api.post('/forms/templates', data)
export const updateFormTemplate = (id, data) => api.put(`/forms/templates/${id}`, data)
export const deleteFormTemplate = (id) => api.delete(`/forms/templates/${id}`)
export const getFormInstances = (params) => api.get('/forms/instances', { params })
export const createFormInstance = (data) => api.post('/forms/instances', data)
export const getFormInstance = (id) => api.get(`/forms/instances/${id}`)
export const updateFormInstance = (id, payload) => api.put(`/forms/instances/${id}`, payload)
export const deleteFormInstance = (id) => api.delete(`/forms/instances/${id}`)

// ============ 存储区域 ============
export const listStorageZones = () => api.get('/storage-zones')
export const getStorageZone = (id) => api.get(`/storage-zones/${id}`)
export const createStorageZone = (data) => api.post('/storage-zones', data)
export const updateStorageZone = (id, data) => api.put(`/storage-zones/${id}`, data)
export const deleteStorageZone = (id) => api.delete(`/storage-zones/${id}`)
export const testStorageZoneConnection = (id) => api.post(`/storage-zones/${id}/test-connection`)
export const revealStorageZonePassword = (id) => api.get(`/storage-zones/${id}/reveal-password`)

// ============ 通知中心 ============
export const listNotifications = (params) => api.get('/notifications', { params })
export const getUnreadCount = () => api.get('/notifications/unread')
export const markNotificationRead = (id) => api.post(`/notifications/${id}/read`)
export const markAllNotificationsRead = () => api.post('/notifications/read-all')
export const listNotificationSettings = () => api.get('/notifications/settings')
export const updateNotificationSetting = (type, data) => api.put(`/notifications/settings/${type}`, data)
export const sendAnnouncement = (data) => api.post('/notifications/announce', data)
export const listNotificationChannels = () => api.get('/notifications/channels')
export const upsertNotificationChannel = (type, data) => api.post(`/notifications/channels/${type}`, data)

// 通知文案模板
export const listNotificationTemplates = () => api.get('/notifications/templates')
export const upsertNotificationTemplate = (type, channel, data) => api.put(`/notifications/templates/${type}/${channel}`, data)
export const deleteNotificationTemplate = (type, channel) => api.delete(`/notifications/templates/${type}/${channel}`)

// 通知全局配置(统一题头)
export const getNotificationGlobalConfig = () => api.get('/notifications/global-config')
export const updateNotificationGlobalConfig = (data) => api.put('/notifications/global-config', data)
export const initFormFolders = (data) => api.post('/forms/file-storage/init-folders', data)
export const listFormFiles = (data) => api.post('/forms/file-storage/list-files', data)
export const uploadFormFiles = (instanceId, folderType, files) => {
  const fd = new FormData()
  fd.append('instance_id', instanceId)
  fd.append('folder_type', folderType)
  files.forEach(f => fd.append('files', f))
  return api.post('/forms/file-storage/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export const deleteFormFile = (data) => api.post('/forms/file-storage/delete-file', data)

export default api