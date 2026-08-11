import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { App, Alert, Button, Card, Form, Select, Space, Table, Tag, Typography } from 'antd'
import { endOfMonth, format, startOfMonth } from 'date-fns'
import { clientService } from '../services/clientService'
import { projectService } from '../services/projectService'
import { teamworkIntegrationService } from '../services/teamworkIntegrationService'
import { teamworkTaskImportService } from '../services/teamworkTaskImportService'
import type { ClientListItem } from '../types/client'
import type { ProjectListItem } from '../types/project'
import type { TeamworkEntityMapping } from '../types/teamworkIntegration'
import type {
  TeamworkTaskImportDiagnosticRow, TeamworkTaskImportPreviewResult, TeamworkTaskImportConfirmResult,
} from '../types/teamworkTaskImport'

const { Title, Text } = Typography

// research.md Decisión 6: `date-fns` (ya aprobado) en vez de `DatePicker.RangePicker`/`dayjs` —
// `dayjs` es dependencia transitiva de `antd`, no resoluble como import directo bajo pnpm
// estricto (verificado contra el `node_modules` real del contenedor frontend).
const today = new Date()
const DEFAULT_DATE_FROM = format(startOfMonth(today), 'yyyy-MM-dd')
const DEFAULT_DATE_TO = format(endOfMonth(today), 'yyyy-MM-dd')

const BLOCK_REASON_TAG: Record<string, { color: string }> = {
  project_not_mapped: { color: 'orange' },
  tasklist_not_mapped: { color: 'orange' },
  assignee_not_mapped: { color: 'gold' },
}

