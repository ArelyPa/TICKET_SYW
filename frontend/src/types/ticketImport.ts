export type ImportRowStatus = 'ready' | 'needs_review' | 'error'

export interface ImportRowResolved {
  title: string | null
  description: string
  start_date: string | null
  due_date: string | null
  estimated_minutes: number
  estimated_hours: number
  company_name: string | null
  project_name: string | null
  list_name: string | null
  assignee_name: string | null
  requester_name: string | null
  parent_external_id: string | null
  client_id: string | null
  project_id: string | null
  assignee_resource_id: string | null
  requester_created_by_user_id: string | null
  requester_client_contact_id: string | null
  duplicate_in_file: boolean
  parent_resolved_external_id: string | null
  existing_ticket_id: string | null
}

export interface ImportRow {
  source_row_number: number
  external_id: string | null
  status: ImportRowStatus
  issues: string[]
  resolved: ImportRowResolved
}

export interface ImportPreviewResponse {
  rows: ImportRow[]
  summary: { total: number; ready: number; needs_review: number; error: number }
}

export interface ImportConfirmResult {
  created: number
  updated: number
  errors: { source_row_number: number; reason: string }[]
}

/** Etiquetas legibles de `issues` (códigos estables devueltos por el backend) para la vista previa. */
export const IMPORT_ISSUE_LABELS: Record<string, string> = {
  duplicate_external_id_in_file: 'ID de Teamwork repetido en el archivo',
  client_not_found: 'Cliente no encontrado en SYTIX',
  project_not_found: 'Proyecto no encontrado en SYTIX',
  assignee_not_found: 'Asignado no encontrado en SYTIX',
  creator_not_found: 'Solicitante no encontrado en SYTIX',
  parent_not_found_in_batch: 'Tarea padre no incluida en el lote (se importa como Tarea de primer nivel)',
}
