import { api } from './request'

export const authApi = {
  login: (username: string, password: string) => api<{ success: boolean; message: string; username: string }>('/auth/login', { method: 'POST', body: { username, password } }),
  logout: () => api<{ success: boolean }>('/auth/logout', { method: 'POST' }),
  status: () => api<{ authenticated: boolean; username?: string }>('/auth/status'),
}
