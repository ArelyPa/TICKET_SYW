import type { ReactNode } from 'react'
import { TeamOutlined, ProjectOutlined, UserOutlined, StarOutlined, DatabaseOutlined, SafetyCertificateOutlined, FileTextOutlined, DashboardOutlined, TagsOutlined, AppstoreOutlined, ClockCircleOutlined, BarChartOutlined, UnorderedListOutlined, FieldTimeOutlined, CalendarOutlined, IdcardOutlined, PieChartOutlined, ImportOutlined, ApiOutlined } from '@ant-design/icons'
import type { Permission } from '../types/api'

export interface NavLeaf {
  key: string
  icon: ReactNode
  label: string
  module: string
  /** Acción de permiso requerida para mostrar este ítem (default: 'view'). Puede ser una
   * lista — cualquiera de ellas habilita el ítem (ej. Tickets: 'view' o 'view_own'). */
  action?: string | string[]
}

export const MAESTROS_GROUP_KEY = 'maestros'

export const maestrosGroupIcon = <DatabaseOutlined />

export const maestrosNavItems: NavLeaf[] = [
  { key: '/clients', icon: <TeamOutlined />, label: 'Clientes', module: 'clients' },
  { key: '/projects', icon: <ProjectOutlined />, label: 'Proyectos', module: 'projects' },
  { key: '/team', icon: <UserOutlined />, label: 'Equipo', module: 'resources' },
  { key: '/skills', icon: <StarOutlined />, label: 'Skills', module: 'skills' },
  { key: '/roles', icon: <SafetyCertificateOutlined />, label: 'Roles y Permisos', module: 'roles' },
  { key: '/client-contacts', icon: <UserOutlined />, label: 'Usuarios/cliente', module: 'client_contacts', action: 'manage' },
  { key: '/sla-rules', icon: <FieldTimeOutlined />, label: 'SLA', module: 'sla_rules', action: 'manage' },
  { key: '/catalogs', icon: <TagsOutlined />, label: 'Catálogos', module: 'catalogs' },
  { key: '/importacion-tareas', icon: <ImportOutlined />, label: 'Importación de Tareas', module: 'ticket_imports', action: 'run' },
  { key: '/integraciones/teamwork', icon: <ApiOutlined />, label: 'Integración Teamwork', module: 'teamwork_integration', action: 'manage' },
  { key: '/integraciones/teamwork/importador-tareas', icon: <ImportOutlined />, label: 'Importador de Tareas y Subtareas', module: 'teamwork_integration', action: 'operate' },
  { key: '/importacion-tiempos', icon: <ImportOutlined />, label: 'Importación de Tiempos', module: 'teamwork_integration', action: 'operate' },
]

/** FR-006 (spec 038, US1): un Resolutor no debe descargar los catálogos administrativos
 * completos (Clientes, Proyectos, Equipo, Skills, Catálogos — Herramientas/Procesos/Tipos de
 * resolución/Tipos de acceso viven como pestañas dentro de este último) en su sesión — sigue
 * teniendo el permiso `view` de cada módulo porque lo necesita para selects acotados puntuales
 * (p. ej. Cliente/Proyecto al crear un ticket, `CreateTicketModal.tsx`), así que la restricción
 * es de navegación (oculta el ítem + bloquea la ruta), no de RBAC. Admin/Coordinador/QM no se
 * ven afectados — la restricción es explícitamente solo para Resolutor (FR-015: no fusionar
 * implícitamente las capacidades de Resolutor y QM).
 */
const RESOLUTOR_HIDDEN_MAESTROS_KEYS = new Set(['/clients', '/projects', '/team', '/skills', '/catalogs'])

/** Ítems de la Fase 1 — Tickets (van al nivel raíz del menú, antes de Maestros).
 *
 * `/tickets` (vista global) queda deliberadamente fuera de `view_assigned` — spec 038 US1
 * restringe esa vista a Coordinador/Admin (`view`) y Usuario/cliente (`view_own`); Resolutor
 * (solo `view_assigned`) conserva Kanban y Mis Tareas, ambos acotados a lo asignado a él. */
