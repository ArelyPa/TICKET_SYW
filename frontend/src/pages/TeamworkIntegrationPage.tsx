import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import {
  App, Badge, Button, Card, Form, Input, Segmented, Select, Space, Table, Tag, Typography, Modal, Alert,
} from 'antd'
import { SyncOutlined } from '@ant-design/icons'
import { teamworkIntegrationService } from '../services/teamworkIntegrationService'
import { resourceService } from '../services/resourceService'
import { projectService } from '../services/projectService'
import { clientService } from '../services/clientService'
import { taskListService } from '../services/taskListService'
import { roleService } from '../services/roleService'
import type {
  TeamworkIntegrationConfig, TeamworkIntegrationConfigInput, TeamworkEntityType,
  TeamworkEntityMapping, TeamworkCreateNewCandidates, TeamworkMigrationStatus, TeamworkTaskSyncResult,
} from '../types/teamworkIntegration'
import { TEAMWORK_ENTITY_TYPE_LABELS } from '../types/teamworkIntegration'

const { Title, Text } = Typography

const MATCH_METHOD_LABELS: Record<string, string> = {
  email: 'Correo', external_id: 'ID externo', name: 'Nombre exacto', manual: 'Manual',
  created_new: 'Creado desde Teamwork',
}

const MIGRATION_STATUS_BADGE: Record<TeamworkMigrationStatus, { color: string; text: string }> = {
  pending: { color: 'default', text: 'Pendiente' },
  linked: { color: 'blue', text: 'Homologado' },
  created: { color: 'green', text: 'Migrado' },
  inactive: { color: 'red', text: 'Inactivo' },
}

// spec 045 US1 (FR-003): pestañas de filtro por estado sobre el mismo Table ya existente.
const STATUS_TAB_OPTIONS: { value: TeamworkMigrationStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'pending', label: 'Pendientes' },
  { value: 'linked', label: 'Homologados' },
  { value: 'created', label: 'Migrados' },
  { value: 'inactive', label: 'Inactivos' },
]

const USUARIO_CLIENTE_ROLE_NAME = 'Usuario/cliente'

const NEW_ENTITY_PHRASE: Record<TeamworkEntityType, string> = {
  company: 'un Cliente nuevo', project: 'un Proyecto nuevo',
  person: 'una cuenta nueva', tasklist: 'una Lista de Tareas nueva',
}

const SYTIX_CANDIDATE_LOADER: Partial<Record<TeamworkEntityType, () => Promise<{ value: string; label: string }[]>>> = {
  person: () => resourceService.list({ page_size: 200 }).then(r => r.items.map(x => ({ value: x.id, label: x.full_name }))),
  // research.md Decisión 4: "Cliente - Proyecto" desambigua proyectos homónimos entre clientes.
  project: () => projectService.list({ page_size: 200 }).then(r => r.items.map(x => ({
    value: x.id, label: x.client_name ? `${x.client_name} - ${x.name}` : x.name,
  }))),
  company: () => clientService.list({ page_size: 200 }).then(r => r.items.map(x => ({ value: x.id, label: x.name }))),
}

const STATUS_BADGE: Record<string, { status: 'success' | 'error' | 'default'; text: string }> = {
  success: { status: 'success', text: 'Conexión exitosa' },
  auth_error: { status: 'error', text: 'Error de autenticación' },
  connection_error: { status: 'error', text: 'Error de conexión' },
}

const ENTITY_TYPES: TeamworkEntityType[] = ['company', 'project', 'person', 'tasklist']

function canMigrate(row: TeamworkEntityMapping): boolean {
  if (row.migration_status !== 'pending') return false
  if ((row.entity_type === 'project' || row.entity_type === 'tasklist')
      && row.parent_context?.status !== 'resolved') return false
  return true
}

