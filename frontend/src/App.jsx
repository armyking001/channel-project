import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/auth'
import Login from './pages/Login'
import Projects from './pages/Projects'
import UserManagement from './pages/UserManagement'
import Approvals from './pages/Approvals'
import Reports from './pages/Reports'
import FileStorage from './pages/FileStorage'
import AuditLogs from './pages/AuditLogs'
import FormTemplates from './pages/FormTemplates'
import FormBuilder from './pages/FormBuilder'
import StorageZones from './pages/StorageZones'
import ProjectFollowups from './pages/ProjectFollowups'
import Layout from './components/Layout'

function ProtectedRoute({ children }) {
  const { user } = useAuthStore()
  return user ? children : <Navigate to="/login" />
}

function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/project-followups" element={<ProjectFollowups />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/file-storage" element={<StorageZones />} />
          <Route path="/admin/users" element={<UserManagement />} />
          <Route path="/admin/audit" element={<AuditLogs />} />
          <Route path="/admin/forms" element={<FormTemplates />} />
          <Route path="/admin/forms/builder" element={<FormBuilder />} />
          <Route path="/admin/forms/builder/:id" element={<FormBuilder />} />
          <Route path="/admin/storage-zones" element={<StorageZones />} />
        </Route>
      </Routes>
    </HashRouter>
  )
}

export default App