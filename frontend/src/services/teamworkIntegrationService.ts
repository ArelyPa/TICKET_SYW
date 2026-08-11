import apiClient from './apiClient'
import type {
  TeamworkIntegrationConfig, TeamworkIntegrationConfigInput, TeamworkTestConnectionResult,
  TeamworkEntityMapping, TeamworkEntityType, TeamworkSyncResult,
  TeamworkCreateNewCandidates, TeamworkCreateNewPayload, TeamworkCreateNewResult,
  TeamworkBulkCreateNewPayload, TeamworkBulkCreateNewResult, TeamworkTaskSyncResult,
  TeamworkMigratedRefs, TeamworkMigratedRefsEntityType,
  TeamworkBulkStatusPayload, TeamworkBulkStatusResult,
} from '../types/teamworkIntegration'

export const teamworkIntegrationService = {
  getConfig: () =>
    apiClient.get<TeamworkIntegrationConfig>('/api/teamwork-integration/config').then(r => r.data),

  saveConfig: (config: TeamworkIntegrationConfigInput) =>
    apiClient.put<TeamworkIntegrationConfig>('/api/teamwork-integration/config', config)
      .then(r => r.data),

  testConnection: () =>
    apiClient.post<TeamworkTestConnectionResult>('/api/teamwork-integration/test-connection')
      .then(r => r.data),

  syncCatalog: (entityType: TeamworkEntityType) =>
    apiClient.post<TeamworkSyncResult>(`/api/teamwork-integration/sync/${entityType}`)
      .then(r => r.data),

  listEntityMappings: (entityType?: TeamworkEntityType) =>
    apiClient.get<{ rows: TeamworkEntityMapping[] }>('/api/teamwork-integration/entity-mappings', {
      params: entityType ? { entity_type: entityType } : undefined,
    }).then(r => r.data.rows),

  setEntityMapping: (mappingId: string, sytixId: string | null) =>
    apiClient.put<TeamworkEntityMapping>(`/api/teamwork-integration/entity-mappings/${mappingId}`,
      { sytix_id: sytixId }).then(r => r.data),

  getCreateNewCandidates: (mappingId: string) =>
    apiClient.get<TeamworkCreateNewCandidates>(
      `/api/teamwork-integration/entity-mappings/${mappingId}/create-new-candidates`,
    ).then(r => r.data),

  createNew: (mappingId: string, payload: TeamworkCreateNewPayload) =>
    apiClient.post<TeamworkCreateNewResult>(
      `/api/teamwork-integration/entity-mappings/${mappingId}/create-new`, payload,
    ).then(r => r.data),

  bulkCreateNew: (payload: TeamworkBulkCreateNewPayload) =>
    apiClient.post<TeamworkBulkCreateNewResult>(
      '/api/teamwork-integration/entity-mappings/bulk-create-new', payload,
    ).then(r => r.data),

  bulkDiscard: (payload: TeamworkBulkStatusPayload) =>
    apiClient.post<TeamworkBulkStatusResult>(
      '/api/teamwork-integration/entity-mappings/bulk-discard', payload,
    ).then(r => r.data),

  bulkReactivate: (payload: TeamworkBulkStatusPayload) =>
    apiClient.post<TeamworkBulkStatusResult>(
      '/api/teamwork-integration/entity-mappings/bulk-reactivate', payload,
    ).then(r => r.data),

  syncTasks: () =>
    apiClient.post<TeamworkTaskSyncResult>('/api/teamwork-integration/sync/tasks').then(r => r.data),

  // research.md Decisión 7 (spec 044 US5): `X-Skip-Error-Notify` evita un toast de error 403
  // espurio para roles que ven la pantalla principal pero no tienen `teamwork_integration:operate`
  // (mismo patrón que `calendarService.listAbsenceRequestsForResource`) — la llamada en sí solo
  // debe hacerse si `hasPermission('teamwork_integration', 'operate')` ya la habilitó.
  getMigratedRefs: (sytixEntityType: TeamworkMigratedRefsEntityType) =>
    apiClient.get<TeamworkMigratedRefs>('/api/teamwork-integration/migrated-refs', {
      params: { sytix_entity_type: sytixEntityType },
      headers: { 'X-Skip-Error-Notify': 'true' },
    }).then(r => r.data),
}