export default function TeamworkTaskImporterPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()

  const [clients, setClients] = useState<ClientListItem[]>([])
  const [projects, setProjects] = useState<ProjectListItem[]>([])
  const [taskLists, setTaskLists] = useState<TeamworkEntityMapping[]>([])

  const [clientId, setClientId] = useState<string | undefined>()
  const [projectIds, setProjectIds] = useState<string[]>([])
  const [dateFrom, setDateFrom] = useState(DEFAULT_DATE_FROM)
  const [dateTo, setDateTo] = useState(DEFAULT_DATE_TO)
  const [taskListTeamworkId, setTaskListTeamworkId] = useState<string | undefined>()

  const [previewing, setPreviewing] = useState(false)
  const [preview, setPreview] = useState<TeamworkTaskImportPreviewResult | null>(null)
  const [importing, setImporting] = useState(false)
  const [confirmResult, setConfirmResult] = useState<TeamworkTaskImportConfirmResult | null>(null)

  useEffect(() => {
    clientService.list({ page_size: 500, active: true }).then(r => setClients(r.items))
      .catch(() => message.error('No se pudieron cargar los Clientes'))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Cascada Cliente→Proyecto, mismo patrón ya usado en el resto de SYTIX (ej. TicketsPage).
  useEffect(() => {
    setProjectIds([])
    setProjects([])
    if (!clientId) return
    projectService.list({ client_id: clientId, page_size: 500 }).then(r => setProjects(r.items))
      .catch(() => message.error('No se pudieron cargar los Proyectos'))
  }, [clientId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Lista de Tareas opcional: reutiliza GET /entity-mappings?entity_type=tasklist (ya trae
  // parent_context.project_id resuelto, spec 044) filtrado a los Proyectos ya elegidos — sin
  // endpoint nuevo (research.md Decisión 7).
  useEffect(() => {
    setTaskListTeamworkId(undefined)
    if (projectIds.length === 0) { setTaskLists([]); return }
    teamworkIntegrationService.listEntityMappings('tasklist').then(rows =>
      setTaskLists(rows.filter(r => r.parent_context?.project_id
        && projectIds.includes(r.parent_context.project_id))))
      .catch(() => message.error('No se pudieron cargar las Listas de Tareas'))
  }, [projectIds]) // eslint-disable-line react-hooks/exhaustive-deps

  const canRun = !!clientId && projectIds.length > 0

  const buildFilter = () => ({
    client_id: clientId as string,
    project_ids: projectIds,
    date_from: dateFrom || null,
    date_to: dateTo || null,
    task_list_teamwork_id: taskListTeamworkId ?? null,
  })

  const handlePreview = async () => {
    if (!canRun) return
    setPreviewing(true)
    setConfirmResult(null)
    try {
      setPreview(await teamworkTaskImportService.preview(buildFilter()))
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo prevalidar la importación')
    } finally {
      setPreviewing(false)
    }
  }

  const handleConfirm = async () => {
    if (!canRun) return
    setImporting(true)
    try {
      const result = await teamworkTaskImportService.confirm(buildFilter())
      setConfirmResult(result)
      message.success(`${result.summary.created} creadas, ${result.summary.updated} actualizadas, ` +
        `${result.summary.skipped} omitidas`)
      setPreview(null)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo ejecutar la importación')
    } finally {
      setImporting(false)
    }
  }

  // FR-021: el enlace de una fila bloqueada lleva a Integración Teamwork con el catálogo/fila
  // de la homologación faltante preseleccionados (leído por TeamworkIntegrationPage vía
  // `location.state`, sin nuevo query param — research.md Decisión 7).
  const handleResolveLink = (row: TeamworkTaskImportDiagnosticRow) => {
    if (!row.resolve_link) return
    navigate('/integraciones/teamwork', {
      state: { entityType: row.resolve_link.entity_type, teamworkId: row.resolve_link.teamwork_id },
    })
  }

  const diagnosticColumns = [
    { title: 'Tarea', dataIndex: 'name' },
    { title: 'ID Teamwork', dataIndex: 'teamwork_id', width: 110 },
    {
      title: 'Tipo', width: 100,
      render: (_: unknown, row: TeamworkTaskImportDiagnosticRow) =>
        row.is_subtask ? <Tag>Subtarea</Tag> : <Tag>Tarea</Tag>,
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Title level={3}>Importador de Tareas y Subtareas</Title>
      <Text type="secondary">
        Pantalla independiente de "Integración Teamwork" (que sincroniza los catálogos base): segmentá por
        Cliente, Proyecto(s), rango de fechas y opcionalmente una Lista de Tareas, prevalidá qué Tareas y
        Subtareas de Teamwork están listas para migrar, y ejecutá la importación por lotes.
      </Text>

      <Card title="Filtros">
        <Space wrap align="start" size="large">
          <Form.Item label="Cliente" required style={{ marginBottom: 0 }}>
            <Select
              style={{ width: 260 }} placeholder="Seleccionar Cliente" showSearch optionFilterProp="label"
              value={clientId} onChange={setClientId}
              options={clients.map(c => ({ value: c.id, label: c.name }))}
            />
          </Form.Item>
          <Form.Item label="Proyecto(s)" required style={{ marginBottom: 0 }}>
            <Select
              mode="multiple" style={{ minWidth: 260 }} placeholder="Seleccionar Proyecto(s)"
              showSearch optionFilterProp="label" disabled={!clientId}
              value={projectIds} onChange={setProjectIds}
              options={projects.map(p => ({ value: p.id, label: p.name }))}
            />
          </Form.Item>
          <Form.Item label="Fecha Inicio" style={{ marginBottom: 0 }}>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                  style={{ padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 6 }} />
          </Form.Item>
          <Form.Item label="Fecha Fin" style={{ marginBottom: 0 }}>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                  style={{ padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 6 }} />
          </Form.Item>
          <Form.Item label="Lista de Tareas (opcional)" style={{ marginBottom: 0 }}>
            <Select
              allowClear style={{ width: 220 }} placeholder="Todas" disabled={projectIds.length === 0}
              showSearch optionFilterProp="label"
              value={taskListTeamworkId} onChange={setTaskListTeamworkId}
              options={taskLists.map(t => ({ value: t.teamwork_id, label: t.teamwork_name ?? t.teamwork_id }))}
            />
          </Form.Item>
        </Space>
        <Space style={{ marginTop: 16 }}>
          <Button type="primary" disabled={!canRun} loading={previewing} onClick={handlePreview}>
            Prevalidar
          </Button>
          <Button disabled={!preview || preview.summary.ready === 0} loading={importing} onClick={handleConfirm}>
            Importar Lote
          </Button>
        </Space>
      </Card>

      {preview && (
        <Card title="Diagnóstico de Prevalidación">
          <Alert
            type="info" showIcon style={{ marginBottom: 16 }}
            message={`${preview.summary.ready} listas para migrar, ${preview.summary.blocked} bloqueadas ` +
              `(de ${preview.summary.total} totales)`}
          />
          {preview.blocked.length > 0 && (
            <>
              <Title level={5}>Bloqueadas</Title>
              <Table<TeamworkTaskImportDiagnosticRow>
                rowKey="teamwork_id" size="small" dataSource={preview.blocked} pagination={{ pageSize: 10 }}
                columns={[
                  ...diagnosticColumns,
                  {
                    title: 'Motivo',
                    render: (_: unknown, row: TeamworkTaskImportDiagnosticRow) => (
                      <Tag color={row.block_reason ? BLOCK_REASON_TAG[row.block_reason]?.color : undefined}>
                        {row.block_reason_label}
                      </Tag>
                    ),
                  },
                  {
                    title: 'Resolver', width: 120,
                    render: (_: unknown, row: TeamworkTaskImportDiagnosticRow) => (
                      <Button size="small" onClick={() => handleResolveLink(row)}>Homologar</Button>
                    ),
                  },
                ]}
              />
            </>
          )}
          {preview.ready.length > 0 && (
            <>
              <Title level={5} style={{ marginTop: 16 }}>Listas para migrar</Title>
              <Table<TeamworkTaskImportDiagnosticRow>
                rowKey="teamwork_id" size="small" dataSource={preview.ready} pagination={{ pageSize: 10 }}
                columns={diagnosticColumns}
              />
            </>
          )}
        </Card>
      )}

      {confirmResult && (
        <Card title="Resultado de la Importación">
          <Text>
            {confirmResult.summary.created} creadas, {confirmResult.summary.updated} actualizadas,{' '}
            {confirmResult.summary.skipped} omitidas
          </Text>
        </Card>
      )}
    </Space>
  )
}
