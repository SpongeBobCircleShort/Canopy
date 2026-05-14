const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)
  if (!response.ok) {
    let message = `Request failed with ${response.status}`
    try {
      const body = await response.json()
      message = body.detail || message
    } catch {
      // Keep fallback message when the response body is not JSON.
    }
    throw new Error(message)
  }
  if (response.status === 204) return null
  return response.json()
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchHealth() {
  return request('/api/health')
}

export async function fetchMe(token) {
  return request('/api/auth/me', { headers: authHeaders(token) })
}

export async function fetchAlerts(token, params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  return request(`/api/alerts${search.toString() ? `?${search}` : ''}`, { headers: authHeaders(token) })
}

export async function fetchSensors(token) {
  return request('/api/sensors', { headers: authHeaders(token) })
}

export async function fetchRegions(token) {
  return request('/api/regions', { headers: authHeaders(token) })
}

export async function signup({ name, email, password, organization_name, invite_token }) {
  return request('/api/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password, organization_name, invite_token }),
  })
}

export async function login({ email, password }) {
  return request('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
}


export async function fetchInvites(token, orgId) {
  return request(`/api/organizations/${orgId}/invites`, { headers: authHeaders(token) })
}

export async function createInvite(token, orgId, payload) {
  return request(`/api/organizations/${orgId}/invites`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(payload),
  })
}

export async function revokeInvite(token, orgId, inviteId) {
  return request(`/api/organizations/${orgId}/invites/${inviteId}/revoke`, {
    method: 'POST',
    headers: authHeaders(token),
  })
}

export async function createRegion(token, payload) {
  return request('/api/regions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(payload),
  })
}

export async function createSensor(token, payload) {
  return request('/api/sensors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(payload),
  })
}

export async function uploadClip(token, { sensorId, file }) {
  const formData = new FormData()
  formData.set('sensor_id', sensorId)
  formData.set('file', file)
  return request('/api/clips/upload', {
    method: 'POST',
    headers: authHeaders(token),
    body: formData,
  })
}

export async function updateAlertStatus(token, alertId, payload) {
  return request(`/api/alerts/${alertId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(payload),
  })
}

export function exportAlertsUrl() {
  return `${API_BASE_URL}/api/alerts/export?format=csv`
}

export async function downloadAlertsCsv(token) {
  const response = await fetch(exportAlertsUrl(), { headers: authHeaders(token) })
  if (!response.ok) throw new Error(`Export failed with ${response.status}`)
  return response.blob()
}
