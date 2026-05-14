import { useEffect, useState } from 'react'
import Dashboard from './components/Dashboard.jsx'
import {
  createInvite,
  createRegion,
  createSensor,
  downloadAlertsCsv,
  fetchAlerts,
  fetchHealth,
  fetchInvites,
  fetchMe,
  fetchRegions,
  fetchSensors,
  login,
  revokeInvite,
  signup,
  updateAlertStatus,
  uploadClip,
} from './api.js'

export default function App() {
  const [health, setHealth] = useState({ status: 'loading' })
  const [alerts, setAlerts] = useState([])
  const [sensors, setSensors] = useState([])
  const [regions, setRegions] = useState([])
  const [profile, setProfile] = useState(null)
  const [invites, setInvites] = useState([])
  const [token, setToken] = useState(() => window.localStorage.getItem('canopy_token') || '')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const isAuthenticated = Boolean(token)

  async function refreshData(nextToken = token) {
    const healthResult = await fetchHealth()
    setHealth(healthResult)
    if (!nextToken) {
      setAlerts([])
      setSensors([])
      setRegions([])
      setProfile(null)
      setInvites([])
      return
    }
    const profileResult = await fetchMe(nextToken)
    const [alertsResult, sensorsResult, regionsResult, invitesResult] = await Promise.all([
      fetchAlerts(nextToken),
      fetchSensors(nextToken),
      fetchRegions(nextToken),
      profileResult.role === 'admin' && profileResult.org_id ? fetchInvites(nextToken, profileResult.org_id) : Promise.resolve([]),
    ])
    setProfile(profileResult)
    setAlerts(alertsResult)
    setSensors(sensorsResult)
    setRegions(regionsResult)
    setInvites(invitesResult)
  }

  useEffect(() => {
    refreshData().catch((err) => setError(err.message))
  }, [])

  function persistToken(nextToken) {
    setToken(nextToken)
    window.localStorage.setItem('canopy_token', nextToken)
  }

  async function handleAuth(mode, payload) {
    setError('')
    setMessage('')
    const result = mode === 'signup' ? await signup(payload) : await login(payload)
    persistToken(result.access_token)
    setMessage(`${mode === 'signup' ? 'Signed up' : 'Logged in'} successfully.`)
    await refreshData(result.access_token)
  }

  function handleLogout() {
    setToken('')
    window.localStorage.removeItem('canopy_token')
    setAlerts([])
    setSensors([])
    setRegions([])
    setProfile(null)
    setInvites([])
    setMessage('Logged out. Please log in to view organization data.')
  }

  async function handleCreateInvite(payload) {
    setError('')
    const invite = await createInvite(token, profile.org_id, payload)
    setMessage(`Created invite for ${invite.email}. Token: ${invite.token}`)
    await refreshData()
  }

  async function handleRevokeInvite(inviteId) {
    setError('')
    await revokeInvite(token, profile.org_id, inviteId)
    setMessage(`Revoked invite ${inviteId}.`)
    await refreshData()
  }

  async function handleCreateRegion(payload) {
    setError('')
    const region = await createRegion(token, payload)
    setMessage(`Created region ${region.name}.`)
    await refreshData()
  }

  async function handleCreateSensor(payload) {
    setError('')
    const sensor = await createSensor(token, payload)
    setMessage(`Created sensor ${sensor.name}.`)
    await refreshData()
  }

  async function handleUploadClip(payload) {
    setError('')
    const result = await uploadClip(token, payload)
    setMessage(`Uploaded clip ${result.clip_id}; generated alert ${result.generated_alert?.id}.`)
    await refreshData()
  }

  async function handleUpdateAlertStatus(alertId, status) {
    setError('')
    await updateAlertStatus(token, alertId, { status })
    setMessage(`Updated alert ${alertId} to ${status}.`)
    await refreshData()
  }

  async function handleExportAlerts() {
    const blob = await downloadAlertsCsv(token)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'canopy-alerts.csv'
    link.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <Dashboard
      health={health}
      alerts={alerts}
      sensors={sensors}
      regions={regions}
      invites={invites}
      profile={profile}
      isAuthenticated={isAuthenticated}
      message={message}
      error={error}
      token={token}
      onAuth={handleAuth}
      onLogout={handleLogout}
      onExportAlerts={handleExportAlerts}
      onCreateInvite={handleCreateInvite}
      onRevokeInvite={handleRevokeInvite}
      onCreateRegion={handleCreateRegion}
      onCreateSensor={handleCreateSensor}
      onUploadClip={handleUploadClip}
      onUpdateAlertStatus={handleUpdateAlertStatus}
    />
  )
}
