/* global Blob */
import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import {
  addClipLabel,
  createInvite,
  createRegion,
  createSatelliteChange,
  createSensor,
  downloadAlertsCsv,
  downloadLabelsCsv,
  fetchAlerts,
  fetchClipLabels,
  fetchClips,
  fetchFusionSchedule,
  fetchHealth,
  fetchInvites,
  fetchMe,
  fetchNdviBatches,
  fetchNotificationSettings,
  fetchRegions,
  fetchSatelliteChanges,
  fetchSensors,
  ingestSentinel,
  revokeInvite,
  runFusion,
  updateAlertStatus,
  updateNotificationSettings,
  uploadClip,
  uploadNdviCsv,
} from './api.js'
import ClipsReview from './components/ClipsReview.jsx'
import DataIngestion from './components/DataIngestion.jsx'
import Layout from './components/Layout.jsx'
import Overview from './components/Overview.jsx'
import Settings from './components/Settings.jsx'
import { freshDemoState } from './demoData.js'

function nextId(items) {
  return Math.max(0, ...items.map((item) => Number(item.id) || 0)) + 1
}

function nowIso() {
  return new Date().toISOString()
}

function labelFromFile(file) {
  const name = file?.name?.toLowerCase() || ''
  if (name.includes('gun')) return 'gunshot'
  if (name.includes('vehicle') || name.includes('truck') || name.includes('motor')) return 'vehicle'
  if (name.includes('fire')) return 'fire_crackle'
  if (name.includes('chain') || name.includes('saw')) return 'chainsaw'
  return 'chainsaw'
}

