import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Col, Descriptions, Divider, InputNumber, Row, Select, Space, Spin, Tag, Tooltip, Typography, message } from 'antd'
import {
  UserSwitchOutlined, SaveOutlined, ClockCircleOutlined, SwapOutlined,
  FieldTimeOutlined, PlayCircleOutlined, HistoryOutlined, UnorderedListOutlined, PaperClipOutlined,
  LinkOutlined,
} from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { ticketService } from '../services/ticketService'
import { catalogService } from '../services/catalogService'
import { clientContactService } from '../services/clientContactService'
import { taskListService } from '../services/taskListService'
import type { TicketDetail, TicketListItem, Priority, Severity } from '../types/ticket'
import { PRIORITY_LABELS, SEVERITY_LABELS, TICKET_TYPE_LABELS, formatMinutes, formatDuration } from '../types/ticket'
import type { ConsumptionLevel } from '../types/workSession'
import type { CatalogItem } from '../types/catalog'
import type { ClientContact } from '../types/clientContact'
import type { TaskList } from '../types/taskList'
import TicketStatusTag from '../components/tickets/TicketStatusTag'
import PriorityBadge from '../components/tickets/PriorityBadge'
import CommentThread from '../components/tickets/CommentThread'
import CommentComposer from '../components/tickets/CommentComposer'
import TaskStatusChanger from '../components/tickets/TaskStatusChanger'
import SubtaskList from '../components/tickets/SubtaskList'
import SlaCounter from '../components/tickets/SlaCounter'
import AssignModal from '../components/tickets/AssignModal'
import ReassignModal from '../components/tickets/ReassignModal'
import TicketSkillsSelector from '../components/tickets/TicketSkillsSelector'
import TicketWorkSessions from '../components/worksessions/TicketWorkSessions'
import TicketTimerWidget from '../components/worksessions/TicketTimerWidget'
import TicketBreadcrumb from '../components/tickets/TicketBreadcrumb'
import RichTextViewer from '../components/tickets/RichTextViewer'
import { useAuthStore } from '../store/authStore'
import { palette, vivid } from '../theme'

/** Colores del indicador de consumo estimado vs. real (Fase 2.2, US2 — research.md Decisión 6):
 * reutiliza los tokens ya existentes de la paleta, sin ampliarla. */
const CONSUMPTION_COLOR: Record<ConsumptionLevel, string> = {
  success: palette.green600,
  warning: palette.amber600,
  error: palette.red600,
  none: palette.slate400,
}

