import { useEffect, useMemo, useState } from 'react'
import {
  Alert, Button, Checkbox, Collapse, Divider, Form, Input, InputNumber, Modal, Radio, Select,
  Space, Table, Tag, Tooltip, Typography, message,
} from 'antd'
import {
  PlusOutlined, EditOutlined, StopOutlined, PlayCircleOutlined, DollarOutlined,
  SettingOutlined, KeyOutlined, LockOutlined, UnlockOutlined, CopyOutlined, LinkOutlined,
  ClockCircleOutlined, SyncOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { resourceService, skillService } from '../services/resourceService'
import { userService } from '../services/userService'
import { roleService } from '../services/roleService'
import { catalogService } from '../services/catalogService'
import { teamworkIntegrationService } from '../services/teamworkIntegrationService'
import type { CatalogItem } from '../types/catalog'
import type { Resource, ResourceFormData, Skill, ResourceCompensation, CompensationFormData } from '../types/resource'
import type { UserAdmin } from '../types/user'
import type { RoleDetail } from '../types/role'
import { useAuthStore } from '../store/authStore'
import ConfirmationModal from '../components/common/ConfirmationModal'
import StatusTag from '../components/common/StatusTag'
import PageToolbar from '../components/common/PageToolbar'
import { clientColumnFilter, clientTextColumnFilter } from '../components/common/columnFilters'
import { palette, avatarColor, initials, roleColor } from '../theme'
import { COUNTRIES } from '../data/countries'
import { TIMEZONES } from '../data/timezones'
import WorkScheduleDrawer from '../components/resources/WorkScheduleDrawer'
import { format, subYears } from 'date-fns'
import { mapApiErrorToFormFields, type FieldErrorRule } from '../services/formErrorMapper'

const EDUCATION_LEVEL_OPTIONS = [
  'Bachiller', 'Técnico', 'Tecnólogo', 'Pregrado', 'Especialización', 'Maestría', 'Doctorado', 'Otro',
].map(v => ({ value: v, label: v }))

// OBS-0018: asocia códigos de error de la API a los campos del perfil de Recurso.
const RESOURCE_ERROR_RULES: FieldErrorRule[] = [
  { code: 'validation_error', field: 'identification', messageIncludes: ['identification'] },
  { code: 'validation_error', field: 'birth_date', messageIncludes: ['birth_date'] },
  { code: 'email_duplicate', field: 'email' },
]
// OBS-0018: asocia códigos de error de la API a los campos de la cuenta de acceso (Usuario).
const USER_ERROR_RULES: FieldErrorRule[] = [
  { code: 'email_duplicate', field: 'email' },
  { code: 'invalid_email_domain', field: 'email' },
  { code: 'username_duplicate', field: 'username' },
  { code: 'validation_error', field: 'role_id', messageIncludes: ['role_id'] },
]
const MAX_BIRTH_DATE = format(subYears(new Date(), 18), 'yyyy-MM-dd')

const NO_ACCESS = '__sin_acceso__'
const ACTIVE_OPTIONS = [{ text: 'Activo', value: 'true' }, { text: 'Inactivo', value: 'false' }]

interface TeamRow {
  key: string
  resource: Resource | null
  user: UserAdmin | null
}

function mergeTeam(resources: Resource[], users: UserAdmin[]): TeamRow[] {
  const usersById = new Map(users.map(u => [u.id, u]))
  const linkedUserIds = new Set<string>()
  const rows: TeamRow[] = resources.map(r => {
    if (r.user_id) linkedUserIds.add(r.user_id)
    return { key: `r-${r.id}`, resource: r, user: r.user_id ? usersById.get(r.user_id) ?? null : null }
  })
  users.filter(u => !linkedUserIds.has(u.id)).forEach(u => rows.push({ key: `u-${u.id}`, resource: null, user: u }))
  return rows.sort((a, b) =>
    (a.resource?.full_name ?? a.user?.username ?? '').localeCompare(b.resource?.full_name ?? b.user?.username ?? ''))
}

/** Pantalla unificada de Equipo: fusiona Recursos (perfil RRHH + skills) y Usuarios (cuenta
 * de acceso + rol). Son entidades separadas a nivel de datos (0..1 opcional en ambos
 * sentidos — un recurso puede no tener cuenta aún, una cuenta puede ser puramente
 * administrativa); esta pantalla solo unifica la gestión visual para el caso común donde
 * son la misma persona. Roles/permisos siguen viviendo 100% en `users.role_id`. */
export default function TeamPage() {
  const { hasPermission, userId } = useAuthStore()
  const canManageResource = hasPermission('resources', 'create')
  const canCreateUser = hasPermission('users', 'create')
  const canChangeRole = hasPermission('users', 'edit')
  const canDeactivateUser = hasPermission('users', 'deactivate')
  const canViewCompensation = hasPermission('compensation', 'view')
  const canEditCompensation = hasPermission('compensation', 'edit')
  const canSeeTeamworkBadge = hasPermission('teamwork_integration', 'operate')
  const isOwnProfile = (r: Resource) => r.user_id === userId

  const [resources, setResources] = useState<Resource[]>([])
  const [users, setUsers] = useState<UserAdmin[]>([])
  const [migratedResourceIds, setMigratedResourceIds] = useState<Set<string>>(new Set())
  const [skills, setSkills] = useState<Skill[]>([])
  const [roles, setRoles] = useState<RoleDetail[]>([])
  const [teamOptions, setTeamOptions] = useState<CatalogItem[]>([])
  const [loading, setLoading] = useState(false)

  const [createOpen, setCreateOpen] = useState(false)
  const [createForm] = Form.useForm<ResourceFormData & { username?: string; role_id?: string }>()

  const [editingResource, setEditingResource] = useState<Resource | null>(null)
  const [editForm] = Form.useForm<ResourceFormData>()

  const [roleFormOpen, setRoleFormOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserAdmin | null>(null)
  const [roleForm] = Form.useForm<{ role_id: string }>()

  const [compOpen, setCompOpen] = useState<Resource | null>(null)
  const [compensation, setCompensation] = useState<ResourceCompensation | null>(null)
  const [compForm] = Form.useForm<CompensationFormData>()

  const [scheduleResource, setScheduleResource] = useState<Resource | null>(null)

  const [provisionalPassword, setProvisionalPassword] = useState<string | null>(null)
  const [confirmDeactivateResource, setConfirmDeactivateResource] = useState<string | null>(null)
  const [confirmDeactivateUser, setConfirmDeactivateUser] = useState<string | null>(null)
  const [confirmResetPassword, setConfirmResetPassword] = useState<string | null>(null)

  // ── Vincular cuenta/perfil a filas ya existentes sin la otra mitad ────────
  const [linkAccountFor, setLinkAccountFor] = useState<Resource | null>(null)
  const [linkAccountMode, setLinkAccountMode] = useState<'create' | 'existing'>('create')
  const [linkAccountForm] = Form.useForm<{ username?: string; role_id?: string; existing_user_id?: string }>()

  const [linkProfileFor, setLinkProfileFor] = useState<UserAdmin | null>(null)
  const [linkProfileMode, setLinkProfileMode] = useState<'create' | 'existing'>('create')
  const [linkProfileForm] = Form.useForm<ResourceFormData & { existing_resource_id?: string }>()

  const load = async () => {
    setLoading(true)
    try {
      const [resRes, userRes] = await Promise.all([
        resourceService.list({ page_size: 200 }),
        userService.list({ page_size: 200 }),
      ])
      setResources(resRes.items)
      setUsers(userRes.items)
    } catch {
      message.error('No se pudo cargar el equipo')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])
  // spec 044 US5: mismo criterio que ClientsPage.tsx (research.md Decisión 7).
  useEffect(() => {
    if (!canSeeTeamworkBadge) return
    teamworkIntegrationService.getMigratedRefs('resource').then(r => setMigratedResourceIds(new Set(r.sytix_ids)))
      .catch(() => {})
  }, [canSeeTeamworkBadge])
  useEffect(() => {
    skillService.list(true).then(r => setSkills(r.items))
      .catch(() => message.error('No se pudo cargar el catálogo de skills'))
  }, [])
  useEffect(() => {
    catalogService.list('teams').then(r => setTeamOptions(r.items))
      .catch(() => message.error('No se pudo cargar el catálogo de equipos'))
  }, [])
  useEffect(() => {
    roleService.list({ page_size: 100, active: true }).then(r => setRoles(r.items))
      .catch(() => message.error('No se pudo cargar la lista de roles'))
  }, [])

  const rows = useMemo(() => mergeTeam(resources, users), [resources, users])
  const orphanResources = useMemo(() => rows.filter(r => r.resource && !r.user).map(r => r.resource!), [rows])
  const orphanUsers = useMemo(() => rows.filter(r => !r.resource && r.user).map(r => r.user!), [rows])

  // ── Alta de integrante ────────────────────────────────────────────────────
  const openCreate = () => { createForm.resetFields(); setCreateOpen(true) }

  const handleCreate = async (values: ResourceFormData & { username?: string; role_id?: string; notify?: boolean }) => {
    let createdUserId: string | undefined
    let notificationSent = false
    try {
      if (canCreateUser) {
        const { user, provisional_password, notification_sent } = await userService.create({
          email: values.email, username: values.username!, role_id: values.role_id!,
          notify: values.notify,
        })
        createdUserId = user.id
        notificationSent = notification_sent
        setProvisionalPassword(provisional_password)
      }
    } catch (err: unknown) {
      if (mapApiErrorToFormFields(err, createForm, USER_ERROR_RULES)) return
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al crear la cuenta de acceso'
      message.error(msg)
      return
    }
    try {
      await resourceService.create({ ...values, user_id: createdUserId })
      setCreateOpen(false)
      // spec 038 US5 (T037): informa si el correo de bienvenida efectivamente se envió, ya que
      // un fallo de SMTP no revierte la creación del usuario (queda visible acá, no silencioso).
      const notifySuffix = values.notify ? (notificationSent ? ' — correo de bienvenida enviado' : ' — no se pudo enviar el correo de bienvenida') : ''
      message.success((createdUserId ? 'Integrante creado con cuenta de acceso' : 'Recurso creado (sin cuenta de acceso)') + notifySuffix)
      load()
    } catch (err: unknown) {
      if (!createdUserId && mapApiErrorToFormFields(err, createForm, RESOURCE_ERROR_RULES)) return
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al crear el perfil de recurso'
      if (createdUserId) {
        message.error(`La cuenta de acceso se creó, pero el perfil de recurso falló: ${msg}. Contacta a soporte.`)
      } else {
        message.error(msg)
      }
    }
  }

  // ── Editar perfil de recurso ──────────────────────────────────────────────
  const openEditResource = (r: Resource) => {
    editForm.setFieldsValue({ ...r, skill_ids: r.skills.map(s => s.id) })
    setEditingResource(r)
  }

  const handleEditResource = async (values: ResourceFormData) => {
    if (!editingResource) return
    const { skill_ids, ...profileFields } = values
    try {
      await resourceService.update(editingResource.id, profileFields)
      if (canManageResource && skill_ids) {
        await resourceService.updateSkills(editingResource.id, skill_ids)
      }
      message.success('Perfil actualizado')
      setEditingResource(null)
      load()
    } catch (err: unknown) {
      if (mapApiErrorToFormFields(err, editForm, RESOURCE_ERROR_RULES)) return
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al guardar'
      message.error(msg)
    }
  }

  // ── Rol y cuenta de acceso ────────────────────────────────────────────────
  const openRoleChange = (u: UserAdmin) => {
    roleForm.setFieldsValue({ role_id: u.role.id })
    setEditingUser(u)
    setRoleFormOpen(true)
  }

  const handleRoleSubmit = async ({ role_id }: { role_id: string }) => {
    if (!editingUser) return
    try {
      await userService.changeRole(editingUser.id, role_id)
      message.success('Rol actualizado')
      setRoleFormOpen(false)
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al cambiar el rol'
      message.error(msg)
    }
  }

  const handleResetPassword = async (id: string) => {
    try {
      const { provisional_password } = await userService.resetPassword(id)
      setConfirmResetPassword(null)
      setProvisionalPassword(provisional_password)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al resetear la contraseña'
      message.error(msg)
    }
  }

  const handleCopyPassword = async () => {
    if (!provisionalPassword) return
    // spec 038 US5 (T033): antes no esperaba la promesa ni manejaba su rechazo — en un contexto
    // no seguro (HTTP sin TLS, típico al acceder por IP en vez de localhost) o con permiso de
    // portapapeles denegado, `navigator.clipboard.writeText` se rechaza y el toast de éxito se
    // mostraba de todas formas, sin que la contraseña se hubiera copiado realmente.
    try {
      await navigator.clipboard.writeText(provisionalPassword)
      message.success('Contraseña copiada')
    } catch {
      message.error('No se pudo copiar la contraseña — copiala manualmente')
    }
  }

  // ── Compensación ──────────────────────────────────────────────────────────
  const openCompensation = async (r: Resource) => {
    setCompOpen(r)
    compForm.resetFields()
    setCompensation(null)
    try {
      const comp = await resourceService.getCompensation(r.id)
      setCompensation(comp)
      compForm.setFieldsValue(comp)
    } catch (err: unknown) {
      if ((err as { response?: { status?: number } }).response?.status !== 404) {
        message.error('No se pudo cargar la compensación')
      }
      // 404 = sin compensación registrada aún; el formulario queda vacío
    }
  }

  const handleSaveCompensation = async (values: CompensationFormData) => {
    if (!compOpen) return
    try {
      const saved = await resourceService.saveCompensation(compOpen.id, values)
      setCompensation(saved)
      compForm.setFieldsValue(saved)
      message.success('Compensación guardada')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al guardar la compensación'
      message.error(msg)
    }
  }

  // ── Activar/Desactivar (recurso y cuenta son independientes) ─────────────
  const handleDeactivateResource = async (id: string) => {
    try {
      await resourceService.deactivate(id)
      message.success('Recurso desactivado')
      setConfirmDeactivateResource(null)
      load()
    } catch {
      message.error('No se pudo desactivar el recurso')
    }
  }
  const handleActivateResource = async (id: string) => {
    try {
      await resourceService.activate(id)
      message.success('Recurso activado')
      load()
    } catch {
      message.error('No se pudo activar el recurso')
    }
  }
  const handleDeactivateUser = async (id: string) => {
    try {
      await userService.deactivate(id)
      message.success('Cuenta desactivada')
      setConfirmDeactivateUser(null)
      load()
    } catch {
      message.error('No se pudo desactivar la cuenta')
    }
  }
  const handleActivateUser = async (id: string) => {
    try {
      await userService.activate(id)
      message.success('Cuenta activada')
      load()
    } catch {
      message.error('No se pudo activar la cuenta')
    }
  }

  // ── Vincular cuenta a un recurso ya existente sin cuenta ──────────────────
  const openLinkAccount = (r: Resource) => {
    linkAccountForm.resetFields()
    setLinkAccountMode(canCreateUser ? 'create' : 'existing')
    setLinkAccountFor(r)
  }

  const handleLinkAccount = async (values: { username?: string; role_id?: string; existing_user_id?: string }) => {
    if (!linkAccountFor) return
    try {
      let targetUserId: string
      if (linkAccountMode === 'create') {
        const { user, provisional_password } = await userService.create({
          email: linkAccountFor.email, username: values.username!, role_id: values.role_id!,
        })
        targetUserId = user.id
        setProvisionalPassword(provisional_password)
      } else {
        targetUserId = values.existing_user_id!
      }
      await resourceService.update(linkAccountFor.id, { user_id: targetUserId })
      message.success('Cuenta vinculada')
      setLinkAccountFor(null)
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al vincular la cuenta'
      message.error(msg)
    }
  }

  // ── Vincular perfil de recurso a una cuenta ya existente sin perfil ───────
  const openLinkProfile = (u: UserAdmin) => {
    linkProfileForm.resetFields()
    setLinkProfileMode('create')
    setLinkProfileFor(u)
  }

  const handleLinkProfile = async (values: ResourceFormData & { existing_resource_id?: string }) => {
    if (!linkProfileFor) return
    try {
      if (linkProfileMode === 'create') {
        await resourceService.create({ ...values, email: linkProfileFor.email, user_id: linkProfileFor.id })
      } else {
        await resourceService.update(values.existing_resource_id!, { user_id: linkProfileFor.id })
      }
      message.success('Perfil vinculado')
      setLinkProfileFor(null)
      load()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al vincular el perfil'
      message.error(msg)
    }
  }

  const extendedProfileFields = (currentResourceId: string | null) => (
    <Collapse
      ghost
      items={[{
        key: 'profile',
        label: 'Perfil extendido (SDD V3)',
        children: (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', columnGap: 16 }}>
            <Form.Item name="identification" label="Identificación" rules={[
              { pattern: /^[0-9]{6,15}$/, message: 'Solo dígitos (6 a 15)' },
            ]}>
              <Input style={{ width: '100%' }} maxLength={15} />
            </Form.Item>
            <Form.Item name="nationality" label="Nacionalidad">
              <Select
                allowClear showSearch optionFilterProp="label" style={{ width: '100%' }}
                options={COUNTRIES.map(c => ({ value: c.code, label: c.name }))}
              />
            </Form.Item>
            <Form.Item name="birth_date" label="Fecha de nacimiento" rules={[
              {
                validator: (_, value) =>
                  !value || value <= MAX_BIRTH_DATE
                    ? Promise.resolve()
                    : Promise.reject(new Error('Debe implicar al menos 18 años de edad')),
              },
            ]}>
              <Input type="date" max={MAX_BIRTH_DATE} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item name="marital_status" label="Estado civil">
              <Select allowClear style={{ width: '100%' }} options={['Soltero/a', 'Casado/a', 'Unión libre', 'Divorciado/a', 'Viudo/a'].map(v => ({ value: v, label: v }))} />
            </Form.Item>
            <Form.Item name="contract_type" label="Tipo de contrato"><Input style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="calendar_country" label="País calendario">
              <Select allowClear style={{ width: '100%' }} options={['Colombia', 'Argentina', 'Ecuador', 'Otro'].map(v => ({ value: v, label: v }))} />
            </Form.Item>
            <Form.Item name="timezone" label="Huso horario"
              extra="Se usa para calcular disponibilidad y horario laboral (Fase 5).">
              <Select allowClear showSearch style={{ width: '100%' }}
                options={TIMEZONES.map(tz => ({ value: tz, label: tz }))} />
            </Form.Item>

            <Form.Item name="education_level" label="Nivel de estudios">
              <Select allowClear style={{ width: '100%' }} options={EDUCATION_LEVEL_OPTIONS} />
            </Form.Item>
            <Form.Item name="specialty" label="Especialidad">
              <Select allowClear style={{ width: '100%' }} options={['Desarrollador', 'Funcional', 'Infraestructura', 'Otro'].map(v => ({ value: v, label: v }))} />
            </Form.Item>
            <Form.Item name="seniority" label="Seniority">
              <Select allowClear style={{ width: '100%' }} options={['Junior', 'Staff', 'Senior'].map(v => ({ value: v, label: v }))} />
            </Form.Item>

            <Form.Item name="team" label="Equipo">
              <Select
                allowClear showSearch optionFilterProp="label" style={{ width: '100%' }}
                options={teamOptions.filter(t => t.active).map(t => ({ value: t.name, label: t.name }))}
              />
            </Form.Item>
            <Form.Item name="manager_id" label="Jefe directo">
              <Select
                allowClear showSearch optionFilterProp="label" placeholder="Seleccionar jefe" style={{ width: '100%' }}
                options={resources.filter(res => res.active && res.id !== currentResourceId)
                  .map(res => ({ value: res.id, label: res.full_name }))}
              />
            </Form.Item>

            <Form.Item name="certifications" label="Certificaciones" style={{ gridColumn: '1 / -1' }}>
              <Input.TextArea rows={2} />
            </Form.Item>
          </div>
        ),
      }]}
    />
  )

  const columns: ColumnsType<TeamRow> = [
    {
      title: 'Nombre', key: 'nombre',
      ...clientTextColumnFilter<TeamRow>('Buscar nombre o email...', row =>
        `${row.resource?.full_name ?? row.user?.username ?? ''} ${row.resource?.email ?? row.user?.email ?? ''}`),
      render: (_: unknown, row: TeamRow) => {
        const name = row.resource?.full_name ?? row.user?.username ?? '—'
        const c = avatarColor(row.resource?.id ?? row.user?.id ?? name)
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 26, height: 26, borderRadius: '50%', display: 'flex', alignItems: 'center',
              justifyContent: 'center', background: c.bg, color: c.text, fontWeight: 700, fontSize: 11, flexShrink: 0,
            }}>
              {initials(name)}
            </div>
            <div>
              <div>{name}</div>
              <Space size={4}>
                {!row.resource && <Tag style={{ fontSize: 10, marginRight: 0 }}>Sin perfil de recurso</Tag>}
                {!row.user && <Tag style={{ fontSize: 10, marginRight: 0 }}>Sin cuenta de acceso</Tag>}
                {canSeeTeamworkBadge && row.resource && migratedResourceIds.has(row.resource.id) && (
                  <Tag icon={<SyncOutlined />} color="blue" style={{ fontSize: 10, marginRight: 0 }}>Teamwork</Tag>
                )}
              </Space>
            </div>
          </div>
        )
      },
    },
    { title: 'Email', key: 'email', render: (_: unknown, row: TeamRow) => row.resource?.email ?? row.user?.email ?? '—' },
    {
      title: 'Rol', key: 'rol',
      render: (_: unknown, row: TeamRow) => row.user
        ? <Tag color={roleColor(row.user.role.name)}>{row.user.role.name}</Tag>
        : <Tag>Sin acceso</Tag>,
      ...clientColumnFilter<TeamRow>(
        [...roles.map(r => ({ text: r.name, value: r.name })), { text: 'Sin acceso', value: NO_ACCESS }],
        (value, row) => value === NO_ACCESS ? !row.user : row.user?.role.name === value,
      ),
    },
    {
      title: 'Skills', key: 'skills',
      render: (_: unknown, row: TeamRow) => row.resource
        ? row.resource.skills.map(sk => (
            <Tag key={sk.id} style={{ fontFamily: 'ui-monospace, SFMono-Regular, monospace', letterSpacing: 0.3, color: palette.slate700, background: palette.slate100, borderColor: palette.slate200 }}>
              {sk.code}
            </Tag>
          ))
        : <em style={{ color: palette.slate400 }}>—</em>,
      ...clientColumnFilter<TeamRow>(
        skills.map(s => ({ text: `${s.code} — ${s.label}`, value: s.code })),
        (value, row) => !!row.resource?.skills.some(sk => sk.code === value),
      ),
    },
    {
      title: 'Estado', key: 'estado',
      render: (_: unknown, row: TeamRow) => <StatusTag active={row.resource ? row.resource.active : row.user?.active ?? true} />,
      ...clientColumnFilter<TeamRow>(ACTIVE_OPTIONS, (value, row) =>
        String(row.resource ? row.resource.active : row.user?.active ?? true) === value),
    },
    {
      title: 'Acciones', key: 'actions',
      render: (_: unknown, row: TeamRow) => {
        const r = row.resource, u = row.user
        return (
          <Space size={4}>
            {r && (canManageResource || isOwnProfile(r)) && (
              <Tooltip title="Editar perfil"><Button size="small" icon={<EditOutlined />} onClick={() => openEditResource(r)} /></Tooltip>
            )}
            {r && canViewCompensation && (
              <Tooltip title="Compensación"><Button size="small" icon={<DollarOutlined />} onClick={() => openCompensation(r)} /></Tooltip>
            )}
            {r && (canManageResource || isOwnProfile(r)) && (
              <Tooltip title="Horario laboral"><Button size="small" icon={<ClockCircleOutlined />} onClick={() => setScheduleResource(r)} /></Tooltip>
            )}
            {u && canChangeRole && (
              <Tooltip title="Cambiar rol"><Button size="small" icon={<SettingOutlined />} onClick={() => openRoleChange(u)} /></Tooltip>
            )}
            {u && canChangeRole && (
              <Tooltip title="Resetear contraseña"><Button size="small" icon={<KeyOutlined />} onClick={() => setConfirmResetPassword(u.id)} /></Tooltip>
            )}
            {r && canManageResource && (r.active
              ? <Tooltip title="Desactivar recurso (RRHH)"><Button size="small" danger icon={<StopOutlined />} onClick={() => setConfirmDeactivateResource(r.id)} /></Tooltip>
              : <Tooltip title="Activar recurso"><Button size="small" icon={<PlayCircleOutlined style={{ color: palette.green600 }} />} onClick={() => handleActivateResource(r.id)} /></Tooltip>)}
            {u && canDeactivateUser && (u.active
              ? <Tooltip title="Desactivar cuenta (acceso)"><Button size="small" danger icon={<LockOutlined />} onClick={() => setConfirmDeactivateUser(u.id)} /></Tooltip>
              : <Tooltip title="Activar cuenta"><Button size="small" icon={<UnlockOutlined style={{ color: palette.green600 }} />} onClick={() => handleActivateUser(u.id)} /></Tooltip>)}
            {r && !u && canManageResource && (
              <Tooltip title="Vincular cuenta de acceso"><Button size="small" icon={<LinkOutlined />} onClick={() => openLinkAccount(r)} /></Tooltip>
            )}
            {u && !r && canManageResource && (
              <Tooltip title="Vincular perfil de recurso"><Button size="small" icon={<LinkOutlined />} onClick={() => openLinkProfile(u)} /></Tooltip>
            )}
          </Space>
        )
      },
    },
  ]

  return (
    <div>
      <PageToolbar
        filters={null}
        action={(canManageResource || canCreateUser) && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>Nuevo integrante</Button>
        )}
      />

      <Table rowKey="key" columns={columns} dataSource={rows} loading={loading} />

      {/* ── Alta de integrante ── */}
      <Modal title="Nuevo integrante del equipo" open={createOpen} onCancel={() => setCreateOpen(false)}
        onOk={() => createForm.submit()} okText="Crear" width={760}>
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Space style={{ display: 'flex' }} align="start" wrap>
            <Form.Item name="full_name" label="Nombre completo" rules={[{ required: true, message: 'El nombre es requerido' }]}>
              <Input style={{ width: 260 }} />
            </Form.Item>
            <Form.Item name="email" label="Email (@sywork.net)" rules={[
              { required: true, message: 'El email es requerido' },
              { pattern: /^[^@]+@sywork\.net$/, message: 'Debe ser @sywork.net' },
            ]}>
              <Input style={{ width: 260 }} />
            </Form.Item>
          </Space>
          {canCreateUser ? (
            <>
              <Alert type="info" showIcon style={{ marginBottom: 12 }}
                message="Se creará también una cuenta de acceso al sistema (contraseña provisional generada)." />
              <Space style={{ display: 'flex' }} align="start" wrap>
                <Form.Item name="username" label="Nombre de usuario" rules={[{ required: true, message: 'El username es requerido' }]}>
                  <Input style={{ width: 200 }} placeholder="nombre.apellido" />
                </Form.Item>
                <Form.Item name="role_id" label="Rol" rules={[{ required: true, message: 'Selecciona un rol' }]}>
                  <Select style={{ width: 180 }} options={roles.map(r => ({ value: r.id, label: r.name }))} placeholder="Seleccionar rol" />
                </Form.Item>
              </Space>
              <Form.Item name="notify" valuePropName="checked" initialValue={false}>
                <Checkbox>Notificar al Usuario (correo de bienvenida con la contraseña temporal)</Checkbox>
              </Form.Item>
            </>
          ) : (
            <Alert type="warning" showIcon style={{ marginBottom: 12 }}
              message="Este colaborador no tendrá acceso al sistema todavía. Un Admin deberá crearle una cuenta de acceso más adelante." />
          )}
          <Form.Item name="skill_ids" label="Skills">
            <Select mode="multiple" options={skills.map(s => ({ value: s.id, label: `${s.code} — ${s.label}` }))} placeholder="Seleccionar skills" />
          </Form.Item>
          {extendedProfileFields(null)}
          <Form.Item name="notes" label="Notas"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      {/* ── Editar perfil de recurso ── */}
      <Modal title={`Editar perfil — ${editingResource?.full_name ?? ''}`} open={!!editingResource}
        onCancel={() => setEditingResource(null)} onOk={() => editForm.submit()} okText="Guardar" width={760}>
        <Form form={editForm} layout="vertical" onFinish={handleEditResource}>
          <Form.Item name="full_name" label="Nombre completo" rules={[{ required: true, message: 'El nombre es requerido' }]}>
            <Input style={{ width: 300 }} />
          </Form.Item>
          {canManageResource && (
            <Form.Item name="skill_ids" label="Skills">
              <Select mode="multiple" options={skills.map(s => ({ value: s.id, label: `${s.code} — ${s.label}` }))} placeholder="Seleccionar skills" />
            </Form.Item>
          )}
          {extendedProfileFields(editingResource?.id ?? null)}
          <Form.Item name="notes" label="Notas"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      {/* ── Cambiar rol ── */}
      <Modal title="Cambiar rol" open={roleFormOpen} onCancel={() => setRoleFormOpen(false)} onOk={() => roleForm.submit()} okText="Guardar">
        <Form form={roleForm} layout="vertical" onFinish={handleRoleSubmit}>
          <Form.Item name="role_id" label="Nuevo rol" rules={[{ required: true, message: 'Selecciona un rol' }]}>
            <Select options={roles.map(r => ({ value: r.id, label: r.name }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Compensación ── */}
      <Modal
        title={`Compensación — ${compOpen?.full_name ?? ''}`}
        open={!!compOpen}
        onCancel={() => setCompOpen(null)}
        footer={canEditCompensation
          ? [
              <Button key="cancel" onClick={() => setCompOpen(null)}>Cerrar</Button>,
              <Button key="save" type="primary" onClick={() => compForm.submit()}>Guardar</Button>,
            ]
          : [<Button key="cancel" onClick={() => setCompOpen(null)}>Cerrar</Button>]}
      >
        <Form form={compForm} layout="vertical" onFinish={handleSaveCompensation} disabled={!canEditCompensation}>
          <Space style={{ display: 'flex' }} align="start">
            <Form.Item name="base_salary" label="Salario base"><InputNumber min={0} style={{ width: 150 }} /></Form.Item>
            <Form.Item name="total_salary" label="Salario total (con beneficios)"><InputNumber min={0} style={{ width: 180 }} /></Form.Item>
          </Space>
          <Space style={{ display: 'flex' }} align="start">
            <Form.Item name="overhead" label="Overhead / costos adicionales"><InputNumber min={0} style={{ width: 180 }} /></Form.Item>
            <Form.Item name="currency" label="Moneda" initialValue="USD">
              <Select style={{ width: 100 }} options={['USD', 'COP', 'ARS'].map(v => ({ value: v, label: v }))} />
            </Form.Item>
          </Space>
        </Form>
        <Divider style={{ margin: '8px 0' }} />
        <div>
          <strong>Costo hora calculado:</strong>{' '}
          {compensation?.hourly_cost != null
            ? `${compensation.hourly_cost.toLocaleString('en-US')} ${compensation.currency}/h`
            : '— (se calcula al guardar el salario total)'}
        </div>
      </Modal>

      {/* ── Vincular cuenta a un recurso existente ── */}
      <Modal title={`Vincular cuenta de acceso — ${linkAccountFor?.full_name ?? ''}`} open={!!linkAccountFor}
        onCancel={() => setLinkAccountFor(null)} onOk={() => linkAccountForm.submit()} okText="Vincular" width={520}>
        <Form form={linkAccountForm} layout="vertical" onFinish={handleLinkAccount}>
          <Radio.Group value={linkAccountMode} onChange={e => setLinkAccountMode(e.target.value)} style={{ marginBottom: 16 }}>
            {canCreateUser && <Radio.Button value="create">Crear cuenta nueva</Radio.Button>}
            <Radio.Button value="existing">Vincular cuenta existente</Radio.Button>
          </Radio.Group>
          {linkAccountMode === 'create' ? (
            <>
              <Form.Item label="Email"><Input value={linkAccountFor?.email} disabled /></Form.Item>
              <Form.Item name="username" label="Nombre de usuario" rules={[{ required: true, message: 'El username es requerido' }]}>
                <Input placeholder="nombre.apellido" />
              </Form.Item>
              <Form.Item name="role_id" label="Rol" rules={[{ required: true, message: 'Selecciona un rol' }]}>
                <Select options={roles.map(r => ({ value: r.id, label: r.name }))} placeholder="Seleccionar rol" />
              </Form.Item>
            </>
          ) : (
            <Form.Item name="existing_user_id" label="Cuenta existente sin perfil de recurso"
              rules={[{ required: true, message: 'Selecciona una cuenta' }]}>
              <Select
                options={orphanUsers.map(u => ({ value: u.id, label: `${u.username} (${u.email})` }))}
                placeholder={orphanUsers.length ? 'Seleccionar cuenta' : 'No hay cuentas sin perfil disponibles'}
              />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* ── Vincular perfil de recurso a una cuenta existente ── */}
      <Modal title={`Vincular perfil de recurso — ${linkProfileFor?.username ?? ''}`} open={!!linkProfileFor}
        onCancel={() => setLinkProfileFor(null)} onOk={() => linkProfileForm.submit()} okText="Vincular" width={760}>
        <Form form={linkProfileForm} layout="vertical" onFinish={handleLinkProfile}>
          <Radio.Group value={linkProfileMode} onChange={e => setLinkProfileMode(e.target.value)} style={{ marginBottom: 16 }}>
            <Radio.Button value="create">Crear perfil nuevo</Radio.Button>
            <Radio.Button value="existing">Vincular recurso existente</Radio.Button>
          </Radio.Group>
          {linkProfileMode === 'create' ? (
            <>
              <Form.Item name="full_name" label="Nombre completo" rules={[{ required: true, message: 'El nombre es requerido' }]}
                initialValue={linkProfileFor?.username}>
                <Input style={{ width: 300 }} />
              </Form.Item>
              <Form.Item name="skill_ids" label="Skills">
                <Select mode="multiple" options={skills.map(s => ({ value: s.id, label: `${s.code} — ${s.label}` }))} placeholder="Seleccionar skills" />
              </Form.Item>
              {extendedProfileFields(null)}
              <Form.Item name="notes" label="Notas"><Input.TextArea rows={2} /></Form.Item>
            </>
          ) : (
            <Form.Item name="existing_resource_id" label="Recurso existente sin cuenta de acceso"
              rules={[{ required: true, message: 'Selecciona un recurso' }]}>
              <Select
                options={orphanResources.map(r => ({ value: r.id, label: `${r.full_name} (${r.email})` }))}
                placeholder={orphanResources.length ? 'Seleccionar recurso' : 'No hay recursos sin cuenta disponibles'}
              />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* ── Contraseña provisional ── */}
      <Modal
        title="Contraseña provisional generada"
        open={!!provisionalPassword}
        closable={false}
        maskClosable={false}
        footer={<Button type="primary" onClick={() => setProvisionalPassword(null)}>Ya la copié, cerrar</Button>}
      >
        <Alert
          type="warning"
          showIcon
          message="Esta contraseña no se volverá a mostrar. Compártela ahora con la persona por un canal seguro."
          style={{ marginBottom: 16 }}
        />
        <Space>
          <Typography.Text code style={{ fontSize: 16 }}>{provisionalPassword}</Typography.Text>
          <Button size="small" icon={<CopyOutlined />} onClick={handleCopyPassword}>Copiar</Button>
        </Space>
      </Modal>

      {confirmDeactivateResource && (
        <ConfirmationModal open title="Desactivar recurso"
          description="¿Confirmas la desactivación de este recurso? No aparecerá en sugerencias de asignación."
          onConfirm={() => handleDeactivateResource(confirmDeactivateResource)} onCancel={() => setConfirmDeactivateResource(null)} />
      )}
      {confirmDeactivateUser && (
        <ConfirmationModal open title="Desactivar cuenta de acceso"
          description="¿Confirmas la desactivación de esta cuenta? Perderá acceso inmediatamente en su próxima llamada a la API."
          onConfirm={() => handleDeactivateUser(confirmDeactivateUser)} onCancel={() => setConfirmDeactivateUser(null)} />
      )}
      {confirmResetPassword && (
        <ConfirmationModal open title="Resetear contraseña"
          description="¿Confirmas resetear la contraseña de esta cuenta? Se generará una nueva contraseña temporal y la actual dejará de funcionar."
          onConfirm={() => handleResetPassword(confirmResetPassword)} onCancel={() => setConfirmResetPassword(null)} />
      )}

      <WorkScheduleDrawer
        resourceId={scheduleResource?.id ?? null}
        resourceName={scheduleResource?.full_name}
        onClose={() => setScheduleResource(null)}
      />
    </div>
  )
}
