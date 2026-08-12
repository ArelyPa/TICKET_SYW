import { useCallback, useEffect, useState } from 'react'
import { App, Button, Checkbox, Input, Row, Col, Select, Space, Table, Tooltip } from 'antd'
import {
  EyeOutlined, UserSwitchOutlined, InboxOutlined, ThunderboltOutlined,
  ClockCircleOutlined, CheckCircleOutlined, FieldTimeOutlined,
} from '@ant-design/icons'
import type { ColumnsType, TableProps } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import SortIndicator from '../components/tickets/SortIndicator'
import { ticketService } from '../services/ticketService'
import { clientService } from '../services/clientService'
import { resourceService } from '../services/resourceService'
import type {
  TicketListItem, TicketStatus, Priority, Severity,
} from '../types/ticket'
import { STATUS_LABELS, PRIORITY_LABELS, SEVERITY_LABELS } from '../types/ticket'
import type { ClientListItem } from '../types/client'
import type { Resource } from '../types/resource'
import { vivid } from '../theme'
import TicketStatusTag from '../components/tickets/TicketStatusTag'
import SlaStatusTag from '../components/tickets/SlaStatusTag'
import PriorityBadge from '../components/tickets/PriorityBadge'
import AssignModal from '../components/tickets/AssignModal'
import CreateTicketModal from '../components/tickets/CreateTicketModal'
import PageToolbar from '../components/common/PageToolbar'
import StatCard from '../components/common/StatCard'
import SavedFiltersBar from '../components/tickets/SavedFiltersBar'
import { textColumnFilter, serverColumnFilter } from '../components/common/columnFilters'
import { useAuthStore } from '../store/authStore'
import type { TicketFilterCriteria } from '../store/savedFiltersStore'

const IN_PROGRESS_STATUSES: TicketStatus[] = ['contacto', 'en_analisis', 'en_ejecucion', 'en_pruebas']

const statusOptions = Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }))
const priorityOptions = Object.entries(PRIORITY_LABELS).map(([value, label]) => ({ value, label }))
const severityOptions = Object.entries(SEVERITY_LABELS).map(([value, label]) => ({ value, label }))
const SLA_STATUS_OPTIONS = [
  { text: 'Corriendo', value: 'corriendo' },
  { text: 'Pausado', value: 'pausado' },
  { text: 'Vencido', value: 'vencido' },
  { text: 'Detenido', value: 'detenido' },
  { text: 'Sin SLA', value: 'sin_sla' },
]

