export type TeamworkTestStatus = 'success' | 'auth_error' | 'connection_error' | null

export interface TeamworkIntegrationConfig {
  site_url: string | null
  environment: 'test' | 'production' | null
  has_token: boolean
  last_test_status: TeamworkTestStatus
  last_test_at: string | null
  last_test_message: string | null
}

export interface TeamworkIntegrationConfigInput {
  site_url: string
  environment: 'test' | 'production'
  api_token?: string
}

export interface TeamworkTestConnectionResult {
  status: TeamworkTestStatus
  message: string | null
}

export type TeamworkEntityType = 'company' | 'project' | 'person' | 'tasklist'

export type TeamworkMigrationStatus = 'pending' | 'linked' | 'created' | 'inactive'

export interface TeamworkCompanyMetadata {
  country?: string
  address?: string
  domain?: string
  phone?: string
}

export interface TeamworkPersonMetadata {
  job_title?: string
  timezone?: string
}

export interface TeamworkProjectMetadata {
  description?: string
  status?: 'active' | 'archived'
}

export type TeamworkEntityMetadata =
  | TeamworkCompanyMetadata
  | TeamworkPersonMetadata
  | TeamworkProjectMetadata

export interface TeamworkParentContext {
  status: 'unmapped' | 'pending' | 'resolved'
  client_label: string | null
  project_label: string | null
  client_id: string | null
  project_id: string | null
}

export interface TeamworkEntityMapping {
  id: string
  entity_type: TeamworkEntityType
  teamwork_id: string
  teamwork_name: string | null
  sytix_entity_type: string | null
  sytix_id: string | null
  sytix_name: string | null
  match_method: 'email' | 'external_id' | 'name' | 'manual' | 'created_new' | null
  teamwork_email: string | null
  teamwork_metadata: TeamworkEntityMetadata | null
  migration_status: TeamworkMigrationStatus
  parent_context?: TeamworkParentContext
}

export interface TeamworkCreateNewCandidates {
  defaults: { name?: string | null; email?: string | null }
  roles?: { id: string; name: string }[]
  clients?: { id: string; name: string }[]
}

export interface TeamworkCreateNewPayload {
  role_id?: string
  client_id?: string | null
}

export interface TeamworkCreateNewResult {
  mapping: TeamworkEntityMapping
  created: { id: string; name: string | null }
}

export interface TeamworkSyncResult {
  entity_type: TeamworkEntityType
  synced: number
  new: number
  updated: number
}

export interface TeamworkBulkCreateNewPayload {
  mapping_ids: string[]
  /** Requerido solo si la selección incluye filas entity_type='person' */
  role_id?: string
  client_id?: string | null
}

export interface TeamworkBulkCreateNewResult {
  created: { mapping_id: string; sytix_id: string; sytix_name: string | null }[]
  skipped: { mapping_id: string; reason: string }[]
}

export interface TeamworkBulkStatusPayload {
  mapping_ids: string[]
}

export interface TeamworkBulkStatusResult {
  updated: { mapping_id: string }[]
  skipped: { mapping_id: string; reason: string }[]
}

export interface TeamworkTaskSyncResult {
  synced: number
  created: number
  updated: number
  skipped: { teamwork_id: string; reason: string }[]
}

export type TeamworkMigratedRefsEntityType = 'client' | 'project' | 'task_list' | 'resource' | 'user'

export interface TeamworkMigratedRefs {
  sytix_ids: string[]
}

export const TEAMWORK_ENTITY_TYPE_LABELS: Record<TeamworkEntityType, string> = {
  company: 'Clientes / Empresas',
  project: 'Proyectos',
  person: 'Personal',
  tasklist: 'Listas de Tareas',
}
