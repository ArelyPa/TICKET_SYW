import apiClient from './apiClient'
import type {
  TeamworkTaskImportFilter, TeamworkTaskImportPreviewResult, TeamworkTaskImportConfirmResult,
} from '../types/teamworkTaskImport'

export const teamworkTaskImportService = {
  preview: (filter: TeamworkTaskImportFilter) =>
    apiClient.post<TeamworkTaskImportPreviewResult>(
      '/api/teamwork-integration/task-imports/preview', filter,
    ).then(r => r.data),

  confirm: (filter: TeamworkTaskImportFilter) =>
    apiClient.post<TeamworkTaskImportConfirmResult>(
      '/api/teamwork-integration/task-imports/confirm', filter,
    ).then(r => r.data),
}
