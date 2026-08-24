export const controllerApiRoot = '/api/controller/api/v1'

export function controllerToken() {
  return localStorage.getItem('controller.api.token') ?? ''
}

export async function controllerApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${controllerApiRoot}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${controllerToken()}`,
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof payload.detail === 'string' ? payload.detail : payload.detail?.code ?? JSON.stringify(payload.detail))
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
