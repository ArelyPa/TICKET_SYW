import { useEffect, useRef, useState } from 'react'
import { Button, Col, Divider, Form, Input, InputNumber, Modal, Row, Select, Space, Table, Tabs, Tag, Tooltip, Upload, message } from 'antd'
import { PlusOutlined, EditOutlined, StopOutlined, PlayCircleOutlined, EyeInvisibleOutlined, EyeOutlined, DeleteOutlined, UploadOutlined, DownloadOutlined, SyncOutlined } from '@ant-design/icons'
import type { ColumnsType, TableProps } from 'antd/es/table'
import PhoneInput, { isValidPhoneNumber } from 'react-phone-number-input'
import 'react-phone-number-input/style.css'
import { clientService } from '../services/clientService'
import { catalogService } from '../services/catalogService'
import { CATALOG_COLOR_PALETTE } from '../types/catalog'
import { COUNTRIES } from '../data/countries'
import { TIMEZONES } from '../data/timezones'
import apiClient from '../services/apiClient'
import { teamworkIntegrationService } from '../services/teamworkIntegrationService'
import type {
  ClientListItem, ClientDetail, ClientFormData, ClientSystem, ClientSystemFormData,
  ClientAccess, ClientAccessFormData, ClientAccessCredential, ClientAccessCredentialFormData,
  ClientAccessAttachment, AccessTypeCatalogItem,
} from '../types/client'

const ENVIRONMENT_OPTIONS = [
  { value: 'dev', label: 'DEV' }, { value: 'test', label: 'TEST' }, { value: 'prod', label: 'PROD' },
]

function AccessTypeBadge({ type }: { type: AccessTypeCatalogItem }) {
  return (
    <Space size={6}>
      <span style={{
        display: 'inline-block', width: 10, height: 10, borderRadius: 3,
        background: CATALOG_COLOR_PALETTE[type.color_index % CATALOG_COLOR_PALETTE.length],
      }} />
      {type.name}
    </Space>
  )
}
import ConfirmationModal from '../components/common/ConfirmationModal'
import AccessCredentialForm from '../components/clients/AccessCredentialForm'
import { mapApiErrorToFormFields, type FieldErrorRule } from '../services/formErrorMapper'

// OBS-0018: asocia códigos de error de la API a los campos del formulario de Cliente.
const CLIENT_ERROR_RULES: FieldErrorRule[] = [
  { code: 'name_duplicate', field: 'name' },
  { code: 'validation_error', field: 'name', messageIncludes: ["'name'", 'nombre'] },
  { code: 'validation_error', field: 'contact_phone', messageIncludes: ['contact_phone'] },
]
import StatusTag from '../components/common/StatusTag'
import PageToolbar from '../components/common/PageToolbar'
import { textColumnFilter, serverColumnFilter } from '../components/common/columnFilters'
import { palette } from '../theme'
import { useAuthStore } from '../store/authStore'

const ACTIVE_FILTER_OPTIONS = [{ text: 'Activo', value: 'true' }, { text: 'Inactivo', value: 'false' }]

