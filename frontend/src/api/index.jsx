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
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
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

// 报表管理
export const getReportSummary = (params) => api.get('/reports/summary', { params })
export const getReportTrend = (params) => api.get('/reports/trend', { params })
export const getReportByPartner = (params) => api.get('/reports/by-partner', { params })
export const getReportByCooperation = (params) => api.get('/reports/by-cooperation', { params })
export const getReportByWinBid = (params) => api.get('/reports/by-win-bid', { params })
export const exportReport = (params) => api.get('/reports/export', { params, responseType: 'blob' })

// 文件管理
export const getFileStorageConfig = () => api.get('/file-storage/config')
export const updateFileStorageConfig = (data) => api.put('/file-storage/config', data)
export const testFileStorageConnection = () => api.post('/file-storage/test-connection')
export const previewFileStoragePath = (data) => api.post('/file-storage/preview-path', data)
export const listStorageFiles = (data) => api.post('/file-storage/list-files', data)

// 导出
export const exportProjects = (params) => api.get('/export/projects', { params, responseType: 'blob' })

// 审计记录
export const getAuditLogs = (params) => api.get('/audit', { params })
export const exportAuditLogs = (params) => api.get('/audit/export', { params, responseType: 'blob' })

export default api
