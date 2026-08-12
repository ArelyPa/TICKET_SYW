import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { TicketStatus, Priority, Severity, EscalationLevel } from '../types/ticket'

export interface TicketFilterCriteria {
  search?: string
  status?: TicketStatus[]
  client_id?: string
  priority?: Priority
  severity?: Severity
  /** Solo lo usa el Kanban (no tiene equivalente en Tickets/Mis Tareas). */
  escalation_level?: EscalationLevel
  /** Sentinel especial `'__me__'`: se resuelve en runtime al `resource_id` del usuario actual
   * (ver `SavedFiltersBar`, `resourceService.me()`) — solo lo usa el preset "Asignado a mí", así
   * sigue siendo válido aunque cambie el recurso asociado al usuario (research.md Decisión 3). */
  assignee_id?: string
  /** spec 046 (US6): "Asignado a mí" para Usuario/cliente — creador o solicitante explícito.
   * Independiente del sentinel `assignee_id: '__me__'` (ese es para Resolutor/recurso). */
  mine?: boolean
}

export interface SavedFilter {
  id: string
  name: string
  criteria: TicketFilterCriteria
  /** `true` únicamente para el preset por defecto "Asignado a mí" — no eliminable (FR-015). */
  builtIn?: boolean
}

const ASSIGNED_TO_ME_FILTER: SavedFilter = {
  id: 'builtin-assigned-to-me',
  name: 'Asignado a mí',
  criteria: { assignee_id: '__me__' },
  builtIn: true,
}

interface SavedFiltersState {
  filtersByUser: Record<string, SavedFilter[]>
  /** Incluye siempre el preset "Asignado a mí" primero, sin persistirlo (FR-015). */
  listFilters: (userId: string) => SavedFilter[]
  addFilter: (userId: string, name: string, criteria: TicketFilterCriteria) => { ok: true } | { ok: false; error: string }
  removeFilter: (userId: string, id: string) => void
}

/** Filtros guardados de "Tickets"/"Mis Tareas" (Fase 2.2, US3) — persistidos en `localStorage`
 * del navegador, namespaced por `userId` (mismo patrón `persist` que `authStore.ts`). Sin tabla
 * ni endpoint de backend (ver research.md Decisión 3). */
export const useSavedFiltersStore = create<SavedFiltersState>()(
  persist(
    (set, get) => ({
      filtersByUser: {},

      listFilters: (userId) => [ASSIGNED_TO_ME_FILTER, ...(get().filtersByUser[userId] ?? [])],

      addFilter: (userId, name, criteria) => {
        const trimmed = name.trim()
        if (trimmed.length === 0) return { ok: false, error: 'El nombre es requerido' }
        const existing = get().filtersByUser[userId] ?? []
        if (existing.some(f => f.name.toLowerCase() === trimmed.toLowerCase()) || trimmed.toLowerCase() === ASSIGNED_TO_ME_FILTER.name.toLowerCase()) {
          return { ok: false, error: 'Ya existe un filtro con ese nombre' }
        }
        const newFilter: SavedFilter = {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          name: trimmed,
          criteria,
        }
        set({ filtersByUser: { ...get().filtersByUser, [userId]: [...existing, newFilter] } })
        return { ok: true }
      },

      removeFilter: (userId, id) => {
        if (id === ASSIGNED_TO_ME_FILTER.id) return
        const existing = get().filtersByUser[userId] ?? []
        set({ filtersByUser: { ...get().filtersByUser, [userId]: existing.filter(f => f.id !== id) } })
      },
    }),
    { name: 'sywork-saved-filters' },
  ),
)
