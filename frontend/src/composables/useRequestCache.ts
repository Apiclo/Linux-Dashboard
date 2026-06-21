// Simple in-flight request deduplication
const _pending = new Map<string, Promise<any>>()
const _cache = new Map<string, { data: any; ts: number }>()

export function useRequestCache<T>(key: string, fetcher: () => Promise<T>, ttl = 30000): Promise<T> {
  // Return cached value if fresh
  const cached = _cache.get(key)
  if (cached && Date.now() - cached.ts < ttl) {
    return Promise.resolve(cached.data as T)
  }
  // Return in-flight promise if already loading
  const pending = _pending.get(key)
  if (pending) return pending as Promise<T>
  // Fetch and cache
  const p = fetcher().then(data => {
    _cache.set(key, { data, ts: Date.now() })
    _pending.delete(key)
    return data
  }).catch(err => {
    _pending.delete(key)
    throw err
  })
  _pending.set(key, p)
  return p
}
