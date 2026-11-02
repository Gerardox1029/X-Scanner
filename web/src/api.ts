export const API = 'http://127.0.0.1:8765/api/v1'

export type DiagnosticKind = 'storage-space' | 'storage-photo' | 'storage-file' | 'process-slow' | 'process-frozen' | 'process-heat' | 'network-offline' | 'network-slow' | 'network-page' | 'full-scan' | 'strange-case'
export type Action = { kind: string; description: string }
export type Result = { summary: string; measurements?: unknown[]; findings?: string[]; evidence?: unknown[]; limitations?: string[]; recommendations?: string[]; actions?: Action[]; actions_taken?: unknown[] }
export type Task = { id: string; kind: DiagnosticKind; params: Record<string, unknown>; status: string; progress: number; result: Result | null; error: string | null; created: string }
export type Prepared = { token: string; kind: string; description: string; consequences: string; recovery: string }

type LocalRequestInit = RequestInit & { targetAddressSpace: 'loopback' }

export function localFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const localRequest = new Request(`${API}${path}`, { ...options, mode: 'cors', targetAddressSpace: 'loopback' } as LocalRequestInit)
  return fetch(localRequest)
}

export async function request<T>(path: string, token?: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await localFetch(path, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    })
  } catch {
    throw new Error('No se pudo acceder al complemento. Comprueba que esté abierto y permite el acceso a la red local en Brave si aparece el aviso.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(body.detail || `Error HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function post<T>(path: string, token: string | undefined, body: object = {}): Promise<T> {
  return request<T>(path, token, { method: 'POST', body: JSON.stringify(body) })
}

export async function download(path: string, token: string, name: string): Promise<void> {
  const response = await localFetch(path, { headers: { Authorization: `Bearer ${token}` } })
  if (!response.ok) throw new Error(`Descarga fallida: HTTP ${response.status}`)
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
