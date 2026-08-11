import type { TicketSlaState } from './sla'

/** Catálogo único de 10 estados, compartido por Ticket y Tarea/Subtarea (spec 009) — una
 * Tarea puede transicionar a cualquiera de ellos sin restricción de secuencia (ver
 * ticketService.changeStatus). */
export type TicketStatus =
  | 'nuevo' | 'pre_analisis' | 'contacto' | 'en_analisis' | 'en_ejecucion'
  | 'en_pruebas' | 'pendiente_usuario' | 'resuelto' | 'cerrado' | 'cancelado'

export type TicketType = 'incident' | 'evolutive' | 'preventive'
export type Priority = 'critical' | 'high' | 'medium' | 'low'
export type Severity = 's1' | 's2' | 's3' | 's4'
export type EscalationLevel = 'n1' | 'n2' | 'n3' | 'n4'

export const STATUS_LABELS: Record<TicketStatus, string> = {
  nuevo: 'Nuevo', pre_analisis: 'Pre-Análisis', contacto: 'Contacto',
  en_analisis: 'En Análisis', en_ejecucion: 'En Ejecución', en_pruebas: 'En Pruebas',
  pendiente_usuario: 'Pendiente de Usuario', resuelto: 'Resuelto',
  cerrado: 'Cerrado', cancelado: 'Cancelado',
}

export const TICKET_TYPE_LABELS: Record<TicketType, string> = {
  incident: 'Incidente', evolutive: 'Evolutivo', preventive: 'Preventivo',
}

export const PRIORITY_LABELS: Record<Priority, string> = {
  critical: 'Crítica', high: 'Alta', medium: 'Media', low: 'Baja',
}

export const SEVERITY_LABELS: Record<Severity, string> = {
  s1: 'S1', s2: 'S2', s3: 'S3', s4: 'S4',
}

export interface EntityRef {
  id: string
  name: string
}

export interface ResourceRef {
  id: string
  full_name: string
}

export interface TicketListItem {
  id: string
  ticket_number: string
  record_type_id: string
  ticket_type: TicketType
  title: string
  status: TicketStatus
  status_label: string
  priority: Priority
  severity: Severity
  escalation_level: EscalationLevel
  client: EntityRef | null
  project: EntityRef | null
  assignee: ResourceRef | null
  estimated_resolution_minutes: number | null
  /** Nombre de la Lista resuelto (spec 009 — reemplaza el texto libre de la spec 008). */
  list_name: string | null
  list_id: string | null
  /** Nombre resuelto del catálogo tipo de registro ("Ticket" | "Tarea") — usado para el tag
   * del Kanban y de "Mis Tareas" sin round-trip adicional (spec 009). */
  record_type: 'Ticket' | 'Tarea'
  /** Si no es null, este registro es una Subtarea (Nivel 5) de la Tarea indicada. */
  parent_task_id: string | null
  created_at: string
  /** Resumen de SLA (Fase 4, spec 014) — solo `phase`/`status`, sin el detalle completo. */
  sla: Pick<TicketSlaState, 'phase' | 'status'>
}

/** "125" min → "2h 05m"; null → '—'. Usado en el tablero Kanban. */
export function formatMinutes(minutes: number | null): string {
  if (minutes == null) return '—'
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h > 0 ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m`
}

/** Duración legible a partir de segundos (Historial de estados, spec 023). */
export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const d = Math.floor(totalMinutes / (60 * 24))
  const h = Math.floor((totalMinutes % (60 * 24)) / 60)
  const m = totalMinutes % 60
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`
  return `${m}m`
}

export type CommentType =
  | 'asignado' | 'pre_analisis' | 'confirmacion_atencion' | 'solicitud_informacion'
  | 'termina_analisis' | 'solicitud_cierre' | 'respuesta_usuario'
  | 'descripcion_solucion' | 'comentario_interno' | 'cancelacion'

export interface TicketAttachment {
  id: string
  filename: string
  content_type: string
  size_bytes: number
}

export interface TicketComment {
  id: string
  comment_type: CommentType
  comment_type_label: string
  visibility: 'internal' | 'external'
  body: string
  author_id: string
  is_automatic: boolean
  attachments: TicketAttachment[]
  created_at: string
}

export interface TicketTransition {
  id: string
  from_status: string
  to_status: string
  actor_id: string
  comment_id: string | null
  created_at: string
  /** Tiempo disponible transcurrido en el estado anterior (spec 023); `null` en la primera
   * transición del ticket. */
  elapsed_seconds: number | null
  /** Fase de SLA que esta transición cierra, o `null` si es una transición interna de una fase. */
  sla_phase_closed: 'contacto' | 'ejecucion' | null
  /** `true` = ✅ cumplió el SLA de esa fase, `false` = ⚠️/❌ lo incumplió, `null` = sin SLA aplicable. */
  sla_met: boolean | null
  /** `true` en la entrada de auditoría inicial (`from_status` sentinel `"creado"`, spec 038
   * FR-014) — se renderiza como creación, no como cambio de estado. */
  is_creation: boolean
}

export interface TicketReassignment {
  id: string
  actor_id: string
  previous_assignee_id: string | null
  previous_assignee_name: string | null
  new_assignee_id: string
  new_assignee_name: string
  reason: string | null
  created_at: string
}

