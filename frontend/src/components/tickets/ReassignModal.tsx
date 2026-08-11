import { useEffect, useMemo, useState } from 'react'
import { App, Input, Modal } from 'antd'
import { SwapOutlined } from '@ant-design/icons'
import { ticketService } from '../../services/ticketService'
import { useResourceCandidates } from './useResourceCandidates'
import ResourceCandidateGrid from './ResourceCandidateGrid'

interface ReassignModalProps {
  ticketId: string | null
  currentAssigneeId: string | null
  onClose: () => void
  onReassigned: () => void
}

/** Reasignación de resolutor (spec 023) — corrige errores de asignación o escala por
 * complejidad, sin cambiar el estado del ticket. Muestra la misma carga y disponibilidad que
 * la asignación inicial (spec 024, "las mismas sugerencias... como la asignación inicial"). */
export default function ReassignModal({ ticketId, currentAssigneeId, onClose, onReassigned }: ReassignModalProps) {
  const { message } = App.useApp()
  const { resources, workload, availability, candidateRoles } = useResourceCandidates(!!ticketId)
  const [selected, setSelected] = useState<string | undefined>()
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (ticketId) {
      setSelected(undefined)
      setReason('')
    }
  }, [ticketId])

  // El resolutor actualmente asignado no es un candidato de reasignación (spec 023, FR-010).
  const candidates = useMemo(
    () => resources.filter(r => r.id !== currentAssigneeId),
    [resources, currentAssigneeId],
  )

  const doReassign = async () => {
    if (!ticketId || !selected) {
      message.warning('Selecciona el nuevo resolutor')
      return
    }
    setLoading(true)
    try {
      const { missing_skills } = await ticketService.reassign(ticketId, selected, reason || undefined)
      if (missing_skills.length > 0) {
        message.warning(`Reasignado — el nuevo resolutor no tiene: ${missing_skills.join(', ')}`)
      } else {
        message.success('Ticket reasignado')
      }
      onReassigned()
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Error al reasignar'
      message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="Reasignar ticket"
      open={!!ticketId}
      onCancel={onClose}
      onOk={doReassign}
      okText="Reasignar"
      okButtonProps={{ icon: <SwapOutlined />, loading, disabled: !selected }}
      confirmLoading={loading}
      width={680}
    >
      <ResourceCandidateGrid
        resources={candidates}
        workload={workload}
        availability={availability}
        candidateRoles={candidateRoles}
        selected={selected}
        onSelect={setSelected}
      />
      <Input.TextArea
        placeholder="Motivo de la reasignación (opcional)"
        value={reason}
        onChange={e => setReason(e.target.value)}
        rows={2}
        style={{ marginTop: 12 }}
      />
    </Modal>
  )
}
