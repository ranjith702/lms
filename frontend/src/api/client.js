// One place for every HTTP call: parses errors, logs out on 401.
// Auth rides in the httpOnly `lms_session` cookie the backend sets at login. JavaScript never
// sees the token, so there is nothing for an XSS bug to steal from localStorage.

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status }
}

export async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' }

  let res
  try {
    res = await fetch(`/api${path}`, {
      method, headers, body: body ? JSON.stringify(body) : undefined,
      credentials: 'same-origin',   // send the auth cookie (same origin thanks to the Vite proxy)
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the backend running on port 8000?')
  }
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    // A 401 anywhere except the login form itself means the session is gone.
    if (res.status === 401 && path !== '/auth/login') onUnauthorized()
    const detail = data?.detail
    const message = Array.isArray(detail)
      ? detail.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join(', ')   // FastAPI validation errors
      : detail || `Request failed (${res.status})`
    throw new ApiError(res.status, message)
  }
  return data
}

export const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'
export const fmtDateTime = (iso) =>
  iso ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'
