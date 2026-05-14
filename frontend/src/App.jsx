import { useEffect, useState } from 'react'
import Dashboard from './components/Dashboard.jsx'
import {
  createInvite,
  createRegion,
  createSatelliteChange,
  createSensor,
  downloadAlertsCsv,
  fetchAlerts,
  fetchHealth,
  fetchInvites,
  fetchMe,
  fetchNdviBatches,
  fetchRegions,
  fetchSatelliteChanges,
  fetchSensors,
  login,
  revokeInvite,
  runFusion,
  signup,
  updateAlertStatus,
  uploadClip,
  uploadNdviCsv,
} from './api.js'

export default function App() {
  const [health, setHealth] = useState({ status: 'loading' })
  const [alerts, setAlerts] = useState([])
  const [sensors, setSensors] = useState([])
  const [regions, setRegions] = useState([])
  const [satelliteChanges, setSatelliteChanges] = useState([])
  const [fusionResult, setFusionResult] = useState(null)
  const [ndviBatches, setNdviBatches] = useState([])
  const [ndviUploadResult, setNdviUploadResult] = useState(null)
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
      setSatelliteChanges([])
      setNdviBatches([])
      return
    }
    const profileResult = await fetchMe(nextToken)
    const [alertsResult, sensorsResult, regionsResult, satelliteChangesResult, ndviBatchesResult, invitesResult] = await Promise.all([
      fetchAlerts(nextToken),
      fetchSensors(nextToken),
      fetchRegions(nextToken),
      fetchSatelliteChanges(nextToken),
      fetchNdviBatches(nextToken),
      profileResult.role === 'admin' && profileResult.org_id ? fetchInvites(nextToken, profileResult.org_id) : Promise.resolve([]),
    ])
    setProfile(profileResult)
    setAlerts(alertsResult)
    setSensors(sensorsResult)
    setRegions(regionsResult)
    setSatelliteChanges(satelliteChangesResult)
    setNdviBatches(ndviBatchesResult)
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
    setSatelliteChanges([])
    setNdviBatches([])
    setNdviUploadResult(null)
    setProfile(null)
    setInvites([])
    setFusionResult(null)
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

  async function handleCreateSatelliteChange(payload) {
    setError('')
    const change = await createSatelliteChange(token, payload)
    setMessage(`Created satellite change ${change.id}.`)
    await refreshData()
  }

  async function handleUploadNdviCsv(payload) {
    setError('')
    const result = await uploadNdviCsv(token, payload)
    setNdviUploadResult(result)
    setMessage(`Processed NDVI batch ${result.batch_id}: ${result.created_change_count} satellite change(s) created, ${result.skipped_count} row(s) skipped.`)
    await refreshData()
  }

  async function handleRunFusion() {
    setError('')
    const result = await runFusion(token, {
      time_window_days: 14,
      distance_meters: 500,
      min_acoustic_confidence: 0.65,
      min_satellite_severity: 0.3,
    })
    setFusionResult(result)
    setMessage(
      result.matched_count === 0
        ? 'Fusion completed: no acoustic/satellite matches found.'
        : `Fusion completed: ${result.created_count} alert(s) created from ${result.matched_count} match(es).`,
    )
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
      satelliteChanges={satelliteChanges}
      fusionResult={fusionResult}
      ndviBatches={ndviBatches}
      ndviUploadResult={ndviUploadResult}
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
      onCreateSatelliteChange={handleCreateSatelliteChange}
      onRunFusion={handleRunFusion}
      onUploadNdviCsv={handleUploadNdviCsv}
      onUpdateAlertStatus={handleUpdateAlertStatus}
    />
  )
}
