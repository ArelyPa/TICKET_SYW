import { useState } from 'react'
import { App, Button, Card, Space, Table, Tag, Typography, Upload } from 'antd'
import { InboxOutlined, SyncOutlined } from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { ticketImportService } from '../services/ticketImportService'
import type { ImportPreviewResponse, ImportRow } from '../types/ticketImport'
import { IMPORT_ISSUE_LABELS } from '../types/ticketImport'

const { Title, Text } = Typography
const { Dragger } = Upload

const STATUS_TAG: Record<ImportRow['status'], { color: string; label: string }> = {
  ready: { color: 'green', label: 'Listo' },
  needs_review: { color: 'orange', label: 'Pendiente de revisión' },
  error: { color: 'red', label: 'Error' },
}

export default function TicketImportsPage() {
  const { message } = App.useApp()
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const runPreview = async (fn: () => Promise<ImportPreviewResponse>) => {
    setLoading(true)
    setPreview(null)
    try {
      setPreview(await fn())
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo generar la vista previa')
    } finally {
      setLoading(false)
    }
  }

  const uploadProps: UploadProps = {
    accept: '.xlsx,.csv',
    multiple: false,
    showUploadList: false,
    beforeUpload: (file) => {
      runPreview(() => ticketImportService.previewFile(file))
      return false
    },
  }

  const handleSyncApiV3 = () => runPreview(() => ticketImportService.previewApiV3())

  const handleConfirm = async () => {
    if (!preview) return
    setConfirming(true)
    try {
      const result = await ticketImportService.confirm(preview.rows)
      message.success(
        `Importación aplicada: ${result.created} creadas, ${result.updated} actualizadas` +
        (result.errors.length ? `, ${result.errors.length} con error` : ''))
      setPreview(null)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message
      message.error(msg ?? 'No se pudo confirmar la importación')
    } finally {
      setConfirming(false)
    }
  }

  const columns = [
    { title: 'Fila', dataIndex: 'source_row_number', width: 70 },
    {
      title: 'Estado', dataIndex: 'status', width: 160,
      render: (status: ImportRow['status']) => (
        <Tag color={STATUS_TAG[status].color}>{STATUS_TAG[status].label}</Tag>
      ),
    },
    { title: 'ID Teamwork', dataIndex: 'external_id', width: 110 },
    { title: 'Cliente', render: (_: unknown, row: ImportRow) => row.resolved.company_name },
    { title: 'Proyecto', render: (_: unknown, row: ImportRow) => row.resolved.project_name },
    { title: 'Título', render: (_: unknown, row: ImportRow) => row.resolved.title },
    { title: 'Asignado', render: (_: unknown, row: ImportRow) => row.resolved.assignee_name },
    { title: 'Tiempo estimado (h)', render: (_: unknown, row: ImportRow) => row.resolved.estimated_hours },
    {
      title: 'Observaciones',
      render: (_: unknown, row: ImportRow) => (
        <Space direction="vertical" size={0}>
          {row.issues.map(issue => (
            <Text key={issue} type={issue === 'parent_not_found_in_batch' ? 'secondary' : 'danger'}>
              {IMPORT_ISSUE_LABELS[issue] ?? issue}
            </Text>
          ))}
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Title level={3}>Importación de Tareas desde Teamwork</Title>

      <Card>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Dragger {...uploadProps} disabled={loading}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">Arrastrá o hacé clic para cargar el reporte de Teamwork (.xlsx/.csv)</p>
          </Dragger>
          <Button icon={<SyncOutlined />} onClick={handleSyncApiV3} loading={loading}>
            Sincronizar con Teamwork (API v3)
          </Button>
        </Space>
      </Card>

      {preview && (
        <Card
          title={`Vista previa: ${preview.summary.total} filas (${preview.summary.ready} listas, ` +
                `${preview.summary.needs_review} pendientes de revisión, ${preview.summary.error} con error)`}
          extra={
            <Button type="primary" onClick={handleConfirm} loading={confirming}
                   disabled={preview.summary.ready + preview.summary.needs_review === 0}>
              Confirmar importación
            </Button>
          }
        >
          <Table<ImportRow>
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
