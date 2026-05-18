import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

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
import DataIngestion from './components/DataIngestion.jsx'
import Layout from './components/Layout.jsx'
import LoginPage from './components/LoginPage.jsx'
import Overview from './components/Overview.jsx'
import Settings from './components/Settings.jsx'

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
  const [isSimulating, setIsSimulating] = useState(false)

  const isAuthenticated = Boolean(token)
  const isAdmin = profile?.role === 'admin'

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
    // Startup load only; later authenticated mutations call refreshData directly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!isSimulating) return undefined

    const interval = setInterval(() => {
      const isAcoustic = Math.random() > 0.4
      const priorities = ['low', 'medium', 'high', 'critical']
      const randomPriority = priorities[Math.floor(Math.random() * priorities.length)]
      const newAlert = {
        id: Date.now(),
        type: isAcoustic ? 'audio' : 'fusion',
        status: 'open',
        priority: randomPriority,
        description: isAcoustic
          ? `Audio classifier detected chainsaw with ${Math.floor(Math.random() * 20 + 80)}% confidence.`
          : 'Fusion alert: acoustic evidence matched satellite change.',
        location: { lat: 21.0 + (Math.random() * 10 - 5), lon: 78.0 + (Math.random() * 10 - 5) },
        created_at: new Date().toISOString(),
        metadata: isAcoustic ? undefined : { fusion_score: Math.random() * 0.5 + 0.5 },
      }
      setAlerts((previousAlerts) => [newAlert, ...previousAlerts])
    }, 2500)

    return () => clearInterval(interval)
  }, [isSimulating])

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
    setIsSimulating(false)
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

  if (!isAuthenticated) {
    return <LoginPage onAuth={handleAuth} error={error} message={message} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout profile={profile} onLogout={handleLogout} health={health} message={message} error={error} />}>
          <Route
            index
            element={
              <Overview
                alerts={alerts}
                sensors={sensors}
                satelliteChanges={satelliteChanges}
                onUpdateAlertStatus={handleUpdateAlertStatus}
                isAdmin={isAdmin}
                isSimulating={isSimulating}
                setIsSimulating={setIsSimulating}
              />
            }
          />
          <Route
            path="ingestion"
            element={
              <DataIngestion
                sensors={sensors}
                regions={regions}
                ndviBatches={ndviBatches}
                satelliteChanges={satelliteChanges}
                fusionResult={fusionResult}
                ndviUploadResult={ndviUploadResult}
                isAuthenticated={isAuthenticated}
                isAdmin={isAdmin}
                onUploadClip={handleUploadClip}
                onUploadNdviCsv={handleUploadNdviCsv}
                onCreateSatelliteChange={handleCreateSatelliteChange}
                onRunFusion={handleRunFusion}
                onExportAlerts={handleExportAlerts}
              />
            }
          />
          <Route
            path="settings"
            element={
              <Settings
                regions={regions}
                invites={invites}
                isAdmin={isAdmin}
                onCreateInvite={handleCreateInvite}
                onRevokeInvite={handleRevokeInvite}
                onCreateRegion={handleCreateRegion}
                onCreateSensor={handleCreateSensor}
              />
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
