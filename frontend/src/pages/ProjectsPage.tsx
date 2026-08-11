import { useEffect, useState } from 'react'
import { Button, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, Tooltip, message } from 'antd'
import { PlusOutlined, EditOutlined, StopOutlined, PlayCircleOutlined, UnorderedListOutlined, TeamOutlined, SyncOutlined } from '@ant-design/icons'
import type { ColumnsType, TableProps } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import { projectService } from '../services/projectService'
import { clientService } from '../services/clientService'
import { teamworkIntegrationService } from '../services/teamworkIntegrationService'
import type { ProjectListItem, ProjectFormData } from '../types/project'
import type { ClientListItem } from '../types/client'
import ConfirmationModal from '../components/common/ConfirmationModal'
import StatusTag from '../components/common/StatusTag'
import PageToolbar from '../components/common/PageToolbar'
import { textColumnFilter, serverColumnFilter } from '../components/common/columnFilters'
import { palette } from '../theme'
import { useAuthStore } from '../store/authStore'
import type { Rule } from 'antd/es/form'
import { mapApiErrorToFormFields, type FieldErrorRule } from '../services/formErrorMapper'

const ACTIVE_FILTER_OPTIONS = [{ text: 'Activo', value: 'true' }, { text: 'Inactivo', value: 'false' }]

// OBS-0018: asocia códigos de error de la API a los campos del formulario de Proyecto.
const PROJECT_ERROR_RULES: FieldErrorRule[] = [
  { code: 'name_duplicate', field: 'name' },
  { code: 'validation_error', field: 'name', messageIncludes: ['nombre del proyecto'] },
  { code: 'invalid_dates', field: 'end_date_estimated' },
  { code: 'invalid_start_date', field: 'start_date' },
]

// OBS-0011: mes actual en formato YYYY-MM, para comparar sin depender de zona horaria del navegador.
const _currentYearMonth = () => new Date().toISOString().slice(0, 7)