function csvValue(value) {
  const text = value === undefined || value === null ? '' : String(value)
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

function alertsToCsv(alerts) {
  const columns = [
    'id',
    'type',
    'status',
    'priority',
    'description',
    'latitude',
    'longitude',
    'sensor_id',
    'created_at',
    'classifier_label',
    'classifier_confidence',
    'fusion_score',
    'acoustic_alert_id',
    'satellite_change_id',
  ]
  const rows = alerts.map((alert) => ({
    id: alert.id,
    type: alert.type,
    status: alert.status,
    priority: alert.priority,
    description: alert.description,
    latitude: alert.location?.lat,
    longitude: alert.location?.lon,
    sensor_id: alert.sensor_id,
    created_at: alert.created_at,
    classifier_label: alert.classifier_label,
    classifier_confidence: alert.classifier_confidence,
    fusion_score: alert.metadata?.fusion_score,
    acoustic_alert_id: alert.metadata?.acoustic_alert_id,
    satellite_change_id: alert.metadata?.satellite_change_id,
  }))
  return [columns.join(','), ...rows.map((row) => columns.map((column) => csvValue(row[column])).join(','))].join('\n')
}

export default function DashboardApp() {
  const initialDemo = freshDemoState()
  const [health, setHealth] = useState({ status: 'demo' })
  const [alerts, setAlerts] = useState(initialDemo.alerts)
  const [sensors, setSensors] = useState(initialDemo.sensors)
  const [regions, setRegions] = useState(initialDemo.regions)
  const [satelliteChanges, setSatelliteChanges] = useState(initialDemo.satelliteChanges)
  const [fusionResult, setFusionResult] = useState(null)
  const [ndviBatches, setNdviBatches] = useState(initialDemo.ndviBatches)
  const [ndviUploadResult, setNdviUploadResult] = useState(null)
  const [profile, setProfile] = useState(initialDemo.profile)
  const [invites, setInvites] = useState(initialDemo.invites)
  const [token, setToken] = useState(() => window.localStorage.getItem('canopy_token') || '')
  const [clips, setClips] = useState([])
  const [webhooks, setWebhooks] = useState([])
  const [fusionSchedule, setFusionSchedule] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [isSimulating, setIsSimulating] = useState(false)

  const hasApiSession = Boolean(token)
  const isAuthenticated = true
  const isAdmin = profile?.role === 'admin'

  function resetDemoState() {
    const demo = freshDemoState()
    setAlerts(demo.alerts)
    setSensors(demo.sensors)
    setRegions(demo.regions)
    setSatelliteChanges(demo.satelliteChanges)
    setNdviBatches(demo.ndviBatches)
    setProfile(demo.profile)
    setInvites(demo.invites)
    setClips([])
    setWebhooks([])
    setFusionSchedule(null)
    setFusionResult(null)
    setNdviUploadResult(null)
    setHealth({ status: 'demo' })
  }

  async function refreshData(nextToken = token) {
    if (!nextToken) {
      try {
        setHealth(await fetchHealth())
      } catch {
        setHealth({ status: 'demo' })
      }
      return
    }

    try {
      const healthResult = await fetchHealth()
      setHealth(healthResult)
      const profileResult = await fetchMe(nextToken)
      const [alertsResult, sensorsResult, regionsResult, satelliteChangesResult, ndviBatchesResult, invitesResult, notifResult] =
        await Promise.all([
          fetchAlerts(nextToken),
          fetchSensors(nextToken),
          fetchRegions(nextToken),
          fetchSatelliteChanges(nextToken),
          fetchNdviBatches(nextToken),
          profileResult.role === 'admin' && profileResult.org_id
            ? fetchInvites(nextToken, profileResult.org_id)
            : Promise.resolve([]),
          profileResult.role === 'admin' && profileResult.org_id
            ? fetchNotificationSettings(nextToken, profileResult.org_id).catch(() => ({ webhooks: [] }))
            : Promise.resolve({ webhooks: [] }),
        ])

      setProfile(profileResult)
      setAlerts(alertsResult.items ?? alertsResult)
      setSensors(sensorsResult)
      setRegions(regionsResult)
      setSatelliteChanges(satelliteChangesResult)
      setNdviBatches(ndviBatchesResult)
      setInvites(invitesResult)
      setWebhooks(notifResult.webhooks ?? [])
      const clipsResult = await fetchClips(nextToken).catch(() => [])
      setClips(clipsResult)
      const scheduleResult = await fetchFusionSchedule(nextToken).catch(() => null)
      setFusionSchedule(scheduleResult)
    } catch {
      window.localStorage.removeItem('canopy_token')
      setToken('')
      resetDemoState()
      setMessage('')
    }
  }

  useEffect(() => {
    refreshData().catch((err) => setError(err.message))
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

  function handleLogout() {
    setToken('')
    window.localStorage.removeItem('canopy_token')
    resetDemoState()
    setIsSimulating(false)
    setMessage('Public demo dashboard reset.')
  }

  async function handleCreateInvite(payload) {
    setError('')
    if (!hasApiSession) {
      const invite = {
        id: nextId(invites),
        email: payload.email,
        role: payload.role || 'member',
        status: 'pending',
        token: `demo-invite-${nextId(invites)}`,
      }
      setInvites((current) => [invite, ...current])
      setMessage(`Created demo invite for ${invite.email}. Token: ${invite.token}`)
      return
    }
    const invite = await createInvite(token, profile.org_id, payload)
    setMessage(`Created invite for ${invite.email}. Token: ${invite.token}`)
    await refreshData()
  }

  async function handleRevokeInvite(inviteId) {
    setError('')
    if (!hasApiSession) {
      setInvites((current) => current.map((invite) => (invite.id === inviteId ? { ...invite, status: 'revoked' } : invite)))
      setMessage(`Revoked demo invite ${inviteId}.`)
      return
    }
    await revokeInvite(token, profile.org_id, inviteId)
    setMessage(`Revoked invite ${inviteId}.`)
    await refreshData()
  }

  async function handleCreateRegion(payload) {
    setError('')
    if (!hasApiSession) {
      const region = {
        id: nextId(regions),
        org_id: profile.org_id,
        name: payload.name,
        description: payload.description || null,
        boundary: payload.boundary || null,
        created_at: nowIso(),
        updated_at: nowIso(),
      }
      setRegions((current) => [region, ...current])
      setMessage(`Created demo region ${region.name}.`)
      return
    }
    const region = await createRegion(token, payload)
    setMessage(`Created region ${region.name}.`)
    await refreshData()
  }

  async function handleCreateSensor(payload) {
    setError('')
    if (!hasApiSession) {
      const sensor = {
        id: nextId(sensors),
        org_id: profile.org_id,
        region_id: payload.region_id || null,
        name: payload.name,
        device_type: payload.device_type,
        location: payload.location,
        status: 'online',
        last_heard_at: nowIso(),
      }
      setSensors((current) => [sensor, ...current])
      setMessage(`Created demo sensor ${sensor.name}.`)
      return
    }
    const sensor = await createSensor(token, payload)
    setMessage(`Created sensor ${sensor.name}.`)
    await refreshData()
  }

  async function handleUploadClip(payload) {
    setError('')
    if (!hasApiSession) {
      const sensor = sensors.find((item) => String(item.id) === String(payload.sensorId)) || sensors[0]
      if (!sensor) throw new Error('Create a sensor before uploading a clip.')
      const label = labelFromFile(payload.file)
      const alert = {
        id: nextId(alerts),
        org_id: profile.org_id,
        type: 'audio',
        status: 'open',
        priority: label === 'background_unknown' ? 'low' : 'high',
        description: `Audio classifier detected '${label}' with 82% confidence.`,
        location: sensor.location,
        sensor_id: sensor.id,
        region_id: sensor.region_id,
        classifier_label: label,
        classifier_confidence: 0.82,
        classifier_model_version: 'placeholder-v0',
        metadata: {},
        created_at: nowIso(),
        updated_at: nowIso(),
      }
      setAlerts((current) => [alert, ...current])
      setMessage(`Uploaded demo clip; generated alert ${alert.id}.`)
      return
    }
    const result = await uploadClip(token, payload)
    setMessage(`Uploaded clip ${result.clip_id}; generated alert ${result.generated_alert?.id}.`)
    await refreshData()
  }

  async function handleCreateSatelliteChange(payload) {
    setError('')
    if (!hasApiSession) {
      const change = {
        id: nextId(satelliteChanges),
        org_id: profile.org_id,
        region_id: payload.region_id || null,
        source: payload.source || 'manual',
        change_type: payload.change_type,
        severity_score: payload.severity_score,
        confidence: payload.confidence,
        latitude: payload.latitude,
        longitude: payload.longitude,
        description: payload.description || 'Manual demo satellite change',
        metadata: {},
        created_at: nowIso(),
        updated_at: nowIso(),
      }
      setSatelliteChanges((current) => [change, ...current])
      setMessage(`Created demo satellite change ${change.id}.`)
      return
    }
    const change = await createSatelliteChange(token, payload)
    setMessage(`Created satellite change ${change.id}.`)
    await refreshData()
  }

  async function handleUploadNdviCsv(payload) {
    setError('')
    if (!hasApiSession) {
      const regionId = payload.regionId ? Number(payload.regionId) : regions[0]?.id || null
      const sensor = sensors[0]
      const firstChangeId = nextId(satelliteChanges)
      const newChanges = [0, 1, 2].map((offset) => ({
        id: firstChangeId + offset,
        org_id: profile.org_id,
        region_id: regionId,
        source: 'csv_ndvi',
        change_type: 'ndvi_drop',
        severity_score: 0.48 + offset * 0.06,
        confidence: 0.86,
        latitude: (sensor?.location?.lat || 20.5937) + offset * 0.0004,
        longitude: (sensor?.location?.lon || 78.9629) - offset * 0.0004,
        description: `Demo NDVI drop row ${offset + 1}`,
        metadata: { baseline_ndvi: 0.72, recent_ndvi: 0.48 - offset * 0.03, ndvi_delta: -0.24 - offset * 0.03 },
        created_at: nowIso(),
        updated_at: nowIso(),
      }))
      const result = {
        batch_id: nextId(ndviBatches),
        status: 'processed',
        row_count: 6,
        created_change_count: newChanges.length,
        skipped_count: 3,
        created_satellite_change_ids: newChanges.map((change) => change.id),
      }
      setSatelliteChanges((current) => [...newChanges, ...current])
      setNdviBatches((current) => [
        {
          id: result.batch_id,
          org_id: profile.org_id,
          region_id: regionId,
          source_type: 'csv',
          filename: payload.file?.name || 'demo-ndvi.csv',
          status: 'processed',
          row_count: result.row_count,
          created_change_count: result.created_change_count,
          created_at: nowIso(),
        },
        ...current,
      ])
      setNdviUploadResult(result)
      setMessage(`Processed demo NDVI batch ${result.batch_id}: ${result.created_change_count} satellite change(s) created.`)
      return
    }
    const result = await uploadNdviCsv(token, payload)
    setNdviUploadResult(result)
    setMessage(
      `Processed NDVI batch ${result.batch_id}: ${result.created_change_count} satellite change(s) created, ${result.skipped_count} row(s) skipped.`,
    )
    await refreshData()
  }

  async function handleRunFusion(payload = {}) {
    setError('')
    if (!hasApiSession) {
      const acousticAlert = alerts.find((alert) => alert.type === 'audio')
      const satelliteChange = satelliteChanges[0]
      if (!acousticAlert || !satelliteChange) {
        setFusionResult({ created_count: 0, matched_count: 0, alerts: [] })
        setMessage('Fusion completed: no acoustic/satellite matches found.')
        return
      }
      const fusionAlert = {
        ...acousticAlert,
        id: nextId(alerts),
        type: 'fusion',
        status: 'open',
        priority: 'medium',
        description: `Fusion alert: acoustic evidence '${acousticAlert.classifier_label || 'audio'}' matched satellite change '${satelliteChange.change_type}' (temporal decay 0.85, spatial decay 0.92).`,
        metadata: {
          acoustic_alert_id: acousticAlert.id,
          satellite_change_id: satelliteChange.id,
          acoustic_confidence: acousticAlert.classifier_confidence || 0,
          acoustic_confidence_threshold: 0.65,
          acoustic_suppressed: false,
          acoustic_weight: 0.45,
          satellite_severity_score: satelliteChange.severity_score,
          satellite_confidence: satelliteChange.confidence,
          distance_meters: 15.71,
          fusion_score: 0.637,
          fusion_scoring_mode: 'acoustic_satellite',
          fusion_rule_version: 'rule-fusion-v2',
          temporal_decay: 0.85,
          spatial_decay: 0.92,
          time_decay_halflife_days: payload.time_decay_halflife_days || 7.0,
          spatial_sigma_meters: payload.spatial_sigma_meters || 200.0,
          corroborating_change_count: 1,
          source_quality_multiplier: 1.10,
        },
        created_at: nowIso(),
        updated_at: nowIso(),
      }
      setAlerts((current) => [fusionAlert, ...current])
      setFusionResult({ created_count: 1, matched_count: 1, alerts: [fusionAlert] })
      setMessage('Fusion completed (Demo Mode): 1 alert created from 1 match.')
      return
    }
    const result = await runFusion(token, {
      time_window_days: 14,
      distance_meters: 500,
      min_acoustic_confidence: 0.65,
      min_satellite_severity: 0.3,
      ...payload,
    })
    setFusionResult(result)
    setMessage(
      result.matched_count === 0
        ? 'Fusion completed: no acoustic/satellite matches found.'
        : `Fusion completed: ${result.created_count} alert(s) created from ${result.matched_count} match(es).`,
    )
    await refreshData()
  }

  async function handleIngestSentinel(payload) {
    setError('')
    if (!hasApiSession) {
      const firstChangeId = nextId(satelliteChanges)
      const mockChange = {
        id: firstChangeId,
        org_id: profile.org_id,
        region_id: payload.region_id || null,
        source: 'sentinel_2',
        change_type: 'canopy_loss',
        severity_score: 0.68,
        confidence: 0.85,
        latitude: (payload.bbox[1] + payload.bbox[3]) / 2,
        longitude: (payload.bbox[0] + payload.bbox[2]) / 2,
        description: 'Sentinel-2 STAC Ingestion Mock (Demo Mode)',
        metadata: {
          bbox: payload.bbox,
          max_cloud_cover: payload.max_cloud_cover,
          loss_threshold: payload.loss_threshold,
          grid_resolution: payload.grid_resolution,
          baseline_scenes: 3,
          observation_scenes: 4,
        },
        created_at: nowIso(),
        updated_at: nowIso(),
        image_date: nowIso(),
      }
      setSatelliteChanges((current) => [mockChange, ...current])
      const res = {
        created_change_count: 1,
        created_satellite_change_ids: [mockChange.id],
        baseline_scene_count: 3,
        observation_scene_count: 4,
        grid_cells_evaluated: payload.grid_resolution * payload.grid_resolution,
        skipped_count: (payload.grid_resolution * payload.grid_resolution) - 1,
      }
      setMessage(`Sentinel Ingestion completed (Demo Mode): 1 change created.`)
      return res
    }
    const result = await ingestSentinel(token, payload)
    setMessage(`Sentinel Ingestion completed: ${result.created_change_count} change(s) created.`)
    await refreshData()
    return result
  }

  async function handleUpdateAlertStatus(alertId, status) {
    setError('')
    if (!hasApiSession) {
      setAlerts((current) => current.map((alert) => (alert.id === alertId ? { ...alert, status, updated_at: nowIso() } : alert)))
      setMessage(`Updated demo alert ${alertId} to ${status}.`)
      return
    }
    await updateAlertStatus(token, alertId, { status })
    setMessage(`Updated alert ${alertId} to ${status}.`)
    await refreshData()
  }

  async function handleFetchLabels(clipId) {
    if (!hasApiSession) return []
    return fetchClipLabels(token, clipId)
  }

  async function handleAddLabel(clipId, payload) {
    setError('')
    if (!hasApiSession) {
      const label = {
        id: Date.now(),
        clip_id: clipId,
        user_id: profile?.id || 1,
        label: payload.label,
        confidence: payload.confidence ?? null,
        labeled_at: nowIso(),
      }
      setClips((current) =>
        current.map((clip) =>
          clip.id === clipId ? { ...clip, _humanLabelCount: (clip._humanLabelCount || 0) + 1 } : clip
        )
      )
      return label
    }
    return addClipLabel(token, clipId, payload)
  }

  async function handleExportLabels() {
    if (!hasApiSession) return
    const blob = await downloadLabelsCsv(token)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'canopy-labels.csv'
    link.click()
    window.URL.revokeObjectURL(url)
  }

  async function handleSaveWebhooks(urls) {
    setError('')
    if (!hasApiSession) {
      setWebhooks(urls)
      setMessage(`Saved ${urls.length} demo webhook(s).`)
      return
    }
    const result = await updateNotificationSettings(token, profile.org_id, { webhooks: urls })
    setWebhooks(result.webhooks)
    setMessage(`Saved ${result.webhooks.length} webhook(s).`)
  }

  async function handleExportAlerts() {
    const blob = hasApiSession ? await downloadAlertsCsv(token) : new Blob([alertsToCsv(alerts)], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'canopy-alerts.csv'
    link.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <Routes>
      <Route path="/" element={<Layout profile={profile} onLogout={handleLogout} health={health} message={message} error={error} isDemoMode={!hasApiSession} />}>
        <Route
          index
          element={
            <Overview
              alerts={alerts}
              sensors={sensors}
              regions={regions}
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
              onIngestSentinel={handleIngestSentinel}
            />
          }
        />
        <Route
          path="clips"
          element={
            <ClipsReview
              clips={clips}
              sensors={sensors}
              onFetchLabels={handleFetchLabels}
              onAddLabel={handleAddLabel}
              onExportLabels={handleExportLabels}
              isAdmin={isAdmin}
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
              webhooks={webhooks}
              fusionSchedule={fusionSchedule}
              onCreateInvite={handleCreateInvite}
              onRevokeInvite={handleRevokeInvite}
              onCreateRegion={handleCreateRegion}
              onCreateSensor={handleCreateSensor}
              onSaveWebhooks={handleSaveWebhooks}
            />
          }
        />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Route>
    </Routes>
  )
}