export interface TicketAssignment {
  id: string
  assigner_id: string
  assignee_id: string
  resulting_status: string
  context: {
    assignee_skills: string[]
    assignee_open_tickets: number
    ticket_priority: string
    ticket_severity: string
  }
  created_at: string
}

export interface TicketRequester {
  id: string
  name: string
  is_encargado: boolean
}

export interface RelatedFromItem {
  id: string
  ticket_number: string
  title: string
  record_type: 'Ticket' | 'Tarea'
}

/** Skill requerido para resolver el ticket, opcional (spec 011). */
export interface TicketSkillRef {
  id: string
  code: string
  label: string
}

export interface TicketDetail extends TicketListItem {
  description: string
  /** Adjuntos de la descripción (spec 017) — independientes de los adjuntos de cada
   * comentario. Incluye tanto imágenes pegadas como archivos adjuntados manualmente. */
  description_attachments: TicketAttachment[]
  tool_id: string | null
  process_id: string | null
  estimated_resolution_minutes: number | null
  resolution_type_id: string | null
  related_ticket_id: string | null
  /** Registros (Ticket o Tarea) que referencian a este como "Registro relacionado" (Fase 3). */
  related_from: RelatedFromItem[]
  created_by: string
  /** Usuario/cliente solicitante asignado manualmente (Fase 2.2) — `null` si no hay o si `requester`
   * se resuelve automáticamente del creador (Fase 2.1). Editable solo cuando no es `null` o
   * cuando `requester` no viene de un creador con rol Usuario/cliente (ver TicketDetailPage). */
  client_contact_id: string | null
  requester: TicketRequester | null
  resolved_at: string | null
  resolution_accepted_at: string | null
  closed_at: string | null
  locked_fields: string[]
  close_eligible: boolean
  valid_actions: string[]
  comments: TicketComment[]
  transitions: TicketTransition[]
  assignments: TicketAssignment[]
  /** Reasignaciones de resolutor (spec 023) — "resolutor anterior ➡️ nuevo resolutor". */
  reassignments: TicketReassignment[]
  /** Subtareas (Nivel 5) de esta Tarea — vacío para Ticket y para Subtarea (spec 009). */
  subtasks: TicketListItem[]
  /** Resumen navegable de la Tarea padre (spec 036) — `null` salvo que este registro sea una Subtarea. */
  parent: { id: string; ticket_number: string; title: string } | null
  /** Skills requeridas para resolverlo, opcional y editable en cualquier estado (spec 011). */
  skills: TicketSkillRef[]
  /** Estado de SLA (Fase 4, spec 014) — 'sin_sla' para Tareas/Subtareas (FR-012). */
  sla: TicketSlaState
  /** Inicio efectivo del SLA persistido (spec 028, FR-005) — `null` si está pausado o sin SLA. */
  sla_effective_start: string | null
  /** Inicio de la jornada laboral aplicable, derivado desde la creación del ticket (spec 028,
   * FR-005, OBS-0040) — permite distinguir "cuándo se creó" de "cuándo empezó a correr el SLA". */
  work_period_start: string | null
  /** Origen Teamwork (spec 041) — ambos `null` salvo que el registro provenga de una
   * importación. `external_reference_url` es el enlace directo a la tarea original. */
  external_reference_id: string | null
  external_reference_url: string | null
}

export interface TicketFormData {
  title: string
  description: string
  /** Requeridos para todos los roles salvo Usuario/cliente (alta simplificada, Fase 2.1 US3):
   * el backend los completa automáticamente (incident/medium/s3 + cliente del Usuario/cliente). */
  ticket_type?: TicketType
  priority?: Priority
  severity?: Severity
  client_id?: string
  project_id?: string | null
  /** Usuario/cliente solicitante (Fase 2.2) — opcional, debe pertenecer al `client_id` elegido. */
  client_contact_id?: string | null
  tool_id?: string | null
  process_id?: string | null
  record_type_id?: string | null
  escalation_level?: EscalationLevel
  related_ticket_id?: string | null
  /** Lista real (spec 009) — solo tiene efecto en una Tarea. */
  list_id?: string | null
  /** Marca el registro como Subtarea de la Tarea indicada (spec 009, Nivel 5). */
  parent_task_id?: string | null
  /** Encargado de la Tarea/Subtarea (spec 009) — opcional, default: el propio creador. */
  assignee_id?: string | null
  /** Skills requeridas al crear (spec 011) — se aplican tras el `create()` vía el endpoint
   * dedicado `PATCH /api/tickets/{id}/skills` (research.md Decisión 2); no viaja en el POST. */
  skill_ids?: string[]
}

export interface TicketFilters {
  page?: number
  page_size?: number
  search?: string
  client_id?: string
  project_id?: string
  status?: TicketStatus[]
  priority?: Priority
  severity?: Severity
  ticket_type?: TicketType
  assignee_id?: string
  escalation_level?: EscalationLevel
  sort?: string
  /** Fase 4, spec 014 — indicadores agregados de SLA (Historia 3). */
  sla_status?: TicketSlaState['status']
  sla_expiring_within_hours?: number
}

export interface PanelRow {
  resource: ResourceRef
  counts: Partial<Record<TicketStatus, number>>
  total: number
}

export interface PanelData {
  matrix: PanelRow[]
  unassigned_new: Array<{
    id: string
    ticket_number: string
    title: string
    priority: Priority
    severity: Severity
    client: EntityRef | null
    created_at: string
  }>
  statuses: TicketStatus[]
  status_labels: Record<string, string>
}