// OBS-0012: separador de miles (coma) + interpretación numérica sin ambigüedad con el punto decimal.
const formatThousands = (v?: number | string) =>
  (v === undefined || v === null || v === '') ? '' : `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
const parseThousands = (v?: string) => (v ? Number(v.replace(/,/g, '')) : 0)
const moneyRule: Rule = {
  validator: (_, value) =>
    (value === undefined || value === null || value >= 0)
      ? Promise.resolve()
      : Promise.reject(new Error('No puede ser negativo')),
}

export default function ProjectsPage() {
  const navigate = useNavigate()
  const { hasPermission } = useAuthStore()
  const canManage = hasPermission('projects', 'create') || hasPermission('projects', 'edit') || hasPermission('projects', 'deactivate')
  const canManageLists = hasPermission('tickets', 'create')
  const canSeeTeamworkBadge = hasPermission('teamwork_integration', 'operate')

  const [projects, setProjects] = useState<ProjectListItem[]>([])
  const [migratedProjectIds, setMigratedProjectIds] = useState<Set<string>>(new Set())
  const [clients, setClients] = useState<ClientListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [clientFilter, setClientFilter] = useState<string | undefined>()
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>()
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [confirmDeactivate, setConfirmDeactivate] = useState<string | null>(null)
  const [form] = Form.useForm<ProjectFormData>()

  const load = async () => {
    setLoading(true)
    try {
      const res = await projectService.list({
        page, page_size: 20, client_id: clientFilter, search: search || undefined, active: activeFilter,
      })
      setProjects(res.items)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    clientService.list({ active: true, page_size: 100 }).then(r => setClients(r.items))
      .catch(() => message.error('No se pudo cargar la lista de clientes'))
  }, [])

  // spec 044 US5: mismo criterio que ClientsPage.tsx — solo se consulta con permiso, evita un
  // toast de error 403 espurio para Resolutor/QM (research.md Decisión 7).
  useEffect(() => {
    if (!canSeeTeamworkBadge) return
    teamworkIntegrationService.getMigratedRefs('project').then(r => setMigratedProjectIds(new Set(r.sytix_ids)))
      .catch(() => {})
  }, [canSeeTeamworkBadge])

  useEffect(() => { load() }, [page, clientFilter, search, activeFilter])

  const handleTableChange: TableProps<ProjectListItem>['onChange'] = (pagination, filters) => {
    setPage(pagination.current || 1)
    setClientFilter((filters.client_name?.[0] as string) || undefined)
    const activeValue = filters.active?.[0] as string | undefined
    setActiveFilter(activeValue === undefined ? undefined : activeValue === 'true')
  }

  const openCreate = () => { form.resetFields(); setEditingId(null); setFormOpen(true) }
  const openEdit = (p: ProjectListItem) => {
    form.setFieldsValue({ ...p, start_date: p.start_date, end_date_estimated: p.end_date_estimated ?? undefined })
    setEditingId(p.id)
    setFormOpen(true)
  }

  const handleSubmit = async (values: ProjectFormData) => {
    try {
      if (editingId) {
        await projectService.update(editingId, values)
        message.success('Proyecto actualizado')
      } else {
        await projectService.create(values)
        message.success('Proyecto creado')
      }
      setFormOpen(false)
      load()
    } catch (err: unknown) {
      if (mapApiErrorToFormFields(err, form, PROJECT_ERROR_RULES)) return
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al guardar'
      message.error(msg)
    }
  }

  const handleDeactivate = async (id: string) => {
    try {
      await projectService.deactivate(id)
      message.success('Proyecto desactivado')
      setConfirmDeactivate(null)
      load()
    } catch {
      message.error('No se pudo desactivar el proyecto')
    }
  }

  const handleActivate = async (id: string) => {
    try {
      await projectService.activate(id)
      message.success('Proyecto activado')
      load()
    } catch {
      message.error('No se pudo activar el proyecto')
    }
  }

  const columns: ColumnsType<ProjectListItem> = [
    {
      title: 'Nombre', dataIndex: 'name', sorter: true, key: 'name',
      ...textColumnFilter('Buscar proyecto...', search, setSearch),
    },
    {
      title: 'Cliente', dataIndex: 'client_name', key: 'client_name',
      ...serverColumnFilter(clients.map(c => ({ text: c.name, value: c.id })), clientFilter),
    },
    { title: 'Inicio', dataIndex: 'start_date', render: (v: string) => <span className="tabular-nums">{v}</span> },
    { title: 'Fin estimado', dataIndex: 'end_date_estimated', render: (v: string | null) => <span className="tabular-nums">{v ?? '—'}</span> },
    {
      title: 'Estado', dataIndex: 'active', key: 'active',
      render: (v: boolean) => <StatusTag active={v} />,
      ...serverColumnFilter(ACTIVE_FILTER_OPTIONS, activeFilter === undefined ? undefined : String(activeFilter)),
    },
    ...(canSeeTeamworkBadge ? [{
      title: '', key: 'teamwork_origin',
      render: (_: unknown, r: ProjectListItem) => migratedProjectIds.has(r.id)
        ? <Tag icon={<SyncOutlined />} color="blue">Teamwork</Tag> : null,
    }] : []),
    {
      title: 'Acciones', key: 'actions',
      render: (_: unknown, r: ProjectListItem) => (
        <Space>
          {canManageLists && (
            <Tooltip title="Listas de tareas">
              <Button size="small" icon={<UnorderedListOutlined />} onClick={() => navigate(`/projects/${r.id}/lists`)} />
            </Tooltip>
          )}
          <Tooltip title="Personal del proyecto">
            <Button size="small" icon={<TeamOutlined />} onClick={() => navigate(`/projects/${r.id}/people`)} />
          </Tooltip>
          {canManage && <Tooltip title="Editar"><Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} /></Tooltip>}
          {canManage && (r.active
            ? <Tooltip title="Desactivar"><Button size="small" danger icon={<StopOutlined />} onClick={() => setConfirmDeactivate(r.id)} /></Tooltip>
            : <Tooltip title="Activar"><Button size="small" icon={<PlayCircleOutlined style={{ color: palette.green600 }} />} onClick={() => handleActivate(r.id)} /></Tooltip>)}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <PageToolbar
        filters={<>
          <Input.Search placeholder="Buscar proyecto..." onSearch={setSearch} allowClear style={{ width: 220 }} />
          <Select placeholder="Filtrar por cliente" allowClear style={{ width: 200 }} onChange={setClientFilter}
            options={clients.map(c => ({ value: c.id, label: c.name }))} />
        </>}
        action={canManage && <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>Nuevo proyecto</Button>}
      />

      <Table rowKey="id" columns={columns} dataSource={projects} loading={loading}
        pagination={{ current: page, total, pageSize: 20 }} onChange={handleTableChange} />

      <Modal title={editingId ? 'Editar proyecto' : 'Nuevo proyecto'} open={formOpen} onCancel={() => setFormOpen(false)} onOk={() => form.submit()} okText="Guardar">
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="client_id" label="Cliente" rules={[{ required: true, message: 'El cliente es requerido' }]}
            extra={editingId ? 'El cliente no se puede cambiar una vez creado el proyecto. Para moverlo a otro cliente, crea un proyecto nuevo.' : undefined}
          >
            <Select
              options={clients.map(c => ({ value: c.id, label: c.name }))}
              placeholder="Seleccionar cliente"
              showSearch
              optionFilterProp="label"
              filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
              disabled={!!editingId}
            />
          </Form.Item>
          <Form.Item name="name" label="Nombre" rules={[
            { required: true, message: 'El nombre es requerido' },
            { max: 150, message: 'Máximo 150 caracteres' },
            {
              validator: (_, value) =>
                !value || !/[!@#$%^&*+={}[\]|\\<>~`]/.test(value)
                  ? Promise.resolve()
                  : Promise.reject(new Error('El nombre contiene caracteres no permitidos')),
            },
          ]}>
            <Input maxLength={150} />
          </Form.Item>
          <Form.Item name="description" label="Descripción"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="overview" label="Overview del proyecto"><Input.TextArea rows={3} /></Form.Item>
          <Space style={{ display: 'flex' }} align="start">
            <Form.Item name="sale_services_usd" label="Venta servicios (USD)" rules={[moneyRule]}>
              <InputNumber style={{ width: 140 }} formatter={formatThousands} parser={parseThousands} />
            </Form.Item>
            <Form.Item name="sale_licenses_usd" label="Venta licencias (USD)" rules={[moneyRule]}>
              <InputNumber style={{ width: 140 }} formatter={formatThousands} parser={parseThousands} />
            </Form.Item>
            <Form.Item name="sale_subscriptions_usd" label="Suscripciones (USD)" rules={[moneyRule]}>
              <InputNumber style={{ width: 140 }} formatter={formatThousands} parser={parseThousands} />
            </Form.Item>
          </Space>
          <Form.Item name="components_sold" label="Componentes vendidos"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="start_date" label="Fecha de inicio" rules={[
            { required: true, message: 'La fecha de inicio es requerida' },
            {
              validator(_, value) {
                // OBS-0011: la regla de "no mes anterior" solo aplica al CREAR — al editar se
                // permite mantener proyectos ya cargados retroactivamente.
                if (editingId || !value) return Promise.resolve()
                return value.slice(0, 7) < _currentYearMonth()
                  ? Promise.reject(new Error('La fecha de inicio no puede estar en un mes anterior al actual'))
                  : Promise.resolve()
              },
            },
          ]}>
            <Input type="date" />
          </Form.Item>
          <Form.Item name="end_date_estimated" label="Fecha de fin estimada" dependencies={['start_date']} rules={[
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value) return Promise.resolve()
                const start = getFieldValue('start_date')
                if (start && new Date(value) <= new Date(start)) {
                  return Promise.reject(new Error('La fecha de fin debe ser posterior a la fecha de inicio'))
                }
                return Promise.resolve()
              },
            }),
          ]}>
            <Input type="date" />
          </Form.Item>
        </Form>
      </Modal>

      {confirmDeactivate && (
        <ConfirmationModal
          open
          title="Desactivar proyecto"
          description="¿Confirmas la desactivación de este proyecto? No aparecerá en la creación de nuevos tickets."
          onConfirm={() => handleDeactivate(confirmDeactivate)}
          onCancel={() => setConfirmDeactivate(null)}
        />
      )}
    </div>
  )
}
