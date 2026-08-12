import apiClient from './apiClient'
import type { AuthUser } from '../store/authStore'

export interface LoginResponse {
  access_token: string
  user: AuthUser
}

export interface MeResponse {
  user: AuthUser
}

/** spec 046 (FR-001/003): pestaña de Login elegida — 'team' (Equipo/Empleados) o
 * 'client_portal' (Portal de Clientes/Colaboradores). El backend rechaza el login si el rol
 * de la cuenta no coincide. */
export type LoginMode = 'team' | 'client_portal'

export const authService = {
  login: (username_or_email: string, password: string, login_mode?: LoginMode) =>
    apiClient.post<LoginResponse>('/api/auth/login', { username_or_email, password, login_mode }).then(r => r.data),

  google: (id_token: string) =>
    apiClient.post<LoginResponse>('/api/auth/google', { id_token }).then(r => r.data),

  me: () =>
    apiClient.get<MeResponse>('/api/auth/me').then(r => r.data),

  forgotPassword: (email: string) =>
    apiClient.post<{ message: string }>('/api/auth/forgot-password', { email }).then(r => r.data),

  resetPassword: (token: string, new_password: string) =>
    apiClient.post<{ message: string }>('/api/auth/reset-password', { token, new_password }).then(r => r.data),
}
