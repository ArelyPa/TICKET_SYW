import apiClient from './apiClient'
import type { TimeImportPreview, TimeImportConfirmRow, TimeImportConfirmResult } from '../types/timeImport'

export const timeImportService = {
  previewFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<TimeImportPreview>('/api/time-imports/preview', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  confirm: (rows: TimeImportConfirmRow[]) =>
    apiClient.post<TimeImportConfirmResult>('/api/time-imports/confirm', { rows }).then(r => r.data),
}
