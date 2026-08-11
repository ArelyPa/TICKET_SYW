import { useEffect, useState } from 'react'
import { Alert, App, Button, Empty, Modal, Radio, Space, Segmented } from 'antd'
import { UserSwitchOutlined, ExperimentOutlined, BulbOutlined } from '@ant-design/icons'
import { ticketService } from '../../services/ticketService'
import type { QmCandidate } from '../../services/ticketService'
import { useResourceCandidates } from './useResourceCandidates'
import ResourceCandidateGrid from './ResourceCandidateGrid'

interface AssignModalProps {
  ticketId: string | null
  onClose: () => void
  onAssigned: () => void
  /** Si viene de un arrastre en el Kanban, fuerza un único modo y oculta el otro botón. */
  forcedMode?: 'resolver' | 'pre_analysis'
}

/** Selector de resolutor con skills y carga real (Triage Push, US2). OBS-0052/0053: candidatos
 * de "Pre-Análisis" se listan por rol QM (no por la tabla de recursos) en una grilla separada, y
 * el modo activo decide qué acción queda habilitada — ya no se puede enviar un resolutor a
 * Pre-Análisis ni un QM como resolutor. */
export default function AssignModal({ ticketId, onClose, onAssigned, forcedMode }: AssignModalProps) {
  const { message } = App.useApp()
  const { resources, workload, availability, candidateRoles } = useResourceCandidates(!!ticketId && forcedMode !== 'pre_analysis')
  const [qmCandidates, setQmCandidates] = useState<QmCandidate[]>([])
  const [mode, setMode] = useState<'resolver' | 'pre_analysis'>(forcedMode ?? 'resolver')
  const [selected, setSelected] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (ticketId) {
      setSelected(undefined)
      setMode(forcedMode ?? 'resolver')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticketId])

  useEffect(() => {
    if (!ticketId || (forcedMode && forcedMode !== 'pre_analysis')) return
    ticketService.qmCandidates().then(setQmCandidates).catch(() => message.error('No se pudo cargar la lista de QMs'))
  }, [ticketId, forcedMode, message])

  const doAssign = async () => {
    if (!ticketId || !selected) {
      message.warning('Selecciona un candidato')
      return
    }
    setLoading(true)
    try {
      await ticketService.assign(ticketId, selected, mode)
      message.success(mode === 'resolver' ? 'Ticket asignado (→ Contacto)' : 'Enviado a Pre-Análisis (QM)')
      onAssigned()
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al asignar'
      message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title={mode === 'pre_analysis' ? 'Enviar a Pre-Análisis (QM)' : 'Asignar ticket (Triage Push)'}
      open={!!ticketId}
      onCancel={onClose}
      width={680}
      footer={[
        <Button key="cancel" onClick={onClose}>Cancelar</Button>,
        <Button key="do" type="primary"
          icon={mode === 'pre_analysis' ? <ExperimentOutlined /> : <UserSwitchOutlined />}
          loading={loading} disabled={!selected} onClick={doAssign}>
          {mode === 'pre_analysis' ? 'Pre-Análisis (QM)' : 'Asignar resolutor'}
        </Button>,
      ]}
    >
      {!forcedMode && (
        <Segmented
          style={{ marginBottom: 12 }}
          value={mode}
          onChange={v => { setMode(v as 'resolver' | 'pre_analysis'); setSelected(undefined) }}
          options={[
            { label: 'Resolutor', value: 'resolver' },
            { label: 'Pre-Análisis (QM)', value: 'pre_analysis' },
          ]}
        />
      )}

      {mode === 'resolver' ? (
        <>
          <Alert
            type="info"
            showIcon
            icon={<BulbOutlined />}
            style={{ marginBottom: 12, background: '#F9F0FF', borderColor: '#EFDBFF' }}
            message="Sugerencia por IA — disponible en Fase 7 (Triage Agent)"
            description="Por ahora los resolutores se ordenan por menor carga actual. La recomendación automática por historial y patrones llegará con el AI Dispatcher."
          />
          <ResourceCandidateGrid
            resources={resources}
            workload={workload}
            availability={availability}
            candidateRoles={candidateRoles}
            selected={selected}
            onSelect={setSelected}
          />
        </>
      ) : (
        <>
          <Alert
            type="info" showIcon style={{ marginBottom: 12 }}
            message="Candidatos por rol QM"
            description="Los QM no tienen perfil de recurso propio (spec 010) — esta lista se arma por rol, no por la grilla de resolutores."
          />
          {qmCandidates.filter(c => c.active).length === 0 ? (
            <Empty description="Sin usuarios con rol QM activos" />
          ) : (
            <Radio.Group value={selected} onChange={e => setSelected(e.target.value)} style={{ width: '100%' }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                {qmCandidates.filter(c => c.active).map(c => (
                  <Radio key={c.id} value={c.id} style={{ width: '100%' }}>{c.full_name}</Radio>
                ))}
              </Space>
            </Radio.Group>
          )}
        </>
      )}
    </Modal>
  )
}
