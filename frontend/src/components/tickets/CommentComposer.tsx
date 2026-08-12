import { useState } from 'react'
import { App, Button, Modal, Select, Space, Typography, Upload } from 'antd'
import { SendOutlined, UploadOutlined, ExperimentOutlined, CheckOutlined,
         CloseOutlined, StopOutlined, LockOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import type { CommentType, TicketDetail, TicketStatus } from '../../types/ticket'
import { STATUS_LABELS } from '../../types/ticket'
import type { CatalogItem } from '../../types/catalog'
import { ticketService } from '../../services/ticketService'
import { useAuthStore } from '../../store/authStore'
import RichTextEditor, { isRichTextEmpty } from './RichTextEditor'

// Tipos de comentario manuales disponibles por acción FSM válida
const COMMENT_OPTIONS: Array<{ type: CommentType; label: string; action: string | null }> = [
  { type: 'confirmacion_atencion', label: 'Confirmación de atención (→ En Análisis)', action: 'confirmacion_atencion' },
  { type: 'termina_analisis', label: 'Termina análisis (→ En Ejecución)', action: 'termina_analisis' },
  { type: 'solicitud_informacion', label: 'Solicitud de información (→ Pendiente de Usuario)', action: 'solicitud_informacion' },
  { type: 'solicitud_cierre', label: 'Solicitud de cierre (→ Resuelto)', action: 'solicitud_cierre' },
  { type: 'respuesta_usuario', label: 'Respuesta de usuario (→ En Ejecución)', action: 'respuesta_usuario' },
  { type: 'comentario_interno', label: 'Comentario interno (sin cambio de estado)', action: null },
]

// OBS-0057: estado destino de cada comentario tipificado (espejo de ticket_fsm.py TRANSITIONS),
// usado solo para redactar el mensaje de confirmación — no cambia la lógica de transición en sí.
const COMMENT_DEST_STATUS: Partial<Record<CommentType, TicketStatus>> = {
  confirmacion_atencion: 'en_analisis',
  termina_analisis: 'en_ejecucion',
  solicitud_informacion: 'pendiente_usuario',
  solicitud_cierre: 'resuelto',
  respuesta_usuario: 'en_ejecucion',
}

interface CommentComposerProps {
  ticket: TicketDetail
  resolutionTypes: CatalogItem[]
  onUpdated: () => void
  /** Tarea/Subtarea (spec 009): sin tipos tipificados ni acciones de Ticket — el cambio de
   * estado se hace por `TaskStatusChanger`, este composer solo registra comentarios simples. */
  restrictToInternal?: boolean
  /** Usuario/cliente respondiendo una "Solicitud de información" (spec 046, US4/FR-009): única
   * caja disponible para este rol, y solo cuando el ticket está en `pendiente_usuario` — el
   * llamador (`TicketDetailPage`) ya se encarga de no renderizar este componente fuera de ese
   * estado. */
  clientResponseOnly?: boolean
}

/** Composer de comentarios tipificados + botones de acciones de estado (US3). */
export default function CommentComposer({ ticket, resolutionTypes, onUpdated, restrictToInternal, clientResponseOnly }: CommentComposerProps) {
  const { hasPermission } = useAuthStore()
  // OBS-0056: la instancia estática `message` de 'antd' no renderiza ningún toast en esta
  // app (mismo síntoma que OBS-0029/spec 028) — se usa la instancia ligada al `<App>` de antd.
  const { message } = App.useApp()
  const [commentType, setCommentType] = useState<CommentType>('comentario_interno')
  const [body, setBody] = useState('')
  const [bodyKey, setBodyKey] = useState(0)
  const [pendingImages, setPendingImages] = useState<File[]>([])
  const [files, setFiles] = useState<UploadFile[]>([])
  const [sending, setSending] = useState(false)
  const [closeOpen, setCloseOpen] = useState(false)
  const [closeType, setCloseType] = useState<string>()
  const [closeBody, setCloseBody] = useState('')
  const [closeBodyKey, setCloseBodyKey] = useState(0)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [cancelBody, setCancelBody] = useState('')
  const [cancelBodyKey, setCancelBodyKey] = useState(0)

  const isFinal = ticket.status === 'cerrado' || ticket.status === 'cancelado'
  const validActions = new Set(ticket.valid_actions)
  const options = COMMENT_OPTIONS.filter(o => o.action === null || validActions.has(o.action))

  const apiError = (err: unknown, fallback: string) =>
    (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? fallback

  const send = async () => {
    if (isRichTextEmpty(body)) {
      message.warning('El comentario no puede estar vacío')
      return
    }
    setSending(true)
    try {
      const effectiveType = clientResponseOnly ? 'respuesta_usuario'
        : restrictToInternal ? 'comentario_interno' : commentType
      const destStatus = COMMENT_DEST_STATUS[effectiveType]
      const rawFiles = files.map(f => f.originFileObj).filter((f): f is NonNullable<typeof f> => !!f)
      await ticketService.addComment(ticket.id, effectiveType, body, rawFiles, pendingImages)
      setBody(''); setBodyKey(k => k + 1); setPendingImages([]); setFiles([]); setCommentType('comentario_interno')
      message.success(destStatus ? `Ticket movido a "${STATUS_LABELS[destStatus]}"` : 'Comentario registrado')
      onUpdated()
    } catch (err: unknown) {
      message.error(apiError(err, 'Error al registrar el comentario'))
    } finally {
      setSending(false)
    }
  }

  const runAction = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn()
      message.success(ok)
      onUpdated()
    } catch (err: unknown) {
      message.error(apiError(err, 'La acción no pudo completarse'))
    }
  }

  if (clientResponseOnly) {
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Typography.Text type="secondary">
          El equipo de soporte solicitó información adicional. Tu respuesta quedará en el
          historial y reanudará el trabajo sobre este registro.
        </Typography.Text>
        <RichTextEditor key={bodyKey} value={body} onChange={setBody}
          placeholder="Escribe tu respuesta..." allowImages
          onPendingImage={file => setPendingImages(prev => [...prev, file])} />
        <Space>
          <Upload multiple beforeUpload={() => false} fileList={files}
            onChange={({ fileList }) => setFiles(fileList)}>
            <Button icon={<UploadOutlined />}>Adjuntar (máx 10 MB c/u)</Button>
          </Upload>
          <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={send}>
            Enviar respuesta
          </Button>
        </Space>
      </Space>
    )
  }

  if (restrictToInternal) {
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <RichTextEditor key={bodyKey} value={body} onChange={setBody}
          placeholder="Escribe un comentario..." allowImages
          onPendingImage={file => setPendingImages(prev => [...prev, file])} />
        <Space>
          <Upload multiple beforeUpload={() => false} fileList={files}
            onChange={({ fileList }) => setFiles(fileList)}>
            <Button icon={<UploadOutlined />}>Adjuntar (máx 10 MB c/u)</Button>
          </Upload>
          <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={send}>
            Registrar comentario
          </Button>
        </Space>
      </Space>
    )
  }

  if (isFinal) {
    return <em>El ticket está en estado final ({ticket.status_label}); no admite más acciones.</em>
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space wrap>
        {validActions.has('enter_testing') && (
          <Button icon={<ExperimentOutlined />}
            onClick={() => runAction(() => ticketService.toggleTesting(ticket.id, 'enter'), 'Ticket en pruebas')}>
            Pasar a pruebas
          </Button>
        )}
        {validActions.has('exit_testing') && (
          <Button icon={<ExperimentOutlined />}
            onClick={() => runAction(() => ticketService.toggleTesting(ticket.id, 'exit'), 'Ticket en ejecución')}>
            Volver a ejecución
          </Button>
        )}
        {ticket.status === 'resuelto' && (
          <>
            <Button icon={<CheckOutlined />} type="primary" ghost
              onClick={() => runAction(() => ticketService.recordResolution(ticket.id, true), 'Resolución aceptada — puedes cerrar el ticket')}>
              Usuario acepta resolución
            </Button>
            <Button icon={<CloseOutlined />} danger ghost
              onClick={() => runAction(() => ticketService.recordResolution(ticket.id, false, 'El usuario rechazó la resolución'), 'Ticket devuelto a En Ejecución')}>
              Usuario rechaza
            </Button>
            <Button icon={<LockOutlined />} type="primary" disabled={!ticket.close_eligible}
              title={ticket.close_eligible ? '' : 'Requiere aceptación del usuario o 3+ días sin respuesta'}
              onClick={() => setCloseOpen(true)}>
              Cerrar ticket
            </Button>
          </>
        )}
        {hasPermission('tickets', 'cancel') && (
          <Button icon={<StopOutlined />} danger onClick={() => setCancelOpen(true)}>Cancelar ticket</Button>
        )}
      </Space>

      <Select value={commentType} onChange={setCommentType} style={{ width: '100%' }}
        options={options.map(o => ({ value: o.type, label: o.label }))} />
      <RichTextEditor key={bodyKey} value={body} onChange={setBody}
        placeholder="Escribe el comentario..." allowImages
        onPendingImage={file => setPendingImages(prev => [...prev, file])} />
      <Space>
        <Upload multiple beforeUpload={() => false} fileList={files}
          onChange={({ fileList }) => setFiles(fileList)}>
          <Button icon={<UploadOutlined />}>Adjuntar (máx 10 MB c/u)</Button>
        </Upload>
        <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={send}>
          Registrar comentario
        </Button>
      </Space>

      <Modal title="Cerrar ticket" open={closeOpen} onCancel={() => setCloseOpen(false)}
        okText="Cerrar ticket" onOk={async () => {
          if (!closeType || isRichTextEmpty(closeBody)) {
            message.warning('Tipo de resolución y descripción de la solución son requeridos')
            return
          }
          await runAction(() => ticketService.close(ticket.id, closeType, closeBody), 'Ticket cerrado')
          setCloseOpen(false); setCloseBody(''); setCloseBodyKey(k => k + 1)
        }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Select placeholder="Tipo de resolución" style={{ width: '100%' }} value={closeType}
            onChange={setCloseType}
            options={resolutionTypes.map(t => ({ value: t.id, label: t.name }))} />
          <RichTextEditor key={closeBodyKey} value={closeBody} onChange={setCloseBody}
            placeholder="Descripción de la solución (obligatoria)" />
        </Space>
      </Modal>

      <Modal title="Cancelar ticket" open={cancelOpen} onCancel={() => setCancelOpen(false)}
        okText="Cancelar ticket" okButtonProps={{ danger: true }} onOk={async () => {
          if (isRichTextEmpty(cancelBody)) {
            message.warning('El motivo de cancelación es requerido')
            return
          }
          await runAction(() => ticketService.cancel(ticket.id, cancelBody), 'Ticket cancelado')
          setCancelOpen(false); setCancelBody(''); setCancelBodyKey(k => k + 1)
        }}>
        <RichTextEditor key={cancelBodyKey} value={cancelBody} onChange={setCancelBody}
          placeholder="Motivo de la cancelación (obligatorio)" />
      </Modal>
    </Space>
  )
}