export default function TicketsPage() {
  const { message } = App.useApp()
  const { hasPermission, role } = useAuthStore()
  const navigate = useNavigate()
  const canAssign = hasPermission('tickets', 'assign')
  /** Usuario/cliente (Fase 2.1 US3, renombrado spec 010): alta simplificada (solo título/descripción), sin acceso a
   * catálogos/clientes/recursos internos — el backend ya filtra su listado a lo propio. */
  const isEncargado = role?.name === 'Usuario/cliente'

  const [tickets, setTickets] = useState<TicketListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<TicketStatus[]>([])
  const [clientFilter, setClientFilter] = useState<string | undefined>()
  const [priorityFilter, setPriorityFilter] = useState<Priority | undefined>()
  const [severityFilter, setSeverityFilter] = useState<Severity | undefined>()
  const [assigneeFilter, setAssigneeFilter] = useState<string | undefined>()
  const [slaStatusFilter, setSlaStatusFilter] = useState<TicketListItem['sla']['status'] | undefined>()
  const [sort, setSort] = useState('urgency')
  // spec 046 (US6, FR-014): "Asignado a mí" — solo aplica al rol Usuario/cliente.
  const [mine, setMine] = useState(false)
  const [assigningId, setAssigningId] = useState<string | null>(null)
  const [stats, setStats] = useState<{ nuevo: number; enProgreso: number; pendienteUsuario: number; resuelto: number; vencenHoy: number } | null>(null)

  const [clients, setClients] = useState<ClientListItem[]>([])
  const [resources, setResources] = useState<Resource[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await ticketService.list({
        page, page_size: 20,
        search: search || undefined,
        status: statusFilter.length ? statusFilter : undefined,
        client_id: clientFilter,
        priority: priorityFilter,
        severity: severityFilter,
        assignee_id: assigneeFilter,
        sla_status: slaStatusFilter,
        sort,
        mine: isEncargado && mine ? true : undefined,
      })
      setTickets(res.items)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [page, search, statusFilter, clientFilter, priorityFilter, severityFilter, assigneeFilter, slaStatusFilter, sort, isEncargado, mine])

  useEffect(() => { load() }, [load])

  const loadStats = useCallback(async () => {
    try {
      const [nuevo, enProgreso, pendienteUsuario, resuelto, vencenHoy] = await Promise.all([
        ticketService.list({ status: ['nuevo'], page_size: 1 }).then(r => r.total),
        ticketService.list({ status: IN_PROGRESS_STATUSES, page_size: 1 }).then(r => r.total),
        ticketService.list({ status: ['pendiente_usuario'], page_size: 1 }).then(r => r.total),
        ticketService.list({ status: ['resuelto'], page_size: 1 }).then(r => r.total),
        ticketService.list({ sla_expiring_within_hours: 24, page_size: 1 }).then(r => r.total),
      ])
      setStats({ nuevo, enProgreso, pendienteUsuario, resuelto, vencenHoy })
    } catch {
      message.error('No se pudieron cargar las estadísticas de tickets')
    }
  }, [])

  useEffect(() => { loadStats() }, [loadStats])

  useEffect(() => {
    if (isEncargado) return  // sin permiso sobre clients/resources — alta simplificada
    clientService.list({ active: true, page_size: 100 }).then(r => setClients(r.items))
      .catch(() => message.error('No se pudo cargar la lista de clientes'))
    resourceService.list({ active: true, page_size: 100 }).then(r => setResources(r.items))
      .catch(() => message.error('No se pudo cargar la lista de recursos'))
  }, [isEncargado, message])

  const currentCriteria: TicketFilterCriteria = {
    search: search || undefined,
    status: statusFilter.length ? statusFilter : undefined,
    client_id: clientFilter,
    priority: priorityFilter,
    severity: severityFilter,
    assignee_id: assigneeFilter,
  }

  const applySavedFilter = (criteria: TicketFilterCriteria) => {
    setSearch(criteria.search ?? '')
    setStatusFilter(criteria.status ?? [])
    setClientFilter(criteria.client_id)
    setPriorityFilter(criteria.priority)
    setSeverityFilter(criteria.severity)
    setAssigneeFilter(criteria.assignee_id)
    setPage(1)
  }

  const handleTableChange: TableProps<TicketListItem>['onChange'] = (pagination, filters) => {
    setPage(pagination.current || 1)
    setClientFilter((filters.client?.[0] as string) || undefined)
    setStatusFilter((filters.status as TicketStatus[] | null) || [])
    setPriorityFilter((filters.priority?.[0] as Priority) || undefined)
    setSeverityFilter((filters.severity?.[0] as Severity) || undefined)
    setAssigneeFilter((filters.assignee?.[0] as string) || undefined)
    setSlaStatusFilter((filters.sla?.[0] as TicketListItem['sla']['status']) || undefined)
  }

  const columns: ColumnsType<TicketListItem> = [
    { title: 'Número', dataIndex: 'ticket_number', width: 110,
      render: (v: string, t: TicketListItem) => <a className="tabular-nums" onClick={() => navigate(`/tickets/${t.id}`, {
        state: { from: { pathname: '/tickets', label: 'Tickets' } },
      })}>{v}</a> },
    {
      title: 'Tipo', dataIndex: 'record_type', key: 'record_type', width: 105,
      render: (rt: TicketListItem['record_type'], t: TicketListItem) => {
        const isSubtask = rt === 'Tarea' && !!t.parent_task_id
        const chip = rt === 'Tarea' ? vivid.purple : vivid.blue
        return (
          <span style={{
            fontSize: 11, fontWeight: 700, padding: '1px 8px', borderRadius: 999,
            background: chip.bg, color: chip.text,
          }}>
            {isSubtask ? 'Subtarea' : rt}
          </span>
        )
      },
    },
    {
      title: 'Título', dataIndex: 'title', ellipsis: true,
      ...textColumnFilter('Buscar título o número...', search, setSearch),
    },
    {
      title: 'Cliente', dataIndex: ['client', 'name'], key: 'client', width: 160, ellipsis: true,
      ...serverColumnFilter(clients.map(c => ({ text: c.name, value: c.id })), clientFilter),
    },
    {
      title: 'Estado', dataIndex: 'status', key: 'status', width: 150,
      render: (s: TicketStatus) => <TicketStatusTag status={s} />,
      filters: statusOptions.map(o => ({ text: o.label, value: o.value })),
      filteredValue: statusFilter.length ? statusFilter : null,
      onFilter: () => true,
    },
    {
      title: 'SLA', dataIndex: 'sla', key: 'sla', width: 110,
      render: (sla: TicketListItem['sla']) => <SlaStatusTag status={sla.status} />,
      ...serverColumnFilter(SLA_STATUS_OPTIONS, slaStatusFilter),
    },
    {
      title: 'Prioridad', dataIndex: 'priority', key: 'priority', width: 125,
      render: (p: Priority) => <PriorityBadge priority={p} />,
      ...serverColumnFilter(priorityOptions.map(o => ({ text: o.label, value: o.value })), priorityFilter),
    },
    {
      title: 'Severidad', dataIndex: 'severity', key: 'severity', width: 120,
      render: (s: string) => s.toUpperCase(),
      ...serverColumnFilter(severityOptions.map(o => ({ text: o.label, value: o.value })), severityFilter),
    },
    {
      title: 'Asignado', dataIndex: ['assignee', 'full_name'], key: 'assignee', width: 160,
      render: (v: string | undefined) => v ?? <em>—</em>,
      ...serverColumnFilter(resources.map(r => ({ text: r.full_name, value: r.id })), assigneeFilter),
    },
    {
      title: 'Acciones', key: 'actions', width: 110,
      render: (_: unknown, t: TicketListItem) => (
        <Space>
          <Tooltip title="Ver detalle">
            <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/tickets/${t.id}`, {
              state: { from: { pathname: '/tickets', label: 'Tickets' } },
            })} />
          </Tooltip>
          {canAssign && (t.status === 'nuevo' || t.status === 'pre_analisis') && (
            <Tooltip title="Asignar (Triage)">
              <Button size="small" icon={<UserSwitchOutlined />} onClick={() => setAssigningId(t.id)} />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col xs={12} md={8} lg={4}>
          <StatCard label="Nuevos" value={stats?.nuevo ?? '—'} icon={<InboxOutlined />} color="blue" sub="Pendientes de triage" />
        </Col>
        <Col xs={12} md={8} lg={4}>
          {/* OBS-0051: "En progreso" se leía como si fuera un estado real del ciclo de vida;
             "Activos" deja claro que es un agregado, el subtítulo ya lista los estados que agrupa. */}
          <StatCard label="Activos" value={stats?.enProgreso ?? '—'} icon={<ThunderboltOutlined />} color="orange" sub="Contacto → En pruebas (varios estados)" />
        </Col>
        <Col xs={12} md={8} lg={4}>
          <StatCard label="Pend. usuario" value={stats?.pendienteUsuario ?? '—'} icon={<ClockCircleOutlined />} color="magenta" sub="SLA pausado (Fase 4)" />
        </Col>
        <Col xs={12} md={8} lg={4}>
          <StatCard label="Resueltos" value={stats?.resuelto ?? '—'} icon={<CheckCircleOutlined />} color="green" sub="Pendientes de cierre" />
        </Col>
        <Col xs={12} md={8} lg={4}>
          <StatCard label="Vencen hoy" value={stats?.vencenHoy ?? '—'} icon={<FieldTimeOutlined />} color="red"
            sub="SLA vence en menos de 24h" />
        </Col>
      </Row>

      {!isEncargado && (
        <div style={{ marginBottom: 12 }}>
          <SavedFiltersBar currentCriteria={currentCriteria} onApply={applySavedFilter} />
        </div>
      )}

      <PageToolbar
        filters={isEncargado
          ? <>
              <Input.Search placeholder="Buscar por título o número..." onSearch={setSearch} allowClear style={{ width: 240 }} />
              <Checkbox checked={mine} onChange={e => setMine(e.target.checked)}>Asignado a mí</Checkbox>
            </>
          : <>
              <Input.Search placeholder="Buscar por título o número..." onSearch={setSearch} allowClear style={{ width: 240 }} />
              <Select mode="multiple" placeholder="Estados" allowClear style={{ minWidth: 180 }}
                value={statusFilter} onChange={setStatusFilter} options={statusOptions} maxTagCount={2} />
              <Select placeholder="Cliente" allowClear showSearch optionFilterProp="label" style={{ width: 170 }}
                onChange={setClientFilter} options={clients.map(c => ({ value: c.id, label: c.name }))} />
              <Select placeholder="Prioridad" allowClear style={{ width: 120 }}
                onChange={setPriorityFilter} options={priorityOptions} />
              <Select placeholder="Asignado" allowClear showSearch optionFilterProp="label" style={{ width: 160 }}
                onChange={setAssigneeFilter} options={resources.map(r => ({ value: r.id, label: r.full_name }))} />
            </>}
        action={<CreateTicketModal onCreated={() => { load(); loadStats() }} />}
      />

      <div style={{ marginBottom: 8 }}><SortIndicator value={sort} onChange={setSort} /></div>
      <Table rowKey="id" columns={columns} dataSource={tickets} loading={loading}
        pagination={{ current: page, total, pageSize: 20 }} onChange={handleTableChange} />

      <AssignModal ticketId={assigningId} onClose={() => setAssigningId(null)} onAssigned={load} />
    </div>
  )
}
