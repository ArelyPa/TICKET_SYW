export type TimeImportRowStatus = 'valid' | 'conflict' | 'error'

export interface TimeImportRowResolved {
  who_name: string | null
  company_name: string | null
  project_name: string | null
  task_reference: string | null
  description: string
  started_at: string | null
  ended_at: string | null
  duration_minutes: number | null
  resource_id: string | null
  client_id: string | null
  project_id: string | null
  ticket_id: string | null
  duplicate_in_file: boolean
}

export interface TimeImportRow {
  source_row_number: number
  external_time_id: string | null
  status: TimeImportRowStatus
  issues: string[]
  resolved: TimeImportRowResolved
}

export interface TimeImportPreview {
  rows: TimeImportRow[]
  summary: { total: number; valid: number; conflict: number; error: number }
}

export type TimeImportRowAction = 'resolve' | 'create' | 'omit'

/** El backend no persiste nada entre preview y confirm — cada fila de `/confirm` es la misma
 * fila devuelta por `/preview` (con su `resolved` completo), más `action`/`create_entity_type`
 * cuando el usuario resolvió un conflicto. */
export type TimeImportConfirmRow = Partial<TimeImportRow> & {
  source_row_number: number
  action?: TimeImportRowAction
  create_entity_type?: 'resource' | 'client'
}

export interface TimeImportConfirmResult {
  created_time_entries: number
  updated_time_entries: number
  created_resources: number
  created_clients: number
  skipped: number
  errors: { source_row_number: number; reason: string }[]
}

/** Etiquetas legibles de `issues` (códigos estables devueltos por el backend). */
export const TIME_IMPORT_ISSUE_LABELS: Record<string, string> = {
  who_not_found: 'Usuario (Who) no encontrado en SYTIX',
  project_not_found: 'Proyecto no encontrado en SYTIX',
  task_not_found: 'Tarea/Ticket no encontrado en SYTIX',
  description_missing: 'Descripción vacía',
  duplicate_external_id_in_file: 'ID de Teamwork repetido en el archivo',
  duration_inconsistent: 'Sin duración registrada (Hours/Minutes/Decimal hours)',
}
