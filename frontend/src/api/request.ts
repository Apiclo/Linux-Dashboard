import axios from 'axios'
import type { ApiResponse, TaskResponse } from '@/types/api'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Auth state shared with useAuth ──
let _authClearFn: (() => void) | null = null
let _redirecting = false

export function registerAuthClear(fn: () => void) {
  _authClearFn = fn
}

http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !_redirecting) {
      _redirecting = true
      _authClearFn?.()
      // Use hash-based navigation to avoid full page reload
      // Vue Router will pick this up
      window.location.hash = '#/login'
      // Reset flag after a short delay
      setTimeout(() => { _redirecting = false }, 1000)
    }
    return Promise.reject(err)
  }
)

export async function api<T = any>(url: string, opts?: { method?: string; body?: any }): Promise<T> {
  const method = opts?.method?.toLowerCase() || 'get'
  const res = method === 'get'
    ? await http.get<T>(url)
    : await http.post<T>(url, opts?.body)
  return res.data
}

/** File upload helper that goes through the axios instance (auth interceptor applies). */
export async function uploadFile<T = any>(url: string, file: File, fieldName = 'file'): Promise<T> {
  const fd = new FormData()
  fd.append(fieldName, file)
  const res = await http.post<T>(url, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return res.data
}

export function streamTask(taskId: string, callbacks: {
  onOutput?: (line: string) => void
  onDone?: (code: number) => void
  onError?: (msg: string) => void
}): { close: () => void } {
  const es = new EventSource(`/api/stream/${taskId}`)
  let retries = 0

  es.onmessage = (e) => {
    retries = 0
    const d = JSON.parse(e.data)
    if (d.type === 'output') callbacks.onOutput?.(d.line)
    else if (d.type === 'done') { callbacks.onDone?.(d.code); es.close() }
    else if (d.type === 'error') { callbacks.onError?.(d.message); es.close() }
  }

  es.onerror = () => {
    retries++
    if (retries > 3) {
      callbacks.onError?.('SSE connection lost')
      es.close()
    }
  }

  return { close: () => es.close() }
}
