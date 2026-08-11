import apiClient from './apiClient'
import type { PaginatedResponse } from '../types/api'
import type {
  TicketListItem, TicketDetail, TicketFormData, TicketFilters, PanelData, CommentType, TicketStatus,
  TicketReassignment,
} from '../types/ticket'

/** OBS-0052: candidato para "Pre-Análisis (QM)" — `id` es un user_id, no un resource_id. */
export interface QmCandidate {
  id: string
  full_name: string
  active: boolean
}

/** spec 041 (FR-013): candidato Coordinador para asignación en modo resolver — `id` es un
 * user_id, no un resource_id (mismo criterio que `QmCandidate`). */
export interface CoordinadorCandidate {
  id: string
  full_name: string
  active: boolean
}

function buildParams(filters: TicketFilters): URLSearchParams {
  const params = new URLSearchParams()
  const { status, ...rest } = filters
  Object.entries(rest).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  })
  status?.forEach(s => params.append('status', s))
  return params
}

export const ticketService = {
  list: (filters: TicketFilters = {}) =>
    apiClient.get<PaginatedResponse<TicketListItem>>(`/api/tickets?${buildParams(filters)}`).then(r => r.data),

  get: (id: string) =>
    apiClient.get<TicketDetail>(`/api/tickets/${id}`).then(r => r.data),

  /** `inlineImages`: imágenes pegadas en `description` (referenciadas por `data-pending-id`,
   * spec 017). `attachments`: adjuntos manuales a la descripción (US3). Con cualquiera de los
   * dos, se envía como `multipart/form-data`; si no, JSON como siempre. */
  create: (data: TicketFormData, inlineImages: File[] = [], attachments: File[] = []) => {
    if (inlineImages.length === 0 && attachments.length === 0) {
      return apiClient.post<TicketDetail>('/api/tickets', data).then(r => r.data)
    }
    const form = new FormData()
    Object.entries(data).forEach(([key, value]) => {
      if (value !== undefined && value !== null) form.set(key, String(value))
    })
    inlineImages.forEach(f => form.append('inline_images', f))
    attachments.forEach(f => form.append('attachments', f))
    return apiClient.post<TicketDetail>('/api/tickets', form,
      { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
  },

  update: (id: string, data: Partial<TicketFormData> & { estimated_resolution_minutes?: number | null }) =>
    apiClient.patch<TicketDetail>(`/api/tickets/${id}`, data).then(r => r.data),

  /** Reemplaza el set completo de Skills requeridas (spec 011) — funciona en cualquier estado
   * del ticket, sin transición ni comentario. */
  updateTicketSkills: (id: string, skillIds: string[]) =>
    apiClient.patch<TicketDetail>(`/api/tickets/${id}/skills`, { skill_ids: skillIds }).then(r => r.data),

  assign: (id: string, assignee_id: string, mode: 'resolver' | 'pre_analysis') =>
    apiClient.post<{ ticket: TicketDetail; assignment: { id: string } }>(
      `/api/tickets/${id}/assign`, { assignee_id, mode }).then(r => r.data),

  /** OBS-0052: candidatos para "Pre-Análisis (QM)" — por rol (`users`), no por la tabla de
   * recursos (los QM no tienen perfil de recurso propio). El `id` devuelto es un user_id, se usa
   * tal cual como `assignee_id` de `assign(..., mode: 'pre_analysis')`. */
  qmCandidates: () =>
    apiClient.get<QmCandidate[]>('/api/tickets/qm-candidates').then(r => r.data),

  /** spec 041 (FR-013): candidatos Coordinador para asignación/reasignación en modo resolver —
   * por rol, no por la tabla de recursos. El `id` devuelto es un user_id; `/assign` (modo
   * `resolver`) y `/reassign` lo resuelven a un recurso, aprovisionándolo si hace falta. */
  coordinadorCandidates: () =>
    apiClient.get<CoordinadorCandidate[]>('/api/tickets/coordinador-candidates').then(r => r.data),

  /** Reasignación de resolutor (spec 023) — corrige errores de asignación o escala por
   * complejidad, sin cambiar el estado del ticket. */
  reassign: (id: string, assignee_id: string, reason?: string) =>
    apiClient.post<{ ticket: TicketDetail; reassignment: TicketReassignment; missing_skills: string[] }>(
      `/api/tickets/${id}/reassign`, { assignee_id, reason }).then(r => r.data),

  addComment: (id: string, comment_type: CommentType, body: string, files: File[] = [], inlineImages: File[] = []) => {
    if (files.length === 0 && inlineImages.length === 0) {
      return apiClient.post(`/api/tickets/${id}/comments`, { comment_type, body }).then(r => r.data)
    }
    const form = new FormData()
    form.set('comment_type', comment_type)
    form.set('body', body)
    files.forEach(f => form.append('files', f))
    inlineImages.forEach(f => form.append('inline_images', f))
    return apiClient.post(`/api/tickets/${id}/comments`, form,
      { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
  },

  toggleTesting: (id: string, direction: 'enter' | 'exit') =>
    apiClient.post(`/api/tickets/${id}/testing`, { direction }).then(r => r.data),

  recordResolution: (id: string, accepted: boolean, body?: string) =>
    apiClient.post(`/api/tickets/${id}/resolution`, { accepted, body }).then(r => r.data),

  close: (id: string, resolution_type_id: string, body: string) =>
    apiClient.post<TicketDetail>(`/api/tickets/${id}/close`, { resolution_type_id, body }).then(r => r.data),

  cancel: (id: string, body: string) =>
    apiClient.post<TicketDetail>(`/api/tickets/${id}/cancel`, { body }).then(r => r.data),

  changeStatus: (id: string, status: TicketStatus, comment: string) =>
    apiClient.patch<TicketDetail>(`/api/tickets/${id}/status`, { status, comment }).then(r => r.data),

  attachmentUrl: (ticketId: string, attachmentId: string) =>
    `${apiClient.defaults.baseURL}/api/tickets/${ticketId}/attachments/${attachmentId}`,

  downloadAttachment: async (ticketId: string, attachmentId: string, filename: string) => {
    const response = await apiClient.get(`/api/tickets/${ticketId}/attachments/${attachmentId}`,
      { responseType: 'blob' })
    const url = URL.createObjectURL(response.data as Blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  },

  panel: (statuses?: string[]) => {
    const params = new URLSearchParams()
    statuses?.forEach(s => params.append('statuses', s))
    return apiClient.get<PanelData>(`/api/assignment-panel?${params}`).then(r => r.data)
  },
}
