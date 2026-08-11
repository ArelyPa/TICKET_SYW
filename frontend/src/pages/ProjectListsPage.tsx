import { useCallback, useEffect, useState } from 'react'
import { Button, Empty, Input, Modal, Spin, Tag, Typography, message } from 'antd'
import { PlusOutlined, SyncOutlined, UnorderedListOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { projectService } from '../services/projectService'
import { taskListService } from '../services/taskListService'
import { ticketService } from '../services/ticketService'
import { teamworkIntegrationService } from '../services/teamworkIntegrationService'
import type { ProjectListItem } from '../types/project'
import type { TaskList } from '../types/taskList'
import type { TicketListItem } from '../types/ticket'
import { STATUS_LABELS } from '../types/ticket'
import { avatarColor, initials, palette, TICKET_STATUS_CHIP } from '../theme'
import { useAuthStore } from '../store/authStore'

/** Sidebar de Listas de un Proyecto — según `docs/mockup.html`, pantalla `s-lista`
 * (Cliente → Proyecto → Lista → Tarea → Subtarea). Spec 009, US3. */
export default function ProjectListsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { hasPermission } = useAuthStore()
  const canSeeTeamworkBadge = hasPermission('teamwork_integration', 'operate')

  const [project, setProject] = useState<ProjectListItem | null>(null)
  const [lists, setLists] = useState<TaskList[]>([])
  const [migratedListIds, setMigratedListIds] = useState<Set<string>>(new Set())
  const [selectedListId, setSelectedListId] = useState<string | undefined>()
  const [tasks, setTasks] = useState<TicketListItem[]>([])
  const [loadingTasks, setLoadingTasks] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [newListName, setNewListName] = useState('')
  const [saving, setSaving] = useState(false)
  const [nameError, setNameError] = useState<string | undefined>()

  const loadLists = useCallback(async () => {
    if (!projectId) return
    try {
      const items = await taskListService.listByProject(projectId)
      setLists(items)
      if (!selectedListId && items.length > 0) setSelectedListId(items[0].id)
    } catch {
      message.error('No se pudo cargar la lista de Listas')
    }
  }, [projectId, selectedListId])

  useEffect(() => {
    if (!projectId) return
    projectService.get(projectId).then(setProject)
      .catch(() => message.error('No se pudo cargar el proyecto'))
  }, [projectId])

  useEffect(() => { loadLists() }, [loadLists])

  // spec 044 US5: mismo criterio que ClientsPage.tsx/ProjectsPage.tsx (research.md Decisión 7).
  useEffect(() => {
    if (!canSeeTeamworkBadge) return
    teamworkIntegrationService.getMigratedRefs('task_list').then(r => setMigratedListIds(new Set(r.sytix_ids)))
      .catch(() => {})
  }, [canSeeTeamworkBadge])

  useEffect(() => {
    if (!selectedListId) { setTasks([]); return }
    setLoadingTasks(true)
    ticketService.list({ page_size: 100 }).then(r => {
      setTasks(r.items.filter(t => t.list_id === selectedListId && !t.parent_task_id))
    }).catch(() => message.error('No se pudo cargar las Tareas de la Lista'))
      .finally(() => setLoadingTasks(false))
  }, [selectedListId])

  const createList = async () => {
    if (!projectId || !newListName.trim()) {
      message.warning('El nombre es obligatorio')
      return
    }
    setSaving(true)
    setNameError(undefined)
    try {
      const created = await taskListService.create(projectId, newListName.trim())
      message.success('Lista creada')
      setCreateOpen(false)
      setNewListName('')
      setSelectedListId(created.id)
      loadLists()
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { message?: string; code?: string; error?: string } } }).response?.data
      const msg = data?.message ?? 'No se pudo crear la Lista'
      // OBS-0018: name_duplicate/validation_error se asocian al único campo del modal (inline),
      // en vez de dejarlos solo en el toast.
      if (data?.code === 'name_duplicate' || data?.error === 'name_duplicate'
          || data?.code === 'validation_error' || data?.error === 'validation_error') {
        setNameError(msg)
      } else {
        message.error(msg)
      }
    } finally {
      setSaving(false)
    }
  }

  if (!project) return <Spin style={{ display: 'block', margin: '80px auto' }} />

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>{project.name}</Typography.Title>
        <span style={{ color: palette.slate500, fontSize: 13 }}>› Listas</span>
      </div>

      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
        <div style={{ width: 240, flexShrink: 0 }}>
          {lists.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={<span style={{ fontSize: 12, color: palette.slate400 }}>Sin listas todavía</span>} />
          ) : (
            lists.map(l => (
              <div key={l.id} onClick={() => setSelectedListId(l.id)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '8px 10px', borderRadius: 6, cursor: 'pointer', marginBottom: 4,
                  background: selectedListId === l.id ? palette.brandOrange50 : 'transparent',
                  fontWeight: selectedListId === l.id ? 600 : 400,
                }}
              >
                <span style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {l.name}
                  {canSeeTeamworkBadge && migratedListIds.has(l.id) && (
                    <Tag icon={<SyncOutlined />} color="blue" style={{ fontSize: 10, lineHeight: '16px', marginRight: 0 }}>
                      Teamwork
                    </Tag>
                  )}
                </span>
                <span style={{ fontSize: 11, color: palette.slate400 }}>{l.task_count}</span>
              </div>
            ))
          )}
          <Button type="link" size="small" icon={<PlusOutlined />} style={{ padding: '8px 0 0' }}
            onClick={() => setCreateOpen(true)}>
            Nueva lista
          </Button>
        </div>

        <div style={{ flex: 1 }}>
          {!selectedListId ? (
            <em style={{ color: palette.slate400 }}>Elegí una Lista para ver sus Tareas</em>
          ) : loadingTasks ? (
            <Spin />
          ) : tasks.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={<span style={{ fontSize: 12, color: palette.slate400 }}>Sin Tareas en esta Lista</span>} />
          ) : (
            tasks.map(t => {
              const chip = TICKET_STATUS_CHIP[t.status]
              return (
                <div key={t.id} onClick={() => navigate(`/tickets/${t.id}`)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
                    padding: '8px 10px', borderRadius: 6, border: `1px solid ${palette.slate200}`,
                    marginBottom: 6,
                  }}
                >
                  <UnorderedListOutlined style={{ color: palette.slate400 }} />
                  <span style={{ fontSize: 13, flex: 1 }}>{t.title}</span>
                  {t.assignee && (
                    <div style={{
                      width: 20, height: 20, borderRadius: '50%', display: 'flex', alignItems: 'center',
                      justifyContent: 'center', background: avatarColor(t.assignee.id).bg,
                      color: avatarColor(t.assignee.id).text, fontSize: 9, fontWeight: 700, flexShrink: 0,
                    }}>
                      {initials(t.assignee.full_name)}
                    </div>
                  )}
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: '1px 8px', borderRadius: 999,
                    background: chip?.bg, color: chip?.text,
                  }}>
                    {STATUS_LABELS[t.status]}
                  </span>
                </div>
              )
            })
          )}
        </div>
      </div>

      <Modal title="Nueva Lista" open={createOpen}
        onCancel={() => { setCreateOpen(false); setNameError(undefined) }}
        confirmLoading={saving} onOk={createList} okText="Crear">
        <Input placeholder="p. ej. F1: Definiciones y Alistamiento" value={newListName}
          onChange={e => { setNewListName(e.target.value); setNameError(undefined) }}
          status={nameError ? 'error' : undefined} autoFocus />
        {nameError && <div style={{ color: palette.red600, fontSize: 12, marginTop: 4 }}>{nameError}</div>}
      </Modal>
    </div>
  )
}