export default function TeamworkIntegrationPage() {
  const { message } = App.useApp()
  const location = useLocation()
  const [form] = Form.useForm<TeamworkIntegrationConfigInput>()
  const [migrateForm] = Form.useForm<{ role_id?: string; client_id?: string }>()
  const [config, setConfig] = useState<TeamworkIntegrationConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<TeamworkEntityType | null>(null)
  const [mappingFilter, setMappingFilter] = useState<TeamworkEntityType>('person')
  const [mappings, setMappings] = useState<TeamworkEntityMapping[]>([])
  const [mappingsLoading, setMappingsLoading] = useState(false)
  const [candidateOptions, setCandidateOptions] = useState<{ value: string; label: string }[]>([])
  const [taskListCandidatesByProject, setTaskListCandidatesByProject] =
    useState<Record<string, { value: string; label: string }[]>>({})

  const [migrateTarget, setMigrateTarget] = useState<TeamworkEntityMapping | null>(null)
  const [migrateCandidates, setMigrateCandidates] = useState<TeamworkCreateNewCandidates | null>(null)
  const [migrateLoading, setMigrateLoading] = useState(false)
  const [migrateSubmitting, setMigrateSubmitting] = useState(false)
  const selectedRoleId = Form.useWatch('role_id', migrateForm)

  // ── Filtros superiores por Cliente/Proyecto (spec 044 US4) ───────────────
  const [clientFilterId, setClientFilterId] = useState<string | undefined>()
  const [projectFilterId, setProjectFilterId] = useState<string | undefined>()

  // ── Pestañas de estado (spec 045 US1, FR-003) ─────────────────────────────
  const [statusFilter, setStatusFilter] = useState<TeamworkMigrationStatus | 'all'>('all')

  // ── Enlace de resolución desde el Importador de Tareas (spec 045 US4, FR-021) ────────────
  const [teamworkIdSearch, setTeamworkIdSearch] = useState<string | undefined>()

  useEffect(() => {
    const navState = location.state as { entityType?: TeamworkEntityType; teamworkId?: string } | null
    if (navState?.entityType) {
      setMappingFilter(navState.entityType)
      setTeamworkIdSearch(navState.teamworkId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Acciones masivas de Personal (spec 044 US2) ──────────────────────────
  const [emailFilter, setEmailFilter] = useState('')
  const [selectedMappingIds, setSelectedMappingIds] = useState<string[]>([])
  const [bulkForm] = Form.useForm<{ role_id?: string; client_id?: string }>()
  const [bulkRoles, setBulkRoles] = useState<{ id: string; name: string }[]>([])
  const [bulkClients, setBulkClients] = useState<{ id: string; name: string }[]>([])
  const [bulkSubmitting, setBulkSubmitting] = useState(false)
  const bulkSelectedRoleId = Form.useWatch('role_id', bulkForm)
  const bulkSelectedRole = bulkRoles.find(r => r.id === bulkSelectedRoleId)
  const bulkRequiresClient = bulkSelectedRole?.name === USUARIO_CLIENTE_ROLE_NAME

  useEffect(() => {
    roleService.list({ page_size: 100, active: true }).then(r => setBulkRoles(r.items))
      .catch(() => message.error('No se pudieron cargar los roles'))
    clientService.list({ page_size: 500, active: true }).then(r => setBulkClients(r.items))
      .catch(() => message.error('No se pudieron cargar los clientes'))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Migración masiva de Tareas y Subtareas (spec 044 US3) ────────────────
  const [taskSyncing, setTaskSyncing] = useState(false)
  const [taskSyncResult, setTaskSyncResult] = useState<TeamworkTaskSyncResult | null>(null)

  const handleSyncTasks = async () => {
    setTaskSyncing(true)
    try {
      const result = await teamworkIntegrationService.syncTasks()
      setTaskSyncResult(result)
      message.success(`${result.created} creadas, ${result.updated} actualizadas, ${result.skipped.length} omitidas`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudieron migrar las Tareas y Subtareas')
    } finally {
      setTaskSyncing(false)
    }
  }

  const load = async () => {
    setLoading(true)
    try {
      const data = await teamworkIntegrationService.getConfig()
      setConfig(data)
      form.setFieldsValue({ site_url: data.site_url ?? '', environment: data.environment ?? 'test' })
    } catch {
      message.error('No se pudo cargar la configuración de Teamwork')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async (values: TeamworkIntegrationConfigInput) => {
    setSaving(true)
    try {
      const data = await teamworkIntegrationService.saveConfig(values)
      setConfig(data)
      form.setFieldValue('api_token', undefined)
      message.success('Configuración guardada')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo guardar la configuración')
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async () => {
    setTesting(true)
    try {
      const result = await teamworkIntegrationService.testConnection()
      setConfig(c => c ? { ...c, last_test_status: result.status, last_test_message: result.message } : c)
      if (result.status === 'success') message.success('Conexión exitosa')
      else message.error(result.message ?? 'No se pudo conectar con Teamwork')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo probar la conexión')
    } finally {
      setTesting(false)
    }
  }

  const handleSync = async (entityType: TeamworkEntityType) => {
    setSyncing(entityType)
    try {
      const result = await teamworkIntegrationService.syncCatalog(entityType)
      message.success(
        `${TEAMWORK_ENTITY_TYPE_LABELS[entityType]}: ${result.synced} sincronizados ` +
        `(${result.new} nuevos, ${result.updated} actualizados)`)
      if (entityType === mappingFilter) loadMappings(mappingFilter)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? `No se pudo sincronizar ${TEAMWORK_ENTITY_TYPE_LABELS[entityType]}`)
    } finally {
      setSyncing(null)
    }
  }

  const loadMappings = async (entityType: TeamworkEntityType) => {
    setMappingsLoading(true)
    try {
      setMappings(await teamworkIntegrationService.listEntityMappings(entityType))
    } catch {
      message.error('No se pudieron cargar las homologaciones')
    } finally {
      setMappingsLoading(false)
    }
  }

  useEffect(() => {
    loadMappings(mappingFilter)
    const loader = SYTIX_CANDIDATE_LOADER[mappingFilter]
    setCandidateOptions([])
    if (loader) loader().then(setCandidateOptions)
    setEmailFilter('')
    setSelectedMappingIds([])
    bulkForm.resetFields()
    setClientFilterId(undefined)
    setProjectFilterId(undefined)
  }, [mappingFilter]) // eslint-disable-line react-hooks/exhaustive-deps

  // spec 043 US2/research.md Decisión 7: las Listas de Tareas no tienen candidatos globales —
  // se cargan por Proyecto ya resuelto (`parent_context.project_id`) de las filas visibles.
  useEffect(() => {
    if (mappingFilter !== 'tasklist') return
    const projectIds = Array.from(new Set(
      mappings.map(m => m.parent_context?.project_id).filter((id): id is string => !!id)))
    if (projectIds.length === 0) { setTaskListCandidatesByProject({}); return }
    // research.md Decisión 4: los nombres de Lista de Tareas se repiten mucho entre proyectos
    // ("General Tasks" por defecto de Teamwork) — se prefija con Cliente y Proyecto ya
    // resueltos (`parent_context` de cualquier fila de ese proyecto) para desambiguar.
    Promise.all(projectIds.map(id => {
      const ctx = mappings.find(m => m.parent_context?.project_id === id)?.parent_context
      const prefix = ctx ? `${ctx.client_label} - ${ctx.project_label} - ` : ''
      return taskListService.listByProject(id).then(items =>
        [id, items.map(t => ({ value: t.id, label: `${prefix}${t.name}` }))] as const)
    }))
      .then(entries => setTaskListCandidatesByProject(Object.fromEntries(entries)))
      .catch(() => message.error('No se pudieron cargar las Listas de Tareas de los Proyectos resueltos'))
  }, [mappingFilter, mappings]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleManualMapping = async (mapping: TeamworkEntityMapping, sytixId: string | null) => {
    try {
      await teamworkIntegrationService.setEntityMapping(mapping.id, sytixId)
      loadMappings(mappingFilter)
    } catch {
      message.error('No se pudo guardar la homologación')
    }
  }

  const handleBulkMigrate = async (values: { role_id?: string; client_id?: string }) => {
    if (selectedMappingIds.length === 0 || !values.role_id) return
    setBulkSubmitting(true)
    try {
      const result = await teamworkIntegrationService.bulkCreateNew({
        mapping_ids: selectedMappingIds, role_id: values.role_id, client_id: values.client_id ?? null,
      })
      message.success(
        `${result.created.length} migrados` +
        (result.skipped.length ? `, ${result.skipped.length} omitidos` : ''))
      setSelectedMappingIds([])
      bulkForm.resetFields()
      loadMappings(mappingFilter)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo migrar el lote seleccionado')
    } finally {
      setBulkSubmitting(false)
    }
  }

  // spec 045 US2: "Migrar Masivamente como Nuevos" genérico (Empresas/Proyectos/Listas de Tareas,
  // sin Rol/Cliente — esos campos solo tienen sentido de negocio para Personal, ver handleBulkMigrate).
  const handleBulkMigrateGeneric = async () => {
    if (selectedMappingIds.length === 0) return
    setBulkSubmitting(true)
    try {
      const result = await teamworkIntegrationService.bulkCreateNew({ mapping_ids: selectedMappingIds })
      message.success(
        `${result.created.length} migrados` +
        (result.skipped.length ? `, ${result.skipped.length} omitidos` : ''))
      setSelectedMappingIds([])
      loadMappings(mappingFilter)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo migrar el lote seleccionado')
    } finally {
      setBulkSubmitting(false)
    }
  }

  // spec 045 US2 (FR-010): "Inactivar / Descartar Seleccionados" — disponible en los 4 catálogos.
  const handleBulkDiscard = async () => {
    if (selectedMappingIds.length === 0) return
    setBulkSubmitting(true)
    try {
      const result = await teamworkIntegrationService.bulkDiscard({ mapping_ids: selectedMappingIds })
      message.success(
        `${result.updated.length} inactivados` +
        (result.skipped.length ? `, ${result.skipped.length} omitidos` : ''))
      setSelectedMappingIds([])
      loadMappings(mappingFilter)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo inactivar el lote seleccionado')
    } finally {
      setBulkSubmitting(false)
    }
  }

  // spec 045 US2 (FR-006): revierte una fila Inactiva a Pendiente, sin límite de veces.
  const handleReactivate = async (mapping: TeamworkEntityMapping) => {
    try {
      await teamworkIntegrationService.bulkReactivate({ mapping_ids: [mapping.id] })
      loadMappings(mappingFilter)
    } catch {
      message.error('No se pudo reactivar el registro')
    }
  }

  const openMigrateModal = async (mapping: TeamworkEntityMapping) => {
    setMigrateTarget(mapping)
    setMigrateCandidates(null)
    migrateForm.resetFields()
    setMigrateLoading(true)
    try {
      const candidates = await teamworkIntegrationService.getCreateNewCandidates(mapping.id)
      setMigrateCandidates(candidates)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo preparar la migración')
      setMigrateTarget(null)
    } finally {
      setMigrateLoading(false)
    }
  }

  const closeMigrateModal = () => {
    setMigrateTarget(null)
    setMigrateCandidates(null)
    migrateForm.resetFields()
  }

  const handleMigrateConfirm = async (values: { role_id?: string; client_id?: string }) => {
    if (!migrateTarget) return
    setMigrateSubmitting(true)
    try {
      const result = await teamworkIntegrationService.createNew(migrateTarget.id, {
        role_id: values.role_id, client_id: values.client_id ?? null,
      })
      message.success(`"${result.created.name ?? ''}" migrado a SYTIX`)
      closeMigrateModal()
      loadMappings(mappingFilter)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo migrar el registro')
    } finally {
      setMigrateSubmitting(false)
    }
  }

  const badge = config?.last_test_status ? STATUS_BADGE[config.last_test_status] : null
  const connectionReady = config?.last_test_status === 'success'

  const selectedRole = migrateCandidates?.roles?.find(r => r.id === selectedRoleId)
  const requiresClient = selectedRole?.name === USUARIO_CLIENTE_ROLE_NAME

  // spec 045 US3 (FR-013 a FR-016): campos ampliados por entity_type, con "No informado" para
  // claves ausentes en `teamwork_metadata` — nunca en blanco indistinguible de un error.
  const renderMetaField = (row: TeamworkEntityMapping, key: string) => {
    const value = (row.teamwork_metadata as Record<string, string | undefined> | null)?.[key]
    return value ? value : <Text type="secondary">No informado</Text>
  }

  const extraColumns = (() => {
    if (mappingFilter === 'company') {
      return [{
        title: 'País', width: 110, render: (_: unknown, row: TeamworkEntityMapping) => renderMetaField(row, 'country'),
      }, {
        title: 'Dirección', width: 220,
        render: (_: unknown, row: TeamworkEntityMapping) => {
          const address = row.teamwork_metadata && 'address' in row.teamwork_metadata
            ? (row.teamwork_metadata as { address?: string }).address : undefined
          return address ? <Text ellipsis={{ tooltip: address }} style={{ maxWidth: 220 }}>{address}</Text>
            : <Text type="secondary">No informado</Text>
        },
      }, {
        title: 'Dominio', width: 160, render: (_: unknown, row: TeamworkEntityMapping) => renderMetaField(row, 'domain'),
      }, {
        title: 'Teléfono', width: 140, render: (_: unknown, row: TeamworkEntityMapping) => renderMetaField(row, 'phone'),
      }]
    }
    if (mappingFilter === 'project') {
      return [{
        title: 'Cliente Asociado', width: 200,
        render: (_: unknown, row: TeamworkEntityMapping) => {
          const ctx = row.parent_context
          if (!ctx || ctx.status === 'unmapped') return <Text type="secondary">Empresa sin sincronizar</Text>
          if (ctx.status === 'pending') return <Text type="warning">Pendiente de homologar la Empresa</Text>
          return ctx.client_label ?? '—'
        },
      }, ..._workItemMetaColumns()]
    }
    if (mappingFilter === 'tasklist') {
      return [{
        title: 'Cliente', width: 160,
        render: (_: unknown, row: TeamworkEntityMapping) => {
          const ctx = row.parent_context
          if (!ctx || ctx.status !== 'resolved') return <Text type="secondary">—</Text>
          return ctx.client_label ?? '—'
        },
      }, {
        title: 'Proyecto', width: 180,
        render: (_: unknown, row: TeamworkEntityMapping) => {
          const ctx = row.parent_context
          if (!ctx) return <Text type="secondary">—</Text>
          if (ctx.status === 'unmapped') return <Text type="secondary">Proyecto sin sincronizar</Text>
          if (ctx.status === 'pending') return <Text type="warning">Pendiente de homologar el Proyecto</Text>
          return ctx.project_label ?? '—'
        },
      }, ..._workItemMetaColumns()]
    }
    if (mappingFilter === 'person') {
      return [{
        title: 'Correo', dataIndex: 'teamwork_email', width: 220,
        render: (email: string | null) => email ?? <Text type="secondary">—</Text>,
      }, {
        title: 'Compañía/Empresa de Origen', width: 200,
        render: (_: unknown, row: TeamworkEntityMapping) => row.parent_context?.client_label ?? 'Sin compañía',
      }, {
        title: 'Cargo', width: 160, render: (_: unknown, row: TeamworkEntityMapping) => renderMetaField(row, 'job_title'),
      }, {
        title: 'Zona horaria', width: 140, render: (_: unknown, row: TeamworkEntityMapping) => renderMetaField(row, 'timezone'),
      }]
    }
    return []
  })()

  function _workItemMetaColumns() {
    return [{
      title: 'Estado', width: 110,
      render: (_: unknown, row: TeamworkEntityMapping) => {
        const status = (row.teamwork_metadata as { status?: string } | null)?.status
        if (!status) return <Text type="secondary">No informado</Text>
        return status === 'archived' ? <Tag color="default">Archivado</Tag> : <Tag color="green">Activo</Tag>
      },
    }, {
      title: 'Descripción', width: 220,
      render: (_: unknown, row: TeamworkEntityMapping) => {
        const description = (row.teamwork_metadata as { description?: string } | null)?.description
        return description
          ? <Text ellipsis={{ tooltip: description }} style={{ maxWidth: 220 }}>{description}</Text>
          : <Text type="secondary">No informado</Text>
      },
    }]
  }

  // spec 044 US4 (FR-002/003): filtros superiores por Cliente/Proyecto, client-side sobre
  // `parent_context` ya resuelto por el backend — Empresas no tiene bloque de filtros
  // (spec.md § Assumptions, no aplica: cada fila ya ES una Empresa).
  const clientFilterOptions = Array.from(new Map(
    mappings.filter(m => m.parent_context?.client_id)
      .map(m => [m.parent_context!.client_id as string, m.parent_context!.client_label as string])
  ).entries()).map(([value, label]) => ({ value, label }))

  const projectFilterOptions = Array.from(new Map(
    mappings.filter(m => m.parent_context?.project_id)
      .map(m => [m.parent_context!.project_id as string, m.parent_context!.project_label as string])
  ).entries()).map(([value, label]) => ({ value, label }))

  // spec 044 US2 (FR-007): filtro por patrón de correo, client-side, solo aplica a Personal.
  // spec 045 US1 (FR-005): la pestaña de estado se combina (AND) con el resto de filtros.
  const filteredMappings = mappings.filter(m => {
    if (teamworkIdSearch && m.teamwork_id !== teamworkIdSearch) return false
    if (statusFilter !== 'all' && m.migration_status !== statusFilter) return false
    if (mappingFilter === 'person' && emailFilter.trim()
        && !(m.teamwork_email ?? '').toLowerCase().includes(emailFilter.trim().toLowerCase())) return false
    if (clientFilterId && m.parent_context?.client_id !== clientFilterId) return false
    if (mappingFilter === 'tasklist' && projectFilterId && m.parent_context?.project_id !== projectFilterId) return false
    return true
  })

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Title level={3}>Integración Teamwork</Title>

      <Card title="Conexión">
        <Form form={form} layout="vertical" onFinish={handleSave} disabled={loading}>
          <Form.Item name="site_url" label="URL del Sitio Teamwork" rules={[{ required: true }]}>
            <Input placeholder="https://empresa.teamwork.com" />
          </Form.Item>
          <Form.Item name="api_token" label="API Token / Credenciales"
                    extra={config?.has_token ? 'Ya hay un token guardado — dejar en blanco para conservarlo' : undefined}>
            <Input.Password placeholder={config?.has_token ? '••••••••' : 'Token de API'} />
          </Form.Item>
          <Form.Item name="environment" label="Entorno" rules={[{ required: true }]} initialValue="test">
            <Select options={[{ value: 'test', label: 'Test' }, { value: 'production', label: 'Producción' }]} />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={saving}>Guardar</Button>
            <Button onClick={handleTestConnection} loading={testing} disabled={!config}>
              Probar Conexión
            </Button>
            {badge && <Badge status={badge.status} text={badge.text} />}
          </Space>
          {config?.last_test_message && (
            <div style={{ marginTop: 8 }}><Text type="danger">{config.last_test_message}</Text></div>
          )}
        </Form>
      </Card>

      <Card title="Sincronizar Catálogos">
        {!connectionReady && (
          <Text type="secondary">Probá la conexión con éxito para habilitar la sincronización.</Text>
        )}
        <Space wrap style={{ marginTop: connectionReady ? 0 : 12 }}>
          {ENTITY_TYPES.map(entityType => (
            <Button key={entityType} icon={<SyncOutlined />} disabled={!connectionReady}
                   loading={syncing === entityType} onClick={() => handleSync(entityType)}>
              {TEAMWORK_ENTITY_TYPE_LABELS[entityType]}
            </Button>
          ))}
        </Space>
      </Card>

      <Card title="Migrar Tareas y Subtareas">
        {!connectionReady && (
          <Text type="secondary">Probá la conexión con éxito para habilitar la migración.</Text>
        )}
        <Space direction="vertical" style={{ marginTop: connectionReady ? 0 : 12 }}>
          <Button icon={<SyncOutlined />} disabled={!connectionReady} loading={taskSyncing}
                 onClick={handleSyncTasks}>
            Migrar Tareas y Subtareas
          </Button>
          {taskSyncResult && (
            <div>
              <Text>
                {taskSyncResult.synced} recibidas — {taskSyncResult.created} creadas,{' '}
                {taskSyncResult.updated} actualizadas, {taskSyncResult.skipped.length} omitidas
              </Text>
              {taskSyncResult.skipped.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  {taskSyncResult.skipped.slice(0, 10).map(s => (
                    <div key={s.teamwork_id}>
                      <Text type="secondary">#{s.teamwork_id}: {s.reason}</Text>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Space>
      </Card>

      <Card title="Homologación de Entidades"
           extra={
             <Select<TeamworkEntityType> value={mappingFilter} onChange={setMappingFilter}
                    style={{ width: 220 }}
                    options={(['company', 'project', 'person', 'tasklist'] as TeamworkEntityType[])
                      .map(t => ({ value: t, label: TEAMWORK_ENTITY_TYPE_LABELS[t] }))} />
           }>
        {teamworkIdSearch && (
          <Alert
            type="info" showIcon closable style={{ marginBottom: 12 }}
            onClose={() => setTeamworkIdSearch(undefined)}
            message={`Mostrando la fila de Teamwork #${teamworkIdSearch} (enviado desde el Importador de Tareas)`}
          />
        )}
        <Segmented
          value={statusFilter}
          onChange={(value) => setStatusFilter(value as TeamworkMigrationStatus | 'all')}
          options={STATUS_TAB_OPTIONS.map(o => ({ value: o.value, label: o.label }))}
          style={{ marginBottom: 12 }}
        />
        <Space direction="vertical" style={{ width: '100%', marginBottom: 12 }}>
          {mappingFilter !== 'company' && (
            <Space wrap>
              {mappingFilter === 'person' && (
                <Input.Search
                  placeholder="Filtrar por correo..." allowClear style={{ width: 260 }}
                  value={emailFilter} onChange={e => setEmailFilter(e.target.value)}
                />
              )}
              <Select
                placeholder="Filtrar por Cliente" allowClear showSearch optionFilterProp="label"
                style={{ width: 220 }} value={clientFilterId} onChange={setClientFilterId}
                options={clientFilterOptions}
              />
              {mappingFilter === 'tasklist' && (
                <Select
                  placeholder="Filtrar por Proyecto" allowClear showSearch optionFilterProp="label"
                  style={{ width: 220 }} value={projectFilterId} onChange={setProjectFilterId}
                  options={projectFilterOptions}
                />
              )}
            </Space>
          )}
          {/* spec 045 US2: Acciones Masivas — "Migrar Masivamente como Nuevos" e
              "Inactivar / Descartar Seleccionados" disponibles en los 4 catálogos. */}
          {selectedMappingIds.length > 0 && (
            mappingFilter === 'person' ? (
              <Form form={bulkForm} layout="inline" onFinish={handleBulkMigrate} style={{ rowGap: 8 }}>
                <Text style={{ marginRight: 8 }}>{selectedMappingIds.length} seleccionados</Text>
                <Form.Item name="role_id" rules={[{ required: true, message: 'Elegí un rol' }]}>
                  <Select placeholder="Rol" style={{ width: 200 }}
                    options={bulkRoles.map(r => ({ value: r.id, label: r.name }))} />
                </Form.Item>
                {bulkRequiresClient && (
                  <Form.Item name="client_id" rules={[{ required: true, message: 'Elegí un Cliente' }]}>
                    <Select placeholder="Cliente" showSearch optionFilterProp="label" style={{ width: 220 }}
                      options={bulkClients.map(c => ({ value: c.id, label: c.name }))} />
                  </Form.Item>
                )}
                <Form.Item>
                  <Button type="primary" htmlType="submit" loading={bulkSubmitting}>
                    Migrar seleccionados
                  </Button>
                </Form.Item>
                <Form.Item>
                  <Button danger loading={bulkSubmitting} onClick={handleBulkDiscard}>
                    Inactivar / Descartar Seleccionados
                  </Button>
                </Form.Item>
              </Form>
            ) : (
              <Space wrap>
                <Text style={{ marginRight: 8 }}>{selectedMappingIds.length} seleccionados</Text>
                <Button type="primary" loading={bulkSubmitting} onClick={handleBulkMigrateGeneric}>
                  Migrar Masivamente como Nuevos
                </Button>
                <Button danger loading={bulkSubmitting} onClick={handleBulkDiscard}>
                  Inactivar / Descartar Seleccionados
                </Button>
              </Space>
            )
          )}
        </Space>
        <Table<TeamworkEntityMapping>
          rowKey="id"
          loading={mappingsLoading}
          dataSource={filteredMappings}
          pagination={{ pageSize: 15, showSizeChanger: false }}
          size="small"
          rowSelection={{
            selectedRowKeys: selectedMappingIds,
            onChange: (keys) => setSelectedMappingIds(keys as string[]),
            getCheckboxProps: (row: TeamworkEntityMapping) => ({ disabled: row.migration_status !== 'pending' }),
          }}
          columns={[
            { title: 'Teamwork', dataIndex: 'teamwork_name' },
            ...extraColumns,
            {
              title: 'SYTIX', render: (_: unknown, row) => {
                const options = mappingFilter === 'tasklist'
                  ? taskListCandidatesByProject[row.parent_context?.project_id ?? ''] ?? []
                  : candidateOptions
                const placeholder = mappingFilter === 'tasklist' && row.parent_context?.status !== 'resolved'
                  ? 'Resolvé el Proyecto primero' : 'Sin homologar'
                // research.md Decisión 4: ancho responsive (en vez de `width: 240` fijo) + title
                // nativo con la etiqueta completa, para que un texto largo ("Cliente - Proyecto -
                // Lista") no rompa el layout de la fila.
                const selectedLabel = options.find(o => o.value === row.sytix_id)?.label
                return (
                  <div style={{ minWidth: 240, maxWidth: 360 }} title={selectedLabel}>
                    <Select
                      style={{ width: '100%' }}
                      allowClear
                      showSearch
                      optionFilterProp="label"
                      placeholder={placeholder}
                      options={options}
                      value={row.sytix_id ?? undefined}
                      onChange={(value) => handleManualMapping(row, value ?? null)}
                      onClear={() => handleManualMapping(row, null)}
                    />
                  </div>
                )
              },
            },
            {
              title: 'Estado', dataIndex: 'migration_status', width: 130,
              render: (status: TeamworkMigrationStatus) => {
                const badgeInfo = MIGRATION_STATUS_BADGE[status]
                return <Tag color={badgeInfo.color === 'default' ? undefined : badgeInfo.color}>{badgeInfo.text}</Tag>
              },
            },
            {
              title: 'Método', dataIndex: 'match_method', width: 150,
              render: (method: string | null) => method
                ? <Tag>{MATCH_METHOD_LABELS[method] ?? method}</Tag>
                : <Tag>—</Tag>,
            },
            {
              title: 'Acciones', width: 160, render: (_: unknown, row: TeamworkEntityMapping) => (
                row.migration_status === 'inactive' ? (
                  <Button size="small" onClick={() => handleReactivate(row)}>
                    Reactivar
                  </Button>
                ) : (
                  <Button size="small" disabled={!canMigrate(row)} onClick={() => openMigrateModal(row)}>
                    Migrar como Nuevo
                  </Button>
                )
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="Migrar como Nuevo"
        open={!!migrateTarget}
        onCancel={closeMigrateModal}
        confirmLoading={migrateSubmitting}
        okButtonProps={{ disabled: migrateLoading || !migrateCandidates }}
        onOk={() => migrateForm.submit()}
      >
        {migrateTarget && (
          <Form form={migrateForm} layout="vertical" onFinish={handleMigrateConfirm} disabled={migrateLoading}>
            <Alert
              type="info" showIcon style={{ marginBottom: 16 }}
              message={`Se creará ${NEW_ENTITY_PHRASE[migrateTarget.entity_type]} en SYTIX con los datos de Teamwork.`}
            />
            <Form.Item label="Nombre / dato de Teamwork">
              <Input value={migrateCandidates?.defaults.name ?? migrateTarget.teamwork_name ?? ''} disabled />
            </Form.Item>
            {migrateTarget.entity_type === 'person' && (
              <>
                <Form.Item label="Correo">
                  <Input value={migrateCandidates?.defaults.email ?? ''} disabled />
                </Form.Item>
                <Form.Item name="role_id" label="Rol" rules={[{ required: true, message: 'Elegí un rol' }]}>
                  <Select
                    placeholder="Seleccionar rol"
                    options={(migrateCandidates?.roles ?? []).map(r => ({ value: r.id, label: r.name }))}
                  />
                </Form.Item>
                {requiresClient && (
                  <Form.Item name="client_id" label="Cliente" rules={[{ required: true, message: 'Elegí un Cliente' }]}>
                    <Select
                      placeholder="Seleccionar Cliente"
                      showSearch
                      optionFilterProp="label"
                      options={(migrateCandidates?.clients ?? []).map(c => ({ value: c.id, label: c.name }))}
                    />
                  </Form.Item>
                )}
              </>
            )}
          </Form>
        )}
      </Modal>
    </Space>
  )
}