export const ticketsNavItems: NavLeaf[] = [
  { key: '/tickets', icon: <FileTextOutlined />, label: 'Tickets', module: 'tickets', action: ['view', 'view_own'] },
  { key: '/my-tasks', icon: <UnorderedListOutlined />, label: 'Mis Tareas', module: 'tickets', action: ['view', 'view_own', 'view_assigned'] },
  { key: '/kanban', icon: <AppstoreOutlined />, label: 'Kanban', module: 'tickets', action: ['view', 'view_assigned'] },
  { key: '/assignment-panel', icon: <DashboardOutlined />, label: 'Panel de Asignación', module: 'assignment_panel' },
]

/** Ítems de la Fase 2 — Registro de tiempos (van junto a los de Tickets). */
export const workSessionsNavItems: NavLeaf[] = [
  { key: '/registro-tiempos', icon: <ClockCircleOutlined />, label: 'Registro de Tiempos', module: 'work_sessions' },
  { key: '/reporte-tiempos', icon: <BarChartOutlined />, label: 'Reporte de Tiempos', module: 'work_sessions' },
]

/** Spec 034 — Módulo de Reportes Dinámicos (menú dedicado, solo Admin/Coordinador/QM). */
export const reportsNavItems: NavLeaf[] = [
  { key: '/reportes', icon: <PieChartOutlined />, label: 'Reportes', module: 'reports' },
]

export function getVisibleReportsNavItems(permissions: Permission[]): NavLeaf[] {
  return reportsNavItems.filter(item => hasNavAccess(permissions, item))
}

function hasNavAccess(permissions: Permission[], item: NavLeaf): boolean {
  const actions = Array.isArray(item.action) ? item.action : [item.action ?? 'view']
  return permissions.some(p => p.module === item.module && actions.includes(p.action))
}

/** Filtra los items de navegación por los permisos que tiene el usuario autenticado
 * (por defecto `view`; algunos ítems aceptan una lista de acciones alternativas). `roleName`
 * aplica además la restricción de FR-006 (spec 038) solo para Resolutor. */
export function getVisibleNavItems(permissions: Permission[], roleName?: string): NavLeaf[] {
  return maestrosNavItems
    .filter(item => hasNavAccess(permissions, item))
    .filter(item => roleName !== 'Resolutor' || !RESOLUTOR_HIDDEN_MAESTROS_KEYS.has(item.key))
}

export function getVisibleTicketNavItems(permissions: Permission[]): NavLeaf[] {
  return ticketsNavItems.filter(item => hasNavAccess(permissions, item))
}

/** work_sessions no usa la acción 'view' — cualquier permiso del módulo (view_own incluido,
 * que todos los roles internos tienen) habilita ver estas pantallas. */
export function getVisibleWorkSessionNavItems(permissions: Permission[]): NavLeaf[] {
  return workSessionsNavItems.filter(item =>
    permissions.some(p => p.module === item.module)
  )
}

/** Ítems de la Fase 5 (spec 020, Historia 2) — vacaciones y permisos. `create` lo tiene
 * cualquier rol interno vinculado a un Recurso (no `Encargado`, contacto externo).
 *
 * Spec 022 (FR-001): agrupados bajo el menú "RRHH" (mismo comportamiento visual que
 * "Maestros") junto con la administración de Franjas Horarias globales. */
export const RRHH_GROUP_KEY = 'rrhh'

export const rrhhGroupIcon = <IdcardOutlined />

export const absenceNavItems: NavLeaf[] = [
  { key: '/calendar', icon: <CalendarOutlined />, label: 'Calendario', module: 'resources', action: 'view' },
  { key: '/absence-requests', icon: <CalendarOutlined />, label: 'Permisos', module: 'absence_requests', action: 'create' },
]

export const rrhhNavItems: NavLeaf[] = [
  ...absenceNavItems,
  { key: '/rrhh/franjas-horarias', icon: <FieldTimeOutlined />, label: 'Franjas Horarias', module: 'work_hour_templates', action: 'manage' },
]

export function getVisibleAbsenceNavItems(permissions: Permission[]): NavLeaf[] {
  return absenceNavItems.filter(item => hasNavAccess(permissions, item))
}

export function getVisibleRrhhNavItems(permissions: Permission[]): NavLeaf[] {
  return rrhhNavItems.filter(item => hasNavAccess(permissions, item))
}
