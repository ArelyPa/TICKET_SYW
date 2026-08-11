export interface TeamworkTaskImportFilter {
  client_id: string
  project_ids: string[]
  date_from?: string | null
  date_to?: string | null
  task_list_teamwork_id?: string | null
}

export type TeamworkTaskImportBlockReason = 'project_not_mapped' | 'tasklist_not_mapped' | 'assignee_not_mapped'

export interface TeamworkTaskImportResolveLink {
  entity_type: 'project' | 'tasklist' | 'person'
  teamwork_id: string | null
}

export interface TeamworkTaskImportDiagnosticRow {
  teamwork_id: string
  name: string
  is_subtask: boolean
  block_reason: TeamworkTaskImportBlockReason | null
  block_reason_label: string | null
  resolve_link: TeamworkTaskImportResolveLink | null
}

export interface TeamworkTaskImportPreviewResult {
  summary: { total: number; ready: number; blocked: number }
  ready: TeamworkTaskImportDiagnosticRow[]
  blocked: TeamworkTaskImportDiagnosticRow[]
}

export interface TeamworkTaskImportConfirmResult {
  summary: { created: number; updated: number; skipped: number }
  skipped: { teamwork_id: string; block_reason: string }[]
}