const CONSUMPTION_LABEL: Record<ConsumptionLevel, string> = {
  success: 'Consumo dentro de lo estimado',
  warning: 'Cerca del tiempo estimado',
  error: 'Tiempo estimado superado',
  none: '',
}

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { hasPermission } = useAuthStore()
  const canAssign = hasPermission('tickets', 'assign')
  const canEdit = hasPermission('tickets', 'edit')
  // OBS-0047/0048 (spec 033): permiso dedicado para "Skills requeridas" (solo Coordinador) —
  // Admin/QM ya no pueden editarlas aunque tengan tickets:edit.
  const canManageSkills = hasPermission('tickets', 'manage_skills')
  const canTrackTime = hasPermission('work_sessions', 'manage')

  const [ticket, setTicket] = useState<TicketDetail | null>(null)
  const [resolutionTypes, setResolutionTypes] = useState<CatalogItem[]>([])
  const [recordTypes, setRecordTypes] = useState<CatalogItem[]>([])
  const [assignOpen, setAssignOpen] = useState(false)
  const [reassignOpen, setReassignOpen] = useState(false)
  const [estimateHours, setEstimateHours] = useState<number | null>(null)
  const [priority, setPriority] = useState<Priority>()
  const [severity, setSeverity] = useState<Severity>()
  const [contacts, setContacts] = useState<ClientContact[]>([])
  const [clientContactId, setClientContactId] = useState<string | undefined>()
  const [taskLists, setTaskLists] = useState<TaskList[]>([])
  const [listId, setListId] = useState<string | undefined>()
  const [relatedOptions, setRelatedOptions] = useState<TicketListItem[]>([])
  const [relatedTicketId, setRelatedTicketId] = useState<string | undefined>()
  /** Fuerza el remount (y por lo tanto el refetch) de `TicketWorkSessions` cuando el
   * cronómetro (spec 012) termina y crea un Registro de tiempo nuevo — son componentes
   * hermanos, cada uno con su propio fetch independiente. */
  const [timerFinishedCount, setTimerFinishedCount] = useState(0)
  /** Revelado fluido del resumen de tiempo (Fase 2.2, US1 FR-004/FR-005): expandido por defecto
   * y al cerrar el modal de tiempo; se colapsa al hacer scroll hacia abajo, se re-expande al
   * volver a scrollear hacia arriba (ver research.md Decisión 2). */
  const [timeExpanded, setTimeExpanded] = useState(true)
  const [timeSummary, setTimeSummary] = useState<{ startDate: string | null; consumptionLevel: ConsumptionLevel }>(
    { startDate: null, consumptionLevel: 'none' },
  )

  useEffect(() => {
    let lastY = window.scrollY
    let ticking = false
    // Zona muerta: sin ella, micro-oscilaciones de scroll (rubber-band/trackpad) alternan
    // `timeExpanded` en sucesión rápida, cambiando la altura de "Registros de tiempo" y
    // empujando visualmente "Clasificación"/"Historial de estados" — el parpadeo reportado.
    const DEAD_ZONE = 12
    const onScroll = () => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        const y = window.scrollY
        const delta = y - lastY
        if (Math.abs(delta) > DEAD_ZONE) {
          if (delta > 0 && y > 80) setTimeExpanded(false)
          else if (delta < 0) setTimeExpanded(true)
          lastY = y
        }
        ticking = false
      })
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const load = useCallback(async () => {
    if (!id) return
    try {
      const data = await ticketService.get(id)
      setTicket(data)
      setEstimateHours(
        data.estimated_resolution_minutes != null ? data.estimated_resolution_minutes / 60 : null,
      )
      setPriority(data.priority)
      setSeverity(data.severity)
      setClientContactId(data.client_contact_id ?? undefined)
      setListId(data.list_id ?? undefined)
      setRelatedTicketId(data.related_ticket_id ?? undefined)
    } catch {
      message.error('No se pudo cargar el ticket')
    }
  }, [id])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    catalogService.list('resolution-types').then(r => setResolutionTypes(r.items))
      .catch(() => message.error('No se pudo cargar el catálogo de tipos de resolución'))
    catalogService.list('record-types', 'all').then(r => setRecordTypes(r.items))
      .catch(() => message.error('No se pudo cargar el catálogo de tipo de registro'))
  }, [])
  useEffect(() => {
    if (ticket?.client?.id) {
      ticketService.list({ client_id: ticket.client.id, page_size: 100 }).then(r => setRelatedOptions(r.items))
        .catch(() => message.error('No se pudo cargar la lista de registros del cliente'))
    }
  }, [ticket?.client?.id])
  useEffect(() => {
    /** Spec 010 (US2): el solicitante se alimenta del personal del Proyecto del ticket;
     * sin proyecto se mantiene la fuente por Cliente (spec 007). */
    if (ticket?.project?.id) {
      // Spec 034 (US1/FR-003): excluye cuentas deshabilitadas de nuevas asignaciones
      clientContactService.list({ project_id: ticket.project.id, page_size: 100, active: true }).then(r => setContacts(r.items))
        .catch(() => message.error('No se pudo cargar la lista de usuarios/cliente'))
    } else if (ticket?.client?.id) {
      clientContactService.list({ client_id: ticket.client.id, page_size: 100, active: true }).then(r => setContacts(r.items))
        .catch(() => message.error('No se pudo cargar la lista de usuarios/cliente'))
    }
  }, [ticket?.project?.id, ticket?.client?.id])
  useEffect(() => {
    if (ticket?.project?.id) {
      taskListService.listByProject(ticket.project.id).then(setTaskLists)
        .catch(() => message.error('No se pudo cargar la lista de Listas del proyecto'))
    }
  }, [ticket?.project?.id])

  if (!ticket) return <Spin style={{ display: 'block', margin: '80px auto' }} />

  const locked = new Set(ticket.locked_fields)
  /** Fase 2.2, FR-009: no editable cuando el solicitante se resolvió automáticamente del
   * creador (Usuario/cliente, autoservicio) — solo editable cuando es una asignación manual o cuando
   * todavía no hay ninguna. */
  const encargadoAutoDerivado = !ticket.client_contact_id && !!ticket.requester?.is_encargado
  const encargadoEditable = canEdit && !locked.has('client_contact_id') && !encargadoAutoDerivado
  /** spec 009: Tarea comparte el mismo ciclo de vida y campos de clasificación que Ticket
   * (revierte la spec 008) — isTask solo cambia el composer de estado y habilita Lista/Subtareas. */
  const isTask = recordTypes.find(rt => rt.id === ticket.record_type_id)?.name === 'Tarea'
  const isSubtask = isTask && !!ticket.parent_task_id
  const listEditable = canEdit && isTask && !locked.has('list_id') && !isSubtask
  const projectTaskLists = taskLists.filter(l => l.project_id === ticket.project?.id)

  const saveEditable = async () => {
    try {
      const payload: Record<string, unknown> = {}
      if (!locked.has('estimated_resolution_minutes')) {
        payload.estimated_resolution_minutes = estimateHours != null ? Math.round(estimateHours * 60) : null
      }
      if (!locked.has('priority')) payload.priority = priority
      if (!locked.has('severity')) payload.severity = severity
      if (encargadoEditable) payload.client_contact_id = clientContactId ?? null
      if (listEditable) payload.list_id = listId ?? null
      if (!locked.has('related_ticket_id')) payload.related_ticket_id = relatedTicketId ?? null
      await ticketService.update(ticket.id, payload)
      message.success('Ticket actualizado')
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al actualizar'
      message.error(msg)
    }
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap align="center">
        <TicketBreadcrumb />
        <span style={{ fontSize: 12, fontWeight: 700, color: vivid.blue.text, letterSpacing: 0.4 }}>
          {ticket.ticket_number}
        </span>
        <Typography.Title level={3} style={{ margin: 0 }}>{ticket.title}</Typography.Title>
        <TicketStatusTag status={ticket.status} />
        <span style={{
          fontSize: 11, fontWeight: 700, padding: '1px 8px', borderRadius: 999,
          background: isTask ? vivid.purple.bg : vivid.blue.bg,
          color: isTask ? vivid.purple.text : vivid.blue.text,
        }}>
          {isSubtask ? 'Subtarea' : isTask ? 'Tarea' : 'Ticket'}
        </span>
        <PriorityBadge priority={ticket.priority} full />
        {ticket.external_reference_id && (
          ticket.external_reference_url ? (
            <Tooltip title="Abrir la tarea original en Teamwork">
              <a href={ticket.external_reference_url} target="_blank" rel="noopener noreferrer">
                <Tag icon={<LinkOutlined />} color="cyan">Teamwork #{ticket.external_reference_id}</Tag>
              </a>
            </Tooltip>
          ) : (
            <Tag icon={<LinkOutlined />} color="cyan">Teamwork #{ticket.external_reference_id}</Tag>
          )
        )}
        {canAssign && !isTask && (ticket.status === 'nuevo' || ticket.status === 'pre_analisis') && (
          <Button type="primary" icon={<UserSwitchOutlined />} onClick={() => setAssignOpen(true)}>
            Asignar (Triage)
          </Button>
        )}
      </Space>

      <Row gutter={16}>
        {/* ── Columna principal: descripción → resumen de tiempo → clasificación → actividad
             (OBS-0042, spec 030: "Comentarios y acciones" se movió al sidebar) ── */}
        <Col xs={24} lg={14}>
          <Card title="Descripción" size="small">
            <RichTextViewer html={ticket.description} />
            {ticket.description_attachments.length > 0 && (
              <Space direction="vertical" size={2} style={{ marginTop: 8 }}>
                {ticket.description_attachments.map(a => (
                  <Typography.Link key={a.id}
                    onClick={() => ticketService.downloadAttachment(ticket.id, a.id, a.filename)}>
                    <PaperClipOutlined /> {a.filename} ({(a.size_bytes / 1024).toFixed(0)} KB)
                  </Typography.Link>
                ))}
              </Space>
            )}
          </Card>

          <Card
            size="small"
            title={<span><HistoryOutlined style={{ color: vivid.green.text, marginRight: 8 }} />Registros de tiempo</span>}
            style={{ marginTop: 16, transition: 'opacity 200ms cubic-bezier(0.23, 1, 0.32, 1)' }}
          >
            {canTrackTime && (
              <>
                <TicketTimerWidget
                  ticketId={ticket.id}
                  ticketStatus={ticket.status}
                  onFinished={() => setTimerFinishedCount(c => c + 1)}
                />
                <Divider style={{ margin: '12px 0' }} />
              </>
            )}
            <TicketWorkSessions
              key={timerFinishedCount}
              ticketId={ticket.id}
              ticketNumber={ticket.ticket_number}
              ticketTitle={ticket.title}
              estimatedMinutes={ticket.estimated_resolution_minutes}
              compact={!timeExpanded}
              onSummary={setTimeSummary}
              onModalClose={() => setTimeExpanded(true)}
            />
          </Card>

          <Card title="Clasificación" size="small" style={{ marginTop: 16 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Cliente">{ticket.client?.name}</Descriptions.Item>
              <Descriptions.Item label="Usuario/cliente solicitante">
                {encargadoEditable ? (
                  <Select
                    size="small" allowClear placeholder="Sin encargado asignado" style={{ width: 200 }}
                    value={clientContactId} onChange={setClientContactId}
                    options={contacts.map(c => ({ value: c.id, label: c.username }))}
                  />
                ) : ticket.requester?.is_encargado ? (
                  <span
                    style={{
                      display: 'inline-block', padding: '2px 10px', borderRadius: 999,
                      fontSize: 12, fontWeight: 600, background: vivid.purple.bg, color: vivid.purple.text,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {ticket.requester.name}
                  </span>
                ) : (
                  <em style={{ color: palette.slate400 }}>Sin encargado asignado</em>
                )}
              </Descriptions.Item>
              {isTask && (
                <Descriptions.Item label="Lista">
                  {listEditable
                    ? <Select size="small" allowClear placeholder="Sin lista" style={{ width: 200 }}
                        value={listId} onChange={setListId}
                        options={projectTaskLists.map(l => ({ value: l.id, label: l.name }))} />
                    : (ticket.list_name || <em style={{ color: palette.slate400 }}>Sin lista</em>)}
                </Descriptions.Item>
              )}
              {ticket.parent && (
                <Descriptions.Item label="Tarea Padre">
                  <Button type="link" size="small" style={{ padding: 0, height: 'auto' }}
                    onClick={() => navigate(`/tickets/${ticket.parent!.id}`)}>
                    {ticket.parent.ticket_number} — {ticket.parent.title}
                  </Button>
                </Descriptions.Item>
              )}
              {isTask && !isSubtask && (
                <Descriptions.Item label="Subtareas">
                  {ticket.subtasks.length === 0 ? (
                    <em style={{ color: palette.slate400 }}>Sin subtareas</em>
                  ) : (
                    <Space direction="vertical" size={2}>
                      {ticket.subtasks.map(s => (
                        <Button key={s.id} type="link" size="small" style={{ padding: 0, height: 'auto' }}
                          onClick={() => navigate(`/tickets/${s.id}`)}>
                          {s.ticket_number} — {s.title}
                        </Button>
                      ))}
                    </Space>
                  )}
                </Descriptions.Item>
              )}
              <Descriptions.Item label="Proyecto">{ticket.project?.name ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="Tipo de registro">
                {recordTypes.find(rt => rt.id === ticket.record_type_id)?.name ?? '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Registro relacionado">
                {canEdit && !locked.has('related_ticket_id') ? (
                  <Select
                    size="small" allowClear showSearch optionFilterProp="label"
                    placeholder="Sin registro relacionado" style={{ width: 220 }}
                    value={relatedTicketId} onChange={setRelatedTicketId}
                    options={relatedOptions.filter(t => t.id !== ticket.id)
                      .map(t => ({ value: t.id, label: `${t.ticket_number} — ${t.title}` }))}
                  />
                ) : ticket.related_ticket_id ? (
                  <Button type="link" size="small" style={{ padding: 0, height: 'auto' }}
                    onClick={() => navigate(`/tickets/${ticket.related_ticket_id}`)}>
                    Ver registro relacionado
                  </Button>
                ) : (
                  <em style={{ color: palette.slate400 }}>Sin registro relacionado</em>
                )}
              </Descriptions.Item>
              {ticket.related_from.length > 0 && (
                <Descriptions.Item label="Referenciado por">
                  <Space direction="vertical" size={2}>
                    {ticket.related_from.map(r => (
                      <Button key={r.id} type="link" size="small" style={{ padding: 0, height: 'auto' }}
                        onClick={() => navigate(`/tickets/${r.id}`)}>
                        {r.ticket_number} — {r.title} ({r.record_type})
                      </Button>
                    ))}
                  </Space>
                </Descriptions.Item>
              )}
              <Descriptions.Item label="Tipo">{TICKET_TYPE_LABELS[ticket.ticket_type]}</Descriptions.Item>
              <Descriptions.Item label="Nivel de escalamiento">{ticket.escalation_level.toUpperCase()}</Descriptions.Item>
              <Descriptions.Item label="Asignado">
                <Space size={8}>
                  {ticket.assignee?.full_name ?? 'Sin asignar'}
                  {canAssign && !isTask && ticket.assignee
                    && ticket.status !== 'cerrado' && ticket.status !== 'cancelado' && (
                    <Tooltip title="Reasignar a otro resolutor">
                      <Button size="small" icon={<SwapOutlined />} onClick={() => setReassignOpen(true)} />
                    </Tooltip>
                  )}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="Prioridad">
                {canEdit && !locked.has('priority')
                  ? <Select size="small" value={priority} onChange={setPriority} style={{ width: 120 }}
                      options={Object.entries(PRIORITY_LABELS).map(([v, l]) => ({ value: v, label: l }))} />
                  : <PriorityBadge priority={ticket.priority} full />}
              </Descriptions.Item>
              <Descriptions.Item label="Severidad">
                {canEdit && !locked.has('severity')
                  ? <Select size="small" value={severity} onChange={setSeverity} style={{ width: 90 }}
                      options={Object.entries(SEVERITY_LABELS).map(([v, l]) => ({ value: v, label: l }))} />
                  : ticket.severity.toUpperCase()}
              </Descriptions.Item>
              <Descriptions.Item label="Skills requeridas">
                <TicketSkillsSelector
                  ticketId={ticket.id} skills={ticket.skills} editable={canManageSkills}
                  onUpdated={skills => setTicket({ ...ticket, skills })}
                />
              </Descriptions.Item>
              <Descriptions.Item label="Fecha de inicio">
                {timeSummary.startDate
                  ? new Date(timeSummary.startDate).toLocaleDateString('es-CO')
                  : <em style={{ color: palette.slate400 }}>Aún sin iniciar</em>}
              </Descriptions.Item>
              <Descriptions.Item label="Tiempo estimado de solución">
                <Space size={8} align="center">
                  {canEdit && !locked.has('estimated_resolution_minutes')
                    ? <InputNumber size="small" min={0} step={0.5} addonAfter="h"
                        value={estimateHours} onChange={setEstimateHours} />
                    : (ticket.estimated_resolution_minutes != null
                        ? formatMinutes(ticket.estimated_resolution_minutes)
                        : 'Sin estimar')}
                  {timeSummary.consumptionLevel !== 'none' && (
                    <Tooltip title={CONSUMPTION_LABEL[timeSummary.consumptionLevel]}>
                      <span
                        style={{
                          display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                          background: CONSUMPTION_COLOR[timeSummary.consumptionLevel],
                        }}
                      />
                    </Tooltip>
                  )}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="Creado">{new Date(ticket.created_at).toLocaleString('es-CO')}</Descriptions.Item>
              {ticket.assignments.length > 0 && (
                <Descriptions.Item label="Asignado">
                  {new Date(ticket.assignments[ticket.assignments.length - 1].created_at).toLocaleString('es-CO')}
                </Descriptions.Item>
              )}
              {ticket.work_period_start && (
                <Descriptions.Item label="Inicio de jornada laboral">
                  {new Date(ticket.work_period_start).toLocaleString('es-CO')}
                </Descriptions.Item>
              )}
              {ticket.sla_effective_start && (
                <Descriptions.Item label="Inicio efectivo del SLA">
                  {new Date(ticket.sla_effective_start).toLocaleString('es-CO')}
                </Descriptions.Item>
              )}
              {ticket.resolved_at && (
                <Descriptions.Item label="Resuelto">{new Date(ticket.resolved_at).toLocaleString('es-CO')}</Descriptions.Item>
              )}
              {ticket.closed_at && (
                <Descriptions.Item label="Cerrado">{new Date(ticket.closed_at).toLocaleString('es-CO')}</Descriptions.Item>
              )}
            </Descriptions>
            {canEdit && (!locked.has('priority') || !locked.has('severity') || !locked.has('estimated_resolution_minutes') || !locked.has('related_ticket_id') || encargadoEditable || listEditable) && (
              <Button size="small" icon={<SaveOutlined />} onClick={saveEditable} style={{ marginTop: 8 }}>
                Guardar cambios
              </Button>
            )}
          </Card>

          <Card title="Historial de estados" size="small" style={{ marginTop: 16 }}>
            {ticket.transitions.length === 0
              ? <em>Sin transiciones todavía</em>
              : ticket.transitions.map(t => (
                <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, marginBottom: 6 }}>
                  {t.is_creation ? (
                    <>
                      <span>Ticket creado en estado</span>
                      <TicketStatusTag status={t.to_status as TicketDetail['status']} />
                    </>
                  ) : (
                    <>
                      <TicketStatusTag status={t.from_status as TicketDetail['status']} />
                      <span style={{ color: palette.slate400 }}>→</span>
                      <TicketStatusTag status={t.to_status as TicketDetail['status']} />
                    </>
                  )}
                  <span style={{ color: palette.slate400, marginLeft: 4 }}>{new Date(t.created_at).toLocaleString('es-CO')}</span>
                  {t.elapsed_seconds != null && (
                    <span style={{ color: palette.slate400 }}>· {formatDuration(t.elapsed_seconds)} en el estado anterior</span>
                  )}
                  {t.sla_met === true && (
                    <Tooltip title="Cumplió el SLA de esta fase">
                      <span>✅</span>
                    </Tooltip>
                  )}
                  {t.sla_met === false && (
                    <Tooltip title="Incumplió el SLA de esta fase">
                      <span>⚠️</span>
                    </Tooltip>
                  )}
                </div>
              ))}
          </Card>

          {ticket.reassignments.length > 0 && (
            <Card title="Reasignaciones" size="small" style={{ marginTop: 16 }}>
              {ticket.reassignments.map(r => (
                <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, marginBottom: 6, flexWrap: 'wrap' }}>
                  <span>{r.previous_assignee_name ?? 'Sin resolutor previo'}</span>
                  <span style={{ color: palette.slate400 }}>➡️</span>
                  <span>{r.new_assignee_name}</span>
                  <span style={{ color: palette.slate400, marginLeft: 4 }}>{new Date(r.created_at).toLocaleString('es-CO')}</span>
                  {r.reason && <span style={{ color: palette.slate400 }}>· {r.reason}</span>}
                </div>
              ))}
            </Card>
          )}
        </Col>

        {/* ── Sidebar: SLA / Focus Room / Comentarios y acciones (fijo, OBS-0042) / Subtareas ── */}
        <Col xs={24} lg={10}>
          <Card
            size="small"
            title={<span><ClockCircleOutlined style={{ color: vivid.red.text, marginRight: 8 }} />SLA</span>}
            style={{ borderColor: palette.slate200, background: palette.slate50 }}
          >
            <SlaCounter sla={ticket.sla} hasAssignee={ticket.assignee != null} />
          </Card>

          <Card
            size="small"
            title={<span><FieldTimeOutlined style={{ color: vivid.purple.text, marginRight: 8 }} />Sesión de trabajo (Focus Room)</span>}
            style={{ marginTop: 16, borderColor: palette.slate200, background: palette.slate50 }}
          >
            <div style={{ textAlign: 'center', padding: '4px 0 10px' }}>
              <div style={{ fontSize: 26, fontWeight: 700, color: palette.slate400, fontFamily: 'ui-monospace, monospace' }}>
                00:00:00
              </div>
              <div style={{ fontSize: 11, color: palette.slate400, marginBottom: 10 }}>
                Tiempo efectivo dedicado a este ticket
              </div>
              <Tooltip title="Modo de trabajo enfocado en un solo ticket, con asistente IA — llega en Fase 7">
                <Button size="small" icon={<PlayCircleOutlined />} disabled style={{ width: '100%' }}>
                  Iniciar sesión · Fase 7
                </Button>
              </Tooltip>
            </div>
          </Card>

          <Card
            title={isTask ? 'Estado y comentarios' : 'Comentarios y acciones'}
            size="small"
            style={{ marginTop: 16, position: 'sticky', top: 16 }}
          >
            {isTask && (
              <>
                <TaskStatusChanger ticket={ticket} onUpdated={load} />
                <Divider style={{ margin: '12px 0' }} />
              </>
            )}
            {/* OBS-0042 (spec 030): historial con scroll interno propio, acotado a un alto máximo,
             * para que la caja de nuevo comentario y las acciones de abajo queden siempre visibles. */}
            <div style={{ maxHeight: 420, overflowY: 'auto' }}>
              <CommentThread ticketId={ticket.id} comments={ticket.comments} />
            </div>
            <Divider style={{ margin: '12px 0' }} />
            <CommentComposer ticket={ticket} resolutionTypes={resolutionTypes} onUpdated={load}
              restrictToInternal={isTask} />
          </Card>

          {isTask && !isSubtask && (
            <Card
              size="small"
              title={<span><UnorderedListOutlined style={{ color: palette.slate400, marginRight: 8 }} />Subtareas ({ticket.subtasks.length})</span>}
              style={{ marginTop: 16, borderColor: palette.slate200, background: palette.slate50 }}
            >
              <SubtaskList ticket={ticket} onUpdated={load} />
            </Card>
          )}
        </Col>
      </Row>

      <AssignModal ticketId={assignOpen ? ticket.id : null}
        onClose={() => setAssignOpen(false)} onAssigned={load} />
      <ReassignModal ticketId={reassignOpen ? ticket.id : null}
        currentAssigneeId={ticket.assignee?.id ?? null}
        onClose={() => setReassignOpen(false)} onReassigned={load} />
    </div>
  )
}