export default function ClientsPage() {
  const { hasPermission, role } = useAuthStore()
  const canManage = hasPermission('clients', 'create') || hasPermission('clients', 'edit') || hasPermission('clients', 'deactivate')
  const canSeeSensitive = role?.name === 'Admin' || role?.name === 'Coordinador'
  const canSeeTeamworkBadge = hasPermission('teamwork_integration', 'operate')

  const [clients, setClients] = useState<ClientListItem[]>([])
  const [migratedClientIds, setMigratedClientIds] = useState<Set<string>>(new Set())
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>()
  const [loading, setLoading] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [selectedDetail, setSelectedDetail] = useState<ClientDetail | null>(null)
  const [confirmDeactivate, setConfirmDeactivate] = useState<{ id: string; impact: string } | null>(null)
  const [systems, setSystems] = useState<ClientSystem[]>([])
  const [loadingSystems, setLoadingSystems] = useState(false)
  const [accessTypes, setAccessTypes] = useState<AccessTypeCatalogItem[]>([])
  const [accessList, setAccessList] = useState<ClientAccess[]>([])
  const [loadingAccess, setLoadingAccess] = useState(false)
  const [accessAttachments, setAccessAttachments] = useState<ClientAccessAttachment[]>([])
  const [editingAccessId, setEditingAccessId] = useState<string | null>(null)
  const [credentialsByAccess, setCredentialsByAccess] = useState<Record<string, ClientAccessCredential[]>>({})
  const [revealCredentialId, setRevealCredentialId] = useState<string | null>(null)
  const [editingCredential, setEditingCredential] = useState<{ accessId: string; credentialId: string } | null>(null)
  const [form] = Form.useForm<ClientFormData>()
  const [systemForm] = Form.useForm<ClientSystemFormData>()
  const [accessForm] = Form.useForm<ClientAccessFormData>()

  useEffect(() => { catalogService.list('access-types').then(res => setAccessTypes(res.items as AccessTypeCatalogItem[])) }, [])

  // spec 044 US5: distintivo de trazabilidad "Teamwork" — solo se consulta si el rol tiene
  // permiso de integración (Resolutor/QM ven esta pantalla pero no ese permiso, research.md
  // Decisión 7), evitando un toast de error 403 espurio en el uso diario.
  useEffect(() => {
    if (!canSeeTeamworkBadge) return
    teamworkIntegrationService.getMigratedRefs('client').then(r => setMigratedClientIds(new Set(r.sytix_ids)))
      .catch(() => {})
  }, [canSeeTeamworkBadge])

  const load = async () => {
    setLoading(true)
    try {
      const res = await clientService.list({ page, page_size: 20, search: search || undefined, active: activeFilter })
      setClients(res.items)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [page, search, activeFilter])

  const handleTableChange: TableProps<ClientListItem>['onChange'] = (pagination, filters) => {
    setPage(pagination.current || 1)
    const activeValue = filters.active?.[0] as string | undefined
    setActiveFilter(activeValue === undefined ? undefined : activeValue === 'true')
  }

  const openCreate = () => { form.resetFields(); setEditingId(null); setFormOpen(true) }
  const openEdit = (c: ClientListItem) => {
    form.resetFields()
    form.setFieldsValue(c)
    setEditingId(c.id)
    setFormOpen(true)
  }

  // spec 038 US6 (T039/T040): perfilado en DevTools/Network confirmó 4 peticiones secuenciales
  // (get + systems + access + access-attachments) disparadas al abrir el detalle, aunque solo
  // "Datos generales" (que no necesita ninguna de las otras 3) se ve por defecto — "Accesos y
  // conexiones" y "Portafolio de software" ahora se cargan recién al seleccionarlas
  // (`loadedTabsRef`, evita recargar si el usuario vuelve a una pestaña ya visitada).
  const loadedTabsRef = useRef<Set<string>>(new Set())

  const openDetail = async (id: string) => {
    // Se resetea el estado de inmediato (antes de esperar la respuesta) para no mostrar
    // residualmente los datos del cliente anterior mientras carga (UAT OBS-0008).
    setSelectedDetail(null)
    setSystems([])
    setAccessList([])
    setAccessAttachments([])
    setCredentialsByAccess({})
    setRevealCredentialId(null)
    setEditingAccessId(null)
    setEditingCredential(null)
    accessForm.resetFields()
    loadedTabsRef.current = new Set()
    const detail = await clientService.get(id)
    setSelectedDetail(detail)
    setDetailOpen(true)
  }

  const loadAccessTab = async (id: string) => {
    if (loadedTabsRef.current.has('access')) return
    loadedTabsRef.current.add('access')
    setLoadingAccess(true)
    try {
      const [access, attachments] = await Promise.all([
        clientService.listAccess(id), clientService.listAccessAttachments(id),
      ])
      setAccessList(access)
      setAccessAttachments(attachments)
    } finally {
      setLoadingAccess(false)
    }
  }

  const loadSystemsTab = async (id: string) => {
    if (loadedTabsRef.current.has('systems')) return
    loadedTabsRef.current.add('systems')
    setLoadingSystems(true)
    try {
      setSystems(await clientService.listSystems(id))
    } finally {
      setLoadingSystems(false)
    }
  }

  const handleDetailTabChange = (key: string) => {
    if (!selectedDetail) return
    if (key === 'access') loadAccessTab(selectedDetail.id)
    if (key === 'systems') loadSystemsTab(selectedDetail.id)
  }

  const handleAccessSubmit = async (values: ClientAccessFormData) => {
    if (!selectedDetail) return
    try {
      if (editingAccessId) {
        await clientService.updateAccess(selectedDetail.id, editingAccessId, values)
        message.success('Acceso actualizado')
      } else {
        await clientService.addAccess(selectedDetail.id, values)
        message.success('Acceso agregado')
      }
      accessForm.resetFields()
      setEditingAccessId(null)
      setAccessList(await clientService.listAccess(selectedDetail.id))
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al guardar el acceso'
      message.error(msg)
    }
  }

  const openEditAccess = (access: ClientAccess) => {
    setEditingAccessId(access.id)
    accessForm.setFieldsValue({
      access_type_id: access.access_type_id, environment: access.environment ?? undefined,
      port: access.port ?? undefined, host: access.host ?? undefined, notes: access.notes ?? undefined,
    })
  }

  const handleDeleteAccess = async (accessId: string) => {
    if (!selectedDetail) return
    await clientService.deleteAccess(selectedDetail.id, accessId)
    setAccessList(await clientService.listAccess(selectedDetail.id))
    message.success('Acceso eliminado')
  }

  const loadCredentials = async (accessId: string) => {
    if (!selectedDetail) return
    const items = await clientService.listCredentials(selectedDetail.id, accessId)
    setCredentialsByAccess(prev => ({ ...prev, [accessId]: items }))
  }

  const handleCredentialSubmit = async (accessId: string, values: ClientAccessCredentialFormData) => {
    if (!selectedDetail) return
    try {
      if (editingCredential && editingCredential.accessId === accessId) {
        await clientService.updateCredential(selectedDetail.id, accessId, editingCredential.credentialId, values)
        message.success('Credencial actualizada')
      } else {
        await clientService.addCredential(selectedDetail.id, accessId, values)
        message.success('Credencial agregada')
      }
      setEditingCredential(null)
      await loadCredentials(accessId)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al guardar la credencial'
      message.error(msg)
    }
  }

  const openEditCredential = (accessId: string, credential: ClientAccessCredential) => {
    setEditingCredential({ accessId, credentialId: credential.id })
  }

  const handleDeleteCredential = async (accessId: string, credentialId: string) => {
    if (!selectedDetail) return
    await clientService.deleteCredential(selectedDetail.id, accessId, credentialId)
    await loadCredentials(accessId)
    message.success('Credencial eliminada')
  }

  const handleUploadAccessAttachment = async (file: File, accessId?: string) => {
    if (!selectedDetail) return false
    try {
      await clientService.uploadAccessAttachment(selectedDetail.id, file, accessId)
      setAccessAttachments(await clientService.listAccessAttachments(selectedDetail.id))
      message.success('Adjunto subido')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al subir el adjunto'
      message.error(msg)
    }
    return false
  }

  const handleDeleteAccessAttachment = async (attachmentId: string) => {
    if (!selectedDetail) return
    await clientService.deleteAccessAttachment(selectedDetail.id, attachmentId)
    setAccessAttachments(await clientService.listAccessAttachments(selectedDetail.id))
    message.success('Adjunto eliminado')
  }

  const handleDownloadAccessAttachment = async (attachment: ClientAccessAttachment) => {
    if (!selectedDetail) return
    const url = clientService.downloadAccessAttachmentUrl(selectedDetail.id, attachment.id)
    const res = await apiClient.get(url, { responseType: 'blob' })
    const blobUrl = URL.createObjectURL(res.data as Blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = attachment.filename
    link.click()
    URL.revokeObjectURL(blobUrl)
  }

  const handleAddSystem = async (values: ClientSystemFormData) => {
    if (!selectedDetail) return
    try {
      await clientService.addSystem(selectedDetail.id, values)
      systemForm.resetFields()
      setSystems(await clientService.listSystems(selectedDetail.id))
      message.success('Sistema agregado')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al agregar el sistema'
      message.error(msg)
    }
  }

  const handleDeleteSystem = async (systemId: string) => {
    if (!selectedDetail) return
    await clientService.deleteSystem(selectedDetail.id, systemId)
    setSystems(await clientService.listSystems(selectedDetail.id))
    message.success('Sistema eliminado')
  }

  const handleSubmit = async (values: ClientFormData) => {
    try {
      if (editingId) {
        await clientService.update(editingId, values)
        message.success('Cliente actualizado')
      } else {
        await clientService.create(values)
        message.success('Cliente creado')
      }
      setFormOpen(false)
      load()
    } catch (err: unknown) {
      if (mapApiErrorToFormFields(err, form, CLIENT_ERROR_RULES)) return
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al guardar'
      message.error(msg)
    }
  }

  const handleDeactivate = async (id: string) => {
    const res = await clientService.deactivate(id)
    const impact = res.warning ?? 'Cliente desactivado'
    if (res.active_projects_count && res.active_projects_count > 0) {
      setConfirmDeactivate({ id, impact })
    } else {
      message.success('Cliente desactivado')
      load()
    }
  }

  const handleActivate = async (id: string) => {
    await clientService.activate(id)
    message.success('Cliente activado')
    load()
  }

  const columns: ColumnsType<ClientListItem> = [
    {
      title: 'Nombre', dataIndex: 'name', sorter: true, key: 'name',
      ...textColumnFilter('Buscar cliente...', search, setSearch),
    },
    { title: 'Contacto', dataIndex: 'contact_name' },
    { title: 'Email', dataIndex: 'contact_email' },
    {
      title: 'Estado', dataIndex: 'active', key: 'active',
      render: (v: boolean) => <StatusTag active={v} />,
      ...serverColumnFilter(ACTIVE_FILTER_OPTIONS, activeFilter === undefined ? undefined : String(activeFilter)),
    },
    ...(canSeeTeamworkBadge ? [{
      title: '', key: 'teamwork_origin',
      render: (_: unknown, record: ClientListItem) => migratedClientIds.has(record.id)
        ? <Tag icon={<SyncOutlined />} color="blue">Teamwork</Tag> : null,
    }] : []),
    {
      title: 'Acciones', key: 'actions',
      render: (_: unknown, record: ClientListItem) => (
        <Space>
          <Tooltip title="Ver detalle"><Button size="small" icon={<EyeOutlined />} onClick={() => openDetail(record.id)} /></Tooltip>
          {canManage && <Tooltip title="Editar"><Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} /></Tooltip>}
          {canManage && (record.active
            ? <Tooltip title="Desactivar"><Button size="small" danger icon={<StopOutlined />} onClick={() => handleDeactivate(record.id)} /></Tooltip>
            : <Tooltip title="Activar"><Button size="small" icon={<PlayCircleOutlined style={{ color: palette.green600 }} />} onClick={() => handleActivate(record.id)} /></Tooltip>)}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <PageToolbar
        filters={<Input.Search placeholder="Buscar cliente..." onSearch={setSearch} allowClear style={{ width: 300 }} />}
        action={canManage && <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>Nuevo cliente</Button>}
      />

      <Table
        rowKey="id"
        columns={columns}
        dataSource={clients}
        loading={loading}
        pagination={{ current: page, total, pageSize: 20 }}
        onChange={handleTableChange}
      />

      <Modal title={editingId ? 'Editar cliente' : 'Nuevo cliente'} open={formOpen} onCancel={() => setFormOpen(false)} onOk={() => form.submit()} okText="Guardar">
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="name" label="Nombre" rules={[
            { required: true, message: 'El nombre es requerido' },
            { max: 120, message: 'Máximo 120 caracteres' },
            {
              validator: (_, value) =>
                !value || /[\p{L}\p{N}]/u.test(value)
                  ? Promise.resolve()
                  : Promise.reject(new Error('El nombre debe contener al menos una letra o número')),
            },
          ]}>
            <Input maxLength={120} />
          </Form.Item>
          <Form.Item name="contact_name" label="Nombre de contacto"><Input /></Form.Item>
          <Form.Item
            name="contact_email" label="Email de contacto" rules={[{ type: 'email', message: 'Email inválido' }]}
            extra="No se verifica que el correo exista realmente, solo el formato."
          >
            <Input />
          </Form.Item>
          <Form.Item name="contact_phone" label="Teléfono" rules={[
            {
              validator: (_, value) =>
                !value || isValidPhoneNumber(value)
                  ? Promise.resolve()
                  : Promise.reject(new Error('Teléfono inválido')),
            },
          ]}>
            <PhoneInput
              defaultCountry="CO" international countryCallingCodeEditable={false} className="sw-phone-input"
              onChange={() => {}}
            />
          </Form.Item>
          <Form.Item name="annual_billing_usd" label="Facturación anual (USD)">
            <InputNumber min={0} style={{ width: '100%' }} formatter={v => `$ ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')} />
          </Form.Item>
          <Form.Item name="country" label="País" extra="Determina qué festivos se muestran en el Calendario del cliente.">
            <Select allowClear showSearch optionFilterProp="label" style={{ width: '100%' }}
              options={COUNTRIES.map(c => ({ value: c.code, label: c.name }))} />
          </Form.Item>
          <Form.Item name="timezone" label="Huso horario">
            <Select allowClear showSearch style={{ width: '100%' }}
              options={TIMEZONES.map(tz => ({ value: tz, label: tz }))} />
          </Form.Item>
          <Form.Item name="notes" label="Notas"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="Detalle del cliente" open={detailOpen} onCancel={() => setDetailOpen(false)} footer={null}
        width={selectedDetail ? '90vw' : 520} style={{ maxWidth: selectedDetail ? 1400 : undefined }}>
        {selectedDetail && (
          <Tabs
            onChange={handleDetailTabChange}
            items={[
              {
                key: 'general', label: 'Datos generales',
                children: (
                  // spec 035 (US4): layout horizontal en pantallas anchas (Row/Col), apilado
                  // legible en angostas (xs={24}) — mismos datos, sin campos nuevos.
                  <Row gutter={[24, 8]}>
                    <Col xs={24} md={12}>
                      <div><strong>Nombre:</strong> {selectedDetail.name}</div>
                      <div><strong>Contacto:</strong> {selectedDetail.contact_name}</div>
                      <div><strong>Email:</strong> {selectedDetail.contact_email}</div>
                    </Col>
                    <Col xs={24} md={12}>
                      <div><strong>Facturación anual (USD):</strong>{' '}
                        {selectedDetail.annual_billing_usd != null
                          ? `$ ${selectedDetail.annual_billing_usd.toLocaleString('en-US')}`
                          : '—'}
                      </div>
                      <div><strong>Notas:</strong> {selectedDetail.notes}</div>
                    </Col>
                  </Row>
                ),
              },
              {
                key: 'access', label: 'Accesos y conexiones',
                children: (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Table
                      rowKey="id"
                      size="small"
                      dataSource={accessList}
                      loading={loadingAccess}
                      pagination={false}
                      locale={{ emptyText: 'Sin accesos registrados' }}
                      expandable={{
                        onExpand: (expanded, row) => { if (expanded && !credentialsByAccess[row.id]) loadCredentials(row.id) },
                        expandedRowRender: (row: ClientAccess) => {
                          const credentials = credentialsByAccess[row.id] ?? []
                          const attachmentsForAccess = accessAttachments.filter(a => a.client_access_id === row.id)
                          const isEditingHere = editingCredential?.accessId === row.id
                          return (
                            <Space direction="vertical" style={{ width: '100%' }}>
                              <strong>Credenciales</strong>
                              <Table
                                rowKey="id" size="small" pagination={false}
                                dataSource={credentials}
                                locale={{ emptyText: 'Sin credenciales registradas' }}
                                columns={[
                                  { title: 'Etiqueta', dataIndex: 'label', render: (v: string | null) => v ?? '—' },
                                  { title: 'Usuario', dataIndex: 'username', render: (v: string | null) => canSeeSensitive ? (v ?? '—') : '—' },
                                  {
                                    title: 'Contraseña', dataIndex: 'password',
                                    render: (v: string | null, cred: ClientAccessCredential) => canSeeSensitive ? (
                                      <Space>
                                        {revealCredentialId === cred.id ? (v ?? '—') : '••••••••'}
                                        <Button size="small" type="link" icon={revealCredentialId === cred.id ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                                          onClick={() => setRevealCredentialId(id => id === cred.id ? null : cred.id)} />
                                      </Space>
                                    ) : '—',
                                  },
                                  { title: 'Notas', dataIndex: 'notes', render: (v: string | null) => v ?? '—' },
                                  ...(canManage ? [{
                                    title: '', key: 'actions',
                                    render: (_: unknown, cred: ClientAccessCredential) => (
                                      <Space>
                                        <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openEditCredential(row.id, cred)} />
                                        <Button size="small" danger type="text" icon={<DeleteOutlined />} onClick={() => handleDeleteCredential(row.id, cred.id)} />
                                      </Space>
                                    ),
                                  }] : []),
                                ]}
                              />
                              {canManage && (
                                <AccessCredentialForm
                                  key={row.id}
                                  accessId={row.id}
                                  editingCredential={isEditingHere
                                    ? credentials.find(c => c.id === editingCredential?.credentialId) ?? null
                                    : null}
                                  onSubmit={handleCredentialSubmit}
                                  onCancelEdit={() => setEditingCredential(null)}
                                />
                              )}
                              <strong>Adjuntos de este acceso</strong>
                              <Table
                                rowKey="id" size="small" pagination={false}
                                dataSource={attachmentsForAccess}
                                locale={{ emptyText: 'Sin adjuntos anclados a este acceso' }}
                                columns={[
                                  { title: 'Archivo', dataIndex: 'filename' },
                                  {
                                    title: '', key: 'actions',
                                    render: (_: unknown, a: ClientAccessAttachment) => (
                                      <Space>
                                        <Button size="small" type="text" icon={<DownloadOutlined />} onClick={() => handleDownloadAccessAttachment(a)} />
                                        {canManage && (
                                          <Button size="small" danger type="text" icon={<DeleteOutlined />} onClick={() => handleDeleteAccessAttachment(a.id)} />
                                        )}
                                      </Space>
                                    ),
                                  },
                                ]}
                              />
                              {canManage && (
                                <Upload beforeUpload={file => handleUploadAccessAttachment(file, row.id)} showUploadList={false}>
                                  <Button size="small" icon={<UploadOutlined />}>Adjuntar a este acceso</Button>
                                </Upload>
                              )}
                            </Space>
                          )
                        },
                      }}
                      columns={[
                        { title: 'Tipo', dataIndex: 'access_type', render: (v: AccessTypeCatalogItem) => <AccessTypeBadge type={v} /> },
                        { title: 'Ambiente', dataIndex: 'environment', render: (v: string | null) => v ? v.toUpperCase() : '—' },
                        { title: 'Puerto', dataIndex: 'port', render: (v: number | null) => v ?? '—' },
                        { title: 'Host/IP/URL', dataIndex: 'host' },
                        { title: 'Notas', dataIndex: 'notes' },
                        ...(canManage ? [{
                          title: '', key: 'actions',
                          render: (_: unknown, row: ClientAccess) => (
                            <Space>
                              <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openEditAccess(row)} />
                              <Button size="small" danger type="text" icon={<DeleteOutlined />} onClick={() => handleDeleteAccess(row.id)} />
                            </Space>
                          ),
                        }] : []),
                      ]}
                    />
                    {canManage && (
                      <Form form={accessForm} layout="inline" onFinish={handleAccessSubmit} style={{ marginTop: 8, rowGap: 8 }}>
                        <Form.Item name="access_type_id" rules={[{ required: true, message: 'Tipo requerido' }]}>
                          <Select placeholder="Tipo" style={{ width: 170 }}
                            options={accessTypes.map(t => ({ value: t.id, label: <AccessTypeBadge type={t} /> }))} />
                        </Form.Item>
                        <Form.Item name="environment">
                          <Select placeholder="Ambiente" allowClear style={{ width: 100 }} options={ENVIRONMENT_OPTIONS} />
                        </Form.Item>
                        <Form.Item name="port"><InputNumber placeholder="Puerto" min={1} style={{ width: 100 }} /></Form.Item>
                        <Form.Item name="host"><Input placeholder="Host/IP/URL" style={{ width: 160 }} /></Form.Item>
                        <Form.Item name="notes"><Input placeholder="Notas" style={{ width: 140 }} /></Form.Item>
                        <Form.Item>
                          <Space>
                            <Button htmlType="submit" icon={<PlusOutlined />}>{editingAccessId ? 'Guardar' : 'Agregar'}</Button>
                            {editingAccessId && (
                              <Button onClick={() => { setEditingAccessId(null); accessForm.resetFields() }}>Cancelar</Button>
                            )}
                          </Space>
                        </Form.Item>
                      </Form>
                    )}

                    <Divider style={{ margin: '12px 0' }}>Adjuntos generales (sin acceso asociado)</Divider>
                    <Table
                      rowKey="id"
                      size="small"
                      dataSource={accessAttachments.filter(a => !a.client_access_id)}
                      pagination={false}
                      locale={{ emptyText: 'Sin adjuntos generales' }}
                      columns={[
                        { title: 'Archivo', dataIndex: 'filename' },
                        {
                          title: '', key: 'actions',
                          render: (_: unknown, a: ClientAccessAttachment) => (
                            <Space>
                              <Button size="small" type="text" icon={<DownloadOutlined />} onClick={() => handleDownloadAccessAttachment(a)} />
                              {canManage && (
                                <Button size="small" danger type="text" icon={<DeleteOutlined />} onClick={() => handleDeleteAccessAttachment(a.id)} />
                              )}
                            </Space>
                          ),
                        },
                      ]}
                    />
                    {canManage && (
                      <Upload beforeUpload={file => handleUploadAccessAttachment(file)} showUploadList={false}>
                        <Button icon={<UploadOutlined />}>Adjuntar archivo general</Button>
                      </Upload>
                    )}
                  </Space>
                ),
              },
              {
                key: 'systems', label: 'Portafolio de software',
                children: (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Table
                      rowKey="id"
                      size="small"
                      dataSource={systems}
                      loading={loadingSystems}
                      pagination={false}
                      locale={{ emptyText: 'Sin sistemas registrados' }}
                      columns={[
                        { title: 'Tipo', dataIndex: 'system_type' },
                        { title: 'Marca', dataIndex: 'brand' },
                        { title: 'Versión', dataIndex: 'version' },
                        ...(canManage ? [{
                          title: '', key: 'del',
                          render: (_: unknown, s: ClientSystem) => (
                            <Button size="small" danger type="text" icon={<DeleteOutlined />} onClick={() => handleDeleteSystem(s.id)} />
                          ),
                        }] : []),
                      ]}
                    />
                    {canManage && (
                      <Form form={systemForm} layout="inline" onFinish={handleAddSystem} style={{ marginTop: 8 }}>
                        <Form.Item name="system_type" rules={[{ required: true, message: 'Tipo requerido' }]}>
                          <Select placeholder="Tipo" style={{ width: 110 }} options={['ERP', 'WMS', 'CRM', 'OTM', 'Otro'].map(v => ({ value: v, label: v }))} />
                        </Form.Item>
                        <Form.Item name="brand" rules={[{ required: true, message: 'Marca requerida' }]}>
                          <Input placeholder="Marca (ej. JD Edwards)" style={{ width: 170 }} />
                        </Form.Item>
                        <Form.Item name="version"><Input placeholder="Versión" style={{ width: 90 }} /></Form.Item>
                        <Form.Item><Button htmlType="submit" icon={<PlusOutlined />}>Agregar</Button></Form.Item>
                      </Form>
                    )}
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Modal>

      {confirmDeactivate && (
        <ConfirmationModal
          open
          title="Confirmar desactivación"
          description={confirmDeactivate.impact}
          onConfirm={() => { setConfirmDeactivate(null); load() }}
          onCancel={() => setConfirmDeactivate(null)}
        />
      )}
    </div>
  )
}
