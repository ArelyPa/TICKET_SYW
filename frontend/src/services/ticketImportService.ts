import apiClient from './apiClient'
import type { ImportPreviewResponse, ImportConfirmResult, ImportRow } from '../types/ticketImport'

export const ticketImportService = {
  previewFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<ImportPreviewResponse>('/api/ticket-imports/preview', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  previewApiV3: () =>
    apiClient.post<ImportPreviewResponse>('/api/ticket-imports/preview', { source: 'api_v3' })
      .then(r => r.data),

  confirm: (rows: ImportRow[]) =>
    apiClient.post<ImportConfirmResult>('/api/ticket-imports/confirm', { rows }).then(r => r.data),
}
