import { useState } from 'react'
import { App, Button, Card, Select, Space, Table, Tag, Typography, Upload } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { timeImportService } from '../services/timeImportService'
import { resourceService } from '../services/resourceService'
import { projectService } from '../services/projectService'
import { ticketService } from '../services/ticketService'
import type { TimeImportPreview, TimeImportRow, TimeImportConfirmRow, TimeImportRowAction } from '../types/timeImport'
import { TIME_IMPORT_ISSUE_LABELS } from '../types/timeImport'

const { Title, Text } = Typography
const { Dragger } = Upload

const STATUS_TAG: Record<TimeImportRow['status'], { color: string; label: string }> = {
  valid: { color: 'green', label: 'Válida' },
  conflict: { color: 'orange', label: 'Conflicto' },
  error: { color: 'red', label: 'Error' },
}

type RowResolution = { action: TimeImportRowAction; targetId?: string }

export default function TimeImportsPage() {
  const { message } = App.useApp()
  const [preview, setPreview] = useState<TimeImportPreview | null>(null)
  const [loading, setLoading] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [resolutions, setResolutions] = useState<Record<number, RowResolution>>({})
  const [resourceOptions, setResourceOptions] = useState<{ value: string; label: string }[]>([])
  const [projectOptions, setProjectOptions] = useState<{ value: string; label: string }[]>([])
  const [ticketOptions, setTicketOptions] = useState<{ value: string; label: string }[]>([])

  const ensureResourceOptions = () => {
    if (resourceOptions.length) return
    resourceService.list({ page_size: 100 }).then(r =>
      setResourceOptions(r.items.map(x => ({ value: x.id, label: x.full_name }))))
  }
  const ensureProjectOptions = () => {
    if (projectOptions.length) return
    projectService.list({ page_size: 100 }).then(r =>
      setProjectOptions(r.items.map(x => ({ value: x.id, label: x.name }))))
  }
  const ensureTicketOptions = () => {
    if (ticketOptions.length) return
    ticketService.list({ page_size: 100 }).then(r =>
      setTicketOptions(r.items.map(x => ({ value: x.id, label: `${x.ticket_number} — ${x.title}` }))))
  }

  const uploadProps: UploadProps = {
    accept: '.xlsx,.csv',
    multiple: false,
    showUploadList: false,
    beforeUpload: (file) => {
      setLoading(true)
      setPreview(null)
      setResolutions({})
      timeImportService.previewFile(file)
        .then(setPreview)
        .catch((err: unknown) => {
          const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
          message.error(msg ?? 'No se pudo generar la vista previa')
        })
        .finally(() => setLoading(false))
      return false
    },
  }

  const setResolution = (row: number, resolution: RowResolution) =>
    setResolutions(prev => ({ ...prev, [row]: resolution }))

  // El backend no persiste nada entre preview y confirm (research.md Decisión 2) — cada fila
  // enviada a /confirm debe traer de vuelta su propio `resolved` completo (duración, fechas,
  // descripción) tal como vino de la preview, con los campos que el usuario resolvió sobreescritos.
  const buildConfirmRows = (): TimeImportConfirmRow[] => {
    if (!preview) return []
    return preview.rows
      .filter(r => r.status !== 'error')
      .map((r): TimeImportConfirmRow => {
        const resolution = resolutions[r.source_row_number]
        const base: TimeImportConfirmRow = {
          source_row_number: r.source_row_number, external_time_id: r.external_time_id,
          status: r.status, resolved: { ...r.resolved },
        }
        if (r.status !== 'conflict' || !resolution) return base
        if (resolution.action === 'omit') return { ...base, action: 'omit' }
        if (resolution.action === 'create') return { ...base, action: 'create', create_entity_type: 'resource' }
        const issue = r.issues[0]
        const field = issue === 'who_not_found' ? 'resource_id'
          : issue === 'project_not_found' ? 'project_id' : 'ticket_id'
        return {
          ...base, action: 'resolve',
          resolved: { ...r.resolved, [field]: resolution.targetId },
        }
      })
  }

  const handleConfirm = async () => {
    if (!preview) return
    const unresolved = preview.rows.filter(
      r => r.status === 'conflict' && !resolutions[r.source_row_number])
    if (unresolved.length > 0) {
      message.warning(`Resolvé las ${unresolved.length} fila(s) en conflicto antes de confirmar`)
      return
    }
    setConfirming(true)
    try {
      const result = await timeImportService.confirm(buildConfirmRows())
      message.success(
        `Carga confirmada: ${result.created_time_entries} creados, ` +
        `${result.updated_time_entries} actualizados, ${result.skipped} omitidos` +
        (result.errors.length ? `, ${result.errors.length} con error` : ''))
      setPreview(null)
      setResolutions({})
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo confirmar la carga')
    } finally {
      setConfirming(false)
    }
  }

  const renderResolution = (row: TimeImportRow) => {
    if (row.status !== 'conflict') return null
    const issue = row.issues[0]
    const current = resolutions[row.source_row_number]
    const options = issue === 'who_not_found' ? resourceOptions
      : issue === 'project_not_found' ? projectOptions : ticketOptions
    const onFocus = issue === 'who_not_found' ? ensureResourceOptions
      : issue === 'project_not_found' ? ensureProjectOptions : ensureTicketOptions

    return (
      <Space direction="vertical" size={4}>
        <Select
          style={{ width: 220 }}
          placeholder="Homologar a existente"
          options={options}
          showSearch
          optionFilterProp="label"
          onFocus={onFocus}
          value={current?.action === 'resolve' ? current.targetId : undefined}
          onChange={(value) => setResolution(row.source_row_number, { action: 'resolve', targetId: value })}
        />
        <Space size={4}>
          {issue === 'who_not_found' && (
            <Button size="small"
                   type={current?.action === 'create' ? 'primary' : 'default'}
                   onClick={() => setResolution(row.source_row_number, { action: 'create' })}>
              Crear Recurso
            </Button>
          )}
          <Button size="small" danger={current?.action === 'omit'}
                 onClick={() => setResolution(row.source_row_number, { action: 'omit' })}>
            Omitir
          </Button>
        </Space>
      </Space>
    )
  }

  const columns = [
    { title: 'Fila', dataIndex: 'source_row_number', width: 70 },
    {
      title: 'Estado', dataIndex: 'status', width: 130,
      render: (status: TimeImportRow['status']) => (
        <Tag color={STATUS_TAG[status].color}>{STATUS_TAG[status].label}</Tag>
      ),
    },
    { title: 'ID Teamwork', dataIndex: 'external_time_id', width: 110 },
    { title: 'Who', render: (_: unknown, row: TimeImportRow) => row.resolved.who_name },
    { title: 'Cliente', render: (_: unknown, row: TimeImportRow) => row.resolved.company_name },
    { title: 'Proyecto', render: (_: unknown, row: TimeImportRow) => row.resolved.project_name },
    { title: 'Tarea', render: (_: unknown, row: TimeImportRow) => row.resolved.task_reference },
    { title: 'Duración (min)', render: (_: unknown, row: TimeImportRow) => row.resolved.duration_minutes },
    { title: 'Descripción', render: (_: unknown, row: TimeImportRow) => row.resolved.description },
    {
      title: 'Observaciones',
      render: (_: unknown, row: TimeImportRow) => (
        <Space direction="vertical" size={0}>
          {row.issues.map(issue => (
            <Text key={issue} type="danger">{TIME_IMPORT_ISSUE_LABELS[issue] ?? issue}</Text>
          ))}
        </Space>
      ),
    },
    { title: 'Resolución', width: 260, render: (_: unknown, row: TimeImportRow) => renderResolution(row) },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Title level={3}>Importación de Tiempos</Title>

      <Card>
        <Dragger {...uploadProps} disabled={loading}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">Arrastrá o hacé clic para cargar el reporte mensual de tiempos de Teamwork (.xlsx/.csv)</p>
        </Dragger>
      </Card>

      {preview && (
        <Card
          title={`Vista previa: ${preview.summary.total} filas (${preview.summary.valid} válidas, ` +
                `${preview.summary.conflict} en conflicto, ${preview.summary.error} con error)`}
          extra={
            <Button type="primary" onClick={handleConfirm} loading={confirming}
                   disabled={preview.summary.valid + preview.summary.conflict === 0}>
              Confirmar carga
            </Button>
          }
        >
          <Table<TimeImportRow>
            rowKey="source_row_number"
            columns={columns}
            dataSource={preview.rows}
            pagination={false}
            size="small"
            scroll={{ x: true }}
          />
        </Card>
      )}
    </Space>
  )
}
