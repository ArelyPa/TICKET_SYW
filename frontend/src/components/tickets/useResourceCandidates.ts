import { useEffect, useState } from 'react'
import { App } from 'antd'
import { resourceService } from '../../services/resourceService'
import { ticketService } from '../../services/ticketService'
import { calendarService } from '../../services/calendarService'
import type { Resource } from '../../types/resource'
import type { Availability } from '../../types/calendar'

interface ResourceCandidates {
  resources: Resource[]
  workload: Record<string, number>
  availability: Record<string, Availability>
  /** spec 041 (FR-013): rol de negocio del candidato ('Resolutor' por defecto; 'Coordinador'
   * para los sintetizados desde `GET /coordinador-candidates`, sin perfil de Recurso propio). */
  candidateRoles: Record<string, 'Resolutor' | 'Coordinador'>
}

/** Objeto `Resource` mínimo para un Coordinador sin perfil de Recurso propio — permite que
 * `ResourceCandidateGrid` (que solo entiende `Resource[]`) lo liste igual que a un Resolutor;
 * el backend resuelve/aprovisiona el Recurso real al confirmar la asignación (spec 041). */
function coordinadorAsResource(candidate: { id: string; full_name: string }): Resource {
  return {
    id: candidate.id, user_id: candidate.id, full_name: candidate.full_name, email: '',
    active: true, user_active: true, notes: null, identification: null, nationality: null,
    birth_date: null, marital_status: null, contract_type: null, calendar_country: null,
    education_level: null, specialty: null, seniority: null, certifications: null, team: null,
    manager_id: null, timezone: null, schedule_mode: 'heredado', work_hour_template_id: null,
    skills: [], created_at: '',
  }
}

/** Recursos activos + candidatos Coordinador (spec 041) + carga actual + disponibilidad (Triage
 * Push, spec 010/020) — misma fuente de datos reutilizada por la reasignación (spec 024, "las
 * mismas sugerencias... como la asignación inicial"). La disponibilidad es informativa (nunca
 * bloquea, FR-015 de spec 020), por eso su fallo se ignora en silencio igual que ya hacía
 * `AssignModal`; lo mismo aplica a los candidatos Coordinador (aditivos, no bloqueantes). */
export function useResourceCandidates(enabled: boolean): ResourceCandidates {
  const { message } = App.useApp()
  const [resources, setResources] = useState<Resource[]>([])
  const [candidateRoles, setCandidateRoles] = useState<Record<string, 'Resolutor' | 'Coordinador'>>({})
  const [workload, setWorkload] = useState<Record<string, number>>({})
  const [availability, setAvailability] = useState<Record<string, Availability>>({})

  useEffect(() => {
    if (!enabled) return
    resourceService.list({ active: true, page_size: 100 }).then(r => {
      // OBS-0063: un recurso puede seguir activo como recurso de RRHH con la cuenta de
      // usuario vinculada desactivada — sin acceso al sistema, no debe ofrecerse para asignar.
      const activeResources = r.items.filter(res => res.user_active !== false)
      const roles: Record<string, 'Resolutor' | 'Coordinador'> = {}
      activeResources.forEach(res => { roles[res.id] = 'Resolutor' })
      setResources(activeResources)
      setCandidateRoles(roles)

      ticketService.coordinadorCandidates().then(candidates => {
        const existingUserIds = new Set(activeResources.map(res => res.user_id).filter(Boolean))
        const extra = candidates
          .filter(c => c.active && !existingUserIds.has(c.id))
          .map(coordinadorAsResource)
        if (extra.length === 0) return
        setResources(prev => [...prev, ...extra])
        setCandidateRoles(prev => {
          const next = { ...prev }
          extra.forEach(res => { next[res.id] = 'Coordinador' })
          return next
        })
      }).catch(() => {})
    }).catch(() => message.error('No se pudo cargar la lista de recursos'))
    ticketService.panel().then(data => {
      const map: Record<string, number> = {}
      data.matrix.forEach(row => { map[row.resource.id] = row.total })
      setWorkload(map)
    }).catch(() => message.error('No se pudo cargar la carga de los resolutores'))
    calendarService.getAvailability().then(items => {
      const map: Record<string, Availability> = {}
      items.forEach(a => { map[a.resource_id] = a })
      setAvailability(map)
    }).catch(() => {})
  }, [enabled])

  return { resources, workload, availability, candidateRoles }
}
