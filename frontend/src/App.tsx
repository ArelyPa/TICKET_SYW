import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { App as AntApp, ConfigProvider } from 'antd'
import esES from 'antd/locale/es_ES'
import { bindMessageApi } from './services/errorNotifier'
import LoginPage from './pages/LoginPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import DashboardPage from './pages/DashboardPage'
import ClientsPage from './pages/ClientsPage'
import ProjectsPage from './pages/ProjectsPage'
import ProjectListsPage from './pages/ProjectListsPage'
import ProjectPeoplePage from './pages/ProjectPeoplePage'
import TeamPage from './pages/TeamPage'
import SkillsPage from './pages/SkillsPage'
import RolesPermissionsPage from './pages/RolesPermissionsPage'
import SlaRulesPage from './pages/SlaRulesPage'
import ClientContactsPage from './pages/ClientContactsPage'
import AbsenceRequestsPage from './pages/AbsenceRequestsPage'
import CalendarPage from './pages/CalendarPage'
import WorkHourTemplatesPage from './pages/WorkHourTemplatesPage'
import TicketsPage from './pages/TicketsPage'
import MyTasksPage from './pages/MyTasksPage'
import KanbanPage from './pages/KanbanPage'
import TicketDetailPage from './pages/TicketDetailPage'
import AssignmentPanelPage from './pages/AssignmentPanelPage'
import CatalogsPage from './pages/CatalogsPage'
import MyProfilePage from './pages/MyProfilePage'
import WorkSessionsPage from './pages/WorkSessionsPage'
import TimeReportPage from './pages/TimeReportPage'
import ReportsPage from './pages/ReportsPage'
import TicketImportsPage from './pages/TicketImportsPage'
import TeamworkIntegrationPage from './pages/TeamworkIntegrationPage'
import TeamworkTaskImporterPage from './pages/TeamworkTaskImporterPage'
import TimeImportsPage from './pages/TimeImportsPage'
import ProtectedRoute from './components/common/ProtectedRoute'
import DefaultLanding from './components/common/DefaultLanding'
import EnvironmentBanner, { BANNER_WIDTH } from './components/common/EnvironmentBanner'
import { theme } from './theme'

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      >
        <Route index element={<DefaultLanding />} />
        <Route path="dashboard" element={<DefaultLanding />} />
        <Route path="me" element={<MyProfilePage />} />
        <Route path="tickets" element={<ProtectedRoute requiredPermission={{ module: 'tickets', action: ['view', 'view_own'] }}><TicketsPage /></ProtectedRoute>} />
        <Route path="my-tasks" element={<ProtectedRoute requiredPermission={{ module: 'tickets', action: ['view', 'view_own', 'view_assigned'] }}><MyTasksPage /></ProtectedRoute>} />
        <Route path="tickets/:id" element={<ProtectedRoute requiredPermission={{ module: 'tickets', action: ['view', 'view_own', 'view_assigned'] }}><TicketDetailPage /></ProtectedRoute>} />
        <Route path="kanban" element={<ProtectedRoute requiredPermission={{ module: 'tickets', action: ['view', 'view_assigned'] }}><KanbanPage /></ProtectedRoute>} />
        <Route path="assignment-panel" element={<ProtectedRoute requiredPermission={{ module: 'assignment_panel', action: 'view' }}><AssignmentPanelPage /></ProtectedRoute>} />
        <Route path="catalogs" element={<ProtectedRoute requiredPermission={{ module: 'catalogs', action: 'view' }} blockRoles={['Resolutor']}><CatalogsPage /></ProtectedRoute>} />
        <Route path="importacion-tareas" element={<ProtectedRoute requiredPermission={{ module: 'ticket_imports', action: 'run' }}><TicketImportsPage /></ProtectedRoute>} />
        <Route path="integraciones/teamwork" element={<ProtectedRoute requiredPermission={{ module: 'teamwork_integration', action: 'manage' }}><TeamworkIntegrationPage /></ProtectedRoute>} />
        <Route path="integraciones/teamwork/importador-tareas" element={<ProtectedRoute requiredPermission={{ module: 'teamwork_integration', action: 'operate' }}><TeamworkTaskImporterPage /></ProtectedRoute>} />
        <Route path="importacion-tiempos" element={<ProtectedRoute requiredPermission={{ module: 'teamwork_integration', action: 'operate' }}><TimeImportsPage /></ProtectedRoute>} />
        <Route path="registro-tiempos" element={<ProtectedRoute requiredPermission={{ module: 'work_sessions', action: 'view_own' }}><WorkSessionsPage /></ProtectedRoute>} />
        <Route path="reporte-tiempos" element={<ProtectedRoute requiredPermission={{ module: 'work_sessions', action: 'view_own' }}><TimeReportPage /></ProtectedRoute>} />
        <Route path="reportes" element={<ProtectedRoute requiredPermission={{ module: 'reports', action: 'view' }}><ReportsPage /></ProtectedRoute>} />
        <Route path="clients" element={<ProtectedRoute requiredPermission={{ module: 'clients', action: 'view' }} blockRoles={['Resolutor']}><ClientsPage /></ProtectedRoute>} />
        <Route path="projects" element={<ProtectedRoute requiredPermission={{ module: 'projects', action: 'view' }} blockRoles={['Resolutor']}><ProjectsPage /></ProtectedRoute>} />
        <Route path="projects/:projectId/lists" element={<ProtectedRoute requiredPermission={{ module: 'tickets', action: 'create' }}><ProjectListsPage /></ProtectedRoute>} />
        <Route path="projects/:projectId/people" element={<ProtectedRoute requiredPermission={{ module: 'projects', action: 'view' }}><ProjectPeoplePage /></ProtectedRoute>} />
        <Route path="team" element={<ProtectedRoute requiredPermission={{ module: 'resources', action: 'view' }} blockRoles={['Resolutor']}><TeamPage /></ProtectedRoute>} />
        <Route path="resources" element={<Navigate to="/team" replace />} />
        <Route path="users" element={<Navigate to="/team" replace />} />
        <Route path="skills" element={<ProtectedRoute requiredPermission={{ module: 'skills', action: 'view' }} blockRoles={['Resolutor']}><SkillsPage /></ProtectedRoute>} />
        <Route path="roles" element={<ProtectedRoute requiredPermission={{ module: 'roles', action: 'view' }}><RolesPermissionsPage /></ProtectedRoute>} />
        <Route path="sla-rules" element={<ProtectedRoute requiredPermission={{ module: 'sla_rules', action: 'manage' }}><SlaRulesPage /></ProtectedRoute>} />
        <Route path="client-contacts" element={<ProtectedRoute requiredPermission={{ module: 'client_contacts', action: 'manage' }}><ClientContactsPage /></ProtectedRoute>} />
        <Route path="absence-requests" element={<ProtectedRoute requiredPermission={{ module: 'absence_requests', action: 'create' }}><AbsenceRequestsPage /></ProtectedRoute>} />
        <Route path="calendar" element={<ProtectedRoute requiredPermission={{ module: 'resources', action: 'view' }}><CalendarPage /></ProtectedRoute>} />
        <Route path="rrhh/franjas-horarias" element={<ProtectedRoute requiredPermission={{ module: 'work_hour_templates', action: 'manage' }}><WorkHourTemplatesPage /></ProtectedRoute>} />
      </Route>
    </Routes>
  )
}

// Liga la instancia de mensajes del <App> de antd al notificador global de
// errores para que los toasts respeten tema y locale del ConfigProvider.
function MessageApiBinder() {
  const { message } = AntApp.useApp()
  useEffect(() => {
    bindMessageApi(message)
  }, [message])
  return null
}

export default function App() {
  return (
    <ConfigProvider locale={esES} theme={theme}>
      <AntApp>
        <MessageApiBinder />
        <EnvironmentBanner />
        <div style={{ paddingRight: BANNER_WIDTH }}>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </div>
      </AntApp>
    </ConfigProvider>
  )
}
