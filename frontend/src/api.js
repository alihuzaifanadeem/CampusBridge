const API = '/api'

export async function request(path, options = {}, token = localStorage.getItem('cb.token')) {
  const headers = new Headers(options.headers || {})
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API}${path}`, { ...options, headers })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    const error = new Error(data.detail || `Request failed (${response.status})`)
    error.status = response.status
    throw error
  }
  if (response.status === 204) return null
  return response.json()
}

export const postJson = (path, body, token) => request(path, { method: 'POST', body: JSON.stringify(body) }, token)
export const patchJson = (path, body, token) => request(path, { method: 'PATCH', body: JSON.stringify(body) }, token)
export const putJson = (path, body, token) => request(path, { method: 'PUT', body: JSON.stringify(body) }, token)
export const putForm = (path, body, token) => request(path, { method: 'PUT', body }, token)
