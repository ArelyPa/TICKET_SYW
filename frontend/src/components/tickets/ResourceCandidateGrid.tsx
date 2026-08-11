import { useMemo, useState } from 'react'
import { Input, Tag, Tooltip } from 'antd'
import { FireOutlined, WarningOutlined } from '@ant-design/icons'
import type { Resource } from '../../types/resource'
import type { Availability, AvailabilityReason } from '../../types/calendar'
import { avatarColor, initials, palette, vivid } from '../../theme'

// FR-014 (spec 020): motivo legible por resolutor no disponible (fuera de horario, festivo o
// ausencia aprobada). Nunca bloquea la selección (FR-015) — es solo un indicador informativo.
const UNAVAILABLE_LABELS: Record<Exclude<AvailabilityReason, null>, string> = {
  outside_hours: 'Fuera de horario',
  holiday: 'Festivo',
  absence: 'Ausencia aprobada',
}

const WORKLOAD_SCALE = 8 // referencia visual (no es un límite real de capacidad)

function workloadColor(count: number): string {
  if (count >= 6) return vivid.red.text
  if (count >= 3) return vivid.gold.text
  return vivid.green.text
}

interface ResourceCandidateGridProps {
  resources: Resource[]
  workload: Record<string, number>
  availability: Record<string, Availability>
  selected: string | undefined
  onSelect: (resourceId: string) => void
  /** spec 041 (FR-013): rol de negocio por candidato — 'Resolutor' si se omite, para no romper
   * a los consumidores que todavía no la pasan. */
  candidateRoles?: Record<string, 'Resolutor' | 'Coordinador'>
}

/** Grid de tarjetas de recurso con carga y disponibilidad — extraído de `AssignModal` (Triage
 * Push, spec 010/020) para que la reasignación (spec 024) muestre "las mismas sugerencias".
 * Componente "tonto": solo recibe los candidatos ya resueltos y notifica la selección. */
export default function ResourceCandidateGrid({
  resources, workload, availability, selected, onSelect, candidateRoles,
}: ResourceCandidateGridProps) {
  const [search, setSearch] = useState('')

  const sorted = useMemo(() => {
    const filtered = resources.filter(r => r.full_name.toLowerCase().includes(search.toLowerCase()))
    return [...filtered].sort((a, b) => (workload[a.id] ?? 0) - (workload[b.id] ?? 0))
  }, [resources, workload, search])

  const lightestLoadId = useMemo(() => {
    if (resources.length === 0) return null
    return [...resources].sort((a, b) => (workload[a.id] ?? 0) - (workload[b.id] ?? 0))[0]?.id ?? null
  }, [resources, workload])

  return (
    <>
      <Input.Search
        placeholder="Buscar resolutor..."
        allowClear
        value={search}
        onChange={e => setSearch(e.target.value)}
        style={{ marginBottom: 12 }}
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10, maxHeight: 340, overflowY: 'auto', paddingRight: 4 }}>
        {sorted.map(r => {
          const count = workload[r.id] ?? 0
          const isSelected = selected === r.id
          const color = avatarColor(r.id)
          const isLightest = r.id === lightestLoadId
          const avail = availability[r.id]
          const isUnavailable = avail && !avail.available
          return (
            <div
              key={r.id}
              onClick={() => onSelect(r.id)}
              style={{
                cursor: 'pointer', borderRadius: 10, padding: 12,
                border: `2px solid ${isSelected ? palette.brandOrange500 : palette.slate200}`,
                background: isSelected ? palette.brandOrange50 : '#fff',
                position: 'relative',
              }}
            >
              {isLightest && (
                <Tooltip title="Resolutor con menor carga actual">
                  <Tag color="success" style={{ position: 'absolute', top: -9, right: 8, fontSize: 10 }}>
                    Menor carga
                  </Tag>
                </Tooltip>
              )}
              {isUnavailable && (
                <Tooltip title={avail.detail ?? 'No disponible en este momento'}>
                  <Tag color="error" icon={<WarningOutlined />}
                    style={{ position: 'absolute', top: -9, left: 8, fontSize: 10 }}>
                    {avail.reason ? UNAVAILABLE_LABELS[avail.reason] : 'No disponible'}
                  </Tag>
                </Tooltip>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', background: color.bg, color: color.text, fontWeight: 700, fontSize: 12,
                }}>
                  {initials(r.full_name)}
                </div>
                <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.2 }}>{r.full_name}</div>
              </div>
              {candidateRoles?.[r.id] === 'Coordinador' && (
                <Tag color="purple" style={{ fontSize: 10, marginBottom: 6 }}>Coordinador</Tag>
              )}
              <div style={{ marginBottom: 8, minHeight: 22 }}>
                {r.skills.length > 0
                  ? r.skills.slice(0, 3).map(s => (
                      <Tag key={s.id} style={{ fontSize: 10, marginBottom: 2 }}>{s.code}</Tag>
                    ))
                  : <em style={{ fontSize: 11, color: palette.slate400 }}>sin skills</em>}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: palette.slate500, marginBottom: 3 }}>
                <span>Carga actual</span>
                <span style={{ fontWeight: 700, color: workloadColor(count) }}>
                  {count >= 6 && <FireOutlined style={{ marginRight: 2 }} />}
                  {count}
                </span>
              </div>
              <div style={{ height: 5, background: palette.slate100, borderRadius: 3 }}>
                <div style={{
                  height: 5, borderRadius: 3, background: workloadColor(count),
                  width: `${Math.min(100, (count / WORKLOAD_SCALE) * 100)}%`,
                }} />
              </div>
            </div>
          )
        })}
        {sorted.length === 0 && <em style={{ color: palette.slate400 }}>Sin resolutores activos que coincidan</em>}
      </div>
    </>
  )
}
