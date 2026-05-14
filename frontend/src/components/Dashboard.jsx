import { useState } from 'react'
import MapPanel from './MapPanel.jsx'

const ALERT_STATUSES = ['acknowledged', 'investigating', 'resolved', 'dismissed']
const CHANGE_TYPES = ['ndvi_drop', 'canopy_loss', 'vegetation_stress', 'burn_scar', 'unknown']

function regionName(regions, regionId) {
  return regions.find((region) => region.id === regionId)?.name || (regionId ? `region ${regionId}` : 'No region')
}

function formatPercent(value) {
  return value === undefined || value === null ? 'n/a' : `${Math.round(Number(value) * 100)}%`
}

export default function Dashboard({
  health,
  alerts,
  sensors,
  regions,
  satelliteChanges,
  fusionResult,
  ndviBatches,
  ndviUploadResult,
  invites,
  profile,
  isAuthenticated,
  message,
  error,
  onAuth,
  onLogout,
  onExportAlerts,
  onCreateInvite,
  onRevokeInvite,
  onCreateRegion,
  onCreateSensor,
  onUploadClip,
  onCreateSatelliteChange,
  onRunFusion,
  onUploadNdviCsv,
  onUpdateAlertStatus,
}) {
  const [authMode, setAuthMode] = useState('login')
  const [authForm, setAuthForm] = useState({ name: '', email: '', password: '', organization_name: '', invite_token: '' })
  const [inviteForm, setInviteForm] = useState({ email: '', role: 'member' })
  const [regionForm, setRegionForm] = useState({ name: '', description: '', boundary: '' })
  const [sensorForm, setSensorForm] = useState({ name: '', device_type: 'forest-listening-unit', region_id: '', lat: '', lon: '' })
  const [clipForm, setClipForm] = useState({ sensorId: '', file: null })
  const [ndviForm, setNdviForm] = useState({ regionId: '', lossThreshold: '-0.15', defaultConfidence: '0.75', file: null })
  const [satelliteForm, setSatelliteForm] = useState({
    region_id: '',
    source: 'manual',
    change_type: 'ndvi_drop',
    severity_score: '0.7',
    confidence: '0.8',
    latitude: '',
    longitude: '',
    description: '',
  })
  const [localError, setLocalError] = useState('')
  const openAlerts = alerts.filter((alert) => alert.status === 'open')
  const fusedAlerts = alerts.filter((alert) => alert.type === 'fusion' || alert.type === 'fused_logging_risk')
  const isAdmin = profile?.role === 'admin'

  async function submitWithLocalError(action) {
    setLocalError('')
    try {
      await action()
    } catch (err) {
      setLocalError(err.message)
    }
  }

  function handleAuthSubmit(event) {
    event.preventDefault()
    submitWithLocalError(() => onAuth(authMode, authForm))
  }

  function handleInviteSubmit(event) {
    event.preventDefault()
    submitWithLocalError(() => onCreateInvite(inviteForm))
  }

  function handleRegionSubmit(event) {
    event.preventDefault()
    submitWithLocalError(() =>
      onCreateRegion({
        name: regionForm.name,
        description: regionForm.description || null,
        boundary: regionForm.boundary || null,
      }),
    )
  }

  function handleSensorSubmit(event) {
    event.preventDefault()
    submitWithLocalError(() =>
      onCreateSensor({
        name: sensorForm.name,
        device_type: sensorForm.device_type,
        region_id: sensorForm.region_id ? Number(sensorForm.region_id) : null,
        location: { lat: Number(sensorForm.lat), lon: Number(sensorForm.lon) },
      }),
    )
  }

  function handleClipSubmit(event) {
    event.preventDefault()
    submitWithLocalError(() => onUploadClip({ sensorId: clipForm.sensorId, file: clipForm.file }))
  }

  function handleSatelliteSubmit(event) {
    event.preventDefault()
    submitWithLocalError(() =>
      onCreateSatelliteChange({
        region_id: satelliteForm.region_id ? Number(satelliteForm.region_id) : null,
        source: satelliteForm.source || 'manual',
        change_type: satelliteForm.change_type,
        severity_score: Number(satelliteForm.severity_score),
        confidence: Number(satelliteForm.confidence),
        latitude: satelliteForm.latitude === '' ? null : Number(satelliteForm.latitude),
        longitude: satelliteForm.longitude === '' ? null : Number(satelliteForm.longitude),
        description: satelliteForm.description || null,
      }),
    )
  }

  function handleNdviSubmit(event) {
    event.preventDefault()
    submitWithLocalError(() =>
      onUploadNdviCsv({
        regionId: ndviForm.regionId,
        lossThreshold: ndviForm.lossThreshold,
        defaultConfidence: ndviForm.defaultConfidence,
        file: ndviForm.file,
      }),
    )
  }

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <p className="eyebrow">Open-source forest monitoring</p>
        <h1>Canopy conservation dashboard</h1>
        <p>
          Fuse field acoustic events with satellite vegetation change signals to help conservation teams triage
          forest threats in near real time.
        </p>
        {profile?.organization && (
          <p className="org-banner">
            Organization: <strong>{profile.organization.name}</strong> · Role: <strong>{profile.role}</strong>
          </p>
        )}
        {!isAuthenticated && <p className="status-message">Log in or sign up to load organization-scoped sensors, regions, and alerts.</p>}
        <div className="metrics-grid" aria-label="Canopy metrics">
          <div>
            <strong>{alerts.length}</strong>
            <span>Total alerts</span>
          </div>
          <div>
            <strong>{openAlerts.length}</strong>
            <span>Open alerts</span>
          </div>
          <div>
            <strong>{sensors.length}</strong>
            <span>Registered sensors</span>
          </div>
          <div>
            <strong>{satelliteChanges.length}</strong>
            <span>Satellite changes</span>
          </div>
          <div>
            <strong>{fusedAlerts.length}</strong>
            <span>Fused alerts</span>
          </div>
          <div>
            <strong>{health.status}</strong>
            <span>API status</span>
          </div>
        </div>
        {(message || error || localError) && <p className="status-message">{localError || error || message}</p>}
      </section>

      <section className="workflow-grid">
        <form className="control-card" onSubmit={handleAuthSubmit}>
          <h2>{isAuthenticated ? 'Authenticated' : 'Sign up or log in'}</h2>
          {!isAuthenticated ? (
            <>
              <label>
                Mode
                <select value={authMode} onChange={(event) => setAuthMode(event.target.value)}>
                  <option value="login">Login</option>
                  <option value="signup">Signup</option>
                </select>
              </label>
              {authMode === 'signup' && (
                <>
                  <label>
                    Name
                    <input value={authForm.name} onChange={(event) => setAuthForm({ ...authForm, name: event.target.value })} required />
                  </label>
                  <label>
                    Invite token
                    <input
                      value={authForm.invite_token}
                      onChange={(event) => setAuthForm({ ...authForm, invite_token: event.target.value, organization_name: event.target.value ? '' : authForm.organization_name })}
                      placeholder="Paste invite token to join an existing org"
                    />
                  </label>
                  {authForm.invite_token ? (
                    <p>Joining invited organization</p>
                  ) : (
                    <label>
                      Organization name
                      <input
                        value={authForm.organization_name}
                        onChange={(event) => setAuthForm({ ...authForm, organization_name: event.target.value })}
                        placeholder="Demo Conservation Team"
                        required
                      />
                    </label>
                  )}
                </>
              )}
              <label>
                Email
                <input
                  type="email"
                  value={authForm.email}
                  onChange={(event) => setAuthForm({ ...authForm, email: event.target.value })}
                  required
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={authForm.password}
                  onChange={(event) => setAuthForm({ ...authForm, password: event.target.value })}
                  required
                />
              </label>
              <button type="submit">{authMode === 'signup' ? 'Sign up' : 'Log in'}</button>
            </>
          ) : (
            <button type="button" onClick={onLogout}>
              Log out
            </button>
          )}
        </form>

        <form className="control-card" onSubmit={handleInviteSubmit}>
          <h2>Invite member</h2>
          <label>
            Email
            <input type="email" value={inviteForm.email} onChange={(event) => setInviteForm({ ...inviteForm, email: event.target.value })} required />
          </label>
          <label>
            Role
            <select value={inviteForm.role} onChange={(event) => setInviteForm({ ...inviteForm, role: event.target.value })}>
              <option value="member">member</option>
            </select>
          </label>
          <button type="submit" disabled={!isAdmin}>Create invite</button>
          {isAdmin && invites?.length > 0 && (
            <div className="invite-list">
              {invites.map((invite) => (
                <article key={invite.id}>
                  <strong>{invite.email}</strong> · {invite.role} · {invite.status}
                  {invite.token && <code>{invite.token}</code>}
                  {invite.status === 'pending' && (
                    <button type="button" onClick={() => submitWithLocalError(() => onRevokeInvite(invite.id))}>
                      Revoke
                    </button>
                  )}
                </article>
              ))}
            </div>
          )}
        </form>

        <form className="control-card" onSubmit={handleRegionSubmit}>
          <h2>Create region</h2>
          <label>
            Name
            <input value={regionForm.name} onChange={(event) => setRegionForm({ ...regionForm, name: event.target.value })} required />
          </label>
          <label>
            Description
            <input value={regionForm.description} onChange={(event) => setRegionForm({ ...regionForm, description: event.target.value })} />
          </label>
          <label>
            Boundary GeoJSON
            <textarea
              value={regionForm.boundary}
              onChange={(event) => setRegionForm({ ...regionForm, boundary: event.target.value })}
              placeholder='{"type":"Polygon","coordinates":[...]}'
            />
          </label>
          <button type="submit" disabled={!isAdmin}>Create region</button>
        </form>

        <form className="control-card" onSubmit={handleSensorSubmit}>
          <h2>Create sensor</h2>
          <label>
            Name
            <input value={sensorForm.name} onChange={(event) => setSensorForm({ ...sensorForm, name: event.target.value })} required />
          </label>
          <label>
            Region
            <select value={sensorForm.region_id} onChange={(event) => setSensorForm({ ...sensorForm, region_id: event.target.value })}>
              <option value="">No region</option>
              {regions.map((region) => (
                <option key={region.id} value={region.id}>
                  {region.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Latitude
            <input type="number" step="any" value={sensorForm.lat} onChange={(event) => setSensorForm({ ...sensorForm, lat: event.target.value })} required />
          </label>
          <label>
            Longitude
            <input type="number" step="any" value={sensorForm.lon} onChange={(event) => setSensorForm({ ...sensorForm, lon: event.target.value })} required />
          </label>
          <button type="submit" disabled={!isAdmin}>Create sensor</button>
        </form>

        <form className="control-card" onSubmit={handleClipSubmit}>
          <h2>Upload audio clip</h2>
          <label>
            Sensor
            <select value={clipForm.sensorId} onChange={(event) => setClipForm({ ...clipForm, sensorId: event.target.value })} required>
              <option value="">Select a sensor</option>
              {sensors.map((sensor) => (
                <option key={sensor.id} value={sensor.id}>
                  {sensor.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Audio file
            <input
              type="file"
              accept=".wav,.flac,.mp3,.ogg,.m4a,audio/*"
              onChange={(event) => setClipForm({ ...clipForm, file: event.target.files[0] })}
              required
            />
          </label>
          <button type="submit" disabled={!isAuthenticated || !sensors.length}>Upload clip</button>
        </form>




        <form className="control-card ndvi-card" onSubmit={handleNdviSubmit}>
          <h2>Upload NDVI CSV</h2>
          <p className="card-help">CSV/sample-based NDVI ingestion. Live Sentinel/Google Earth Engine integration is deferred.</p>
          <label>
            Region
            <select value={ndviForm.regionId} onChange={(event) => setNdviForm({ ...ndviForm, regionId: event.target.value })}>
              <option value="">No region</option>
              {regions.map((region) => (
                <option key={region.id} value={region.id}>
                  {region.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Loss threshold
            <input type="number" step="0.01" max="0" value={ndviForm.lossThreshold} onChange={(event) => setNdviForm({ ...ndviForm, lossThreshold: event.target.value })} />
          </label>
          <label>
            Default confidence
            <input type="number" min="0" max="1" step="0.01" value={ndviForm.defaultConfidence} onChange={(event) => setNdviForm({ ...ndviForm, defaultConfidence: event.target.value })} />
          </label>
          <label>
            NDVI CSV file
            <input type="file" accept=".csv,text/csv" onChange={(event) => setNdviForm({ ...ndviForm, file: event.target.files[0] })} required />
          </label>
          <button type="submit" disabled={!isAdmin || !ndviForm.file}>Upload NDVI CSV</button>
          {ndviUploadResult && (
            <p className="fusion-result">
              Batch {ndviUploadResult.batch_id}: {ndviUploadResult.row_count} row(s), {ndviUploadResult.created_change_count} satellite change(s), {ndviUploadResult.skipped_count} skipped.
            </p>
          )}
        </form>

        <form className="control-card satellite-card" onSubmit={handleSatelliteSubmit}>
          <h2>Manual satellite change</h2>
          <p className="card-help">Manual/stub workflow only. Real Sentinel/NDVI processing is deferred.</p>
          <label>
            Region
            <select value={satelliteForm.region_id} onChange={(event) => setSatelliteForm({ ...satelliteForm, region_id: event.target.value })}>
              <option value="">No region</option>
              {regions.map((region) => (
                <option key={region.id} value={region.id}>
                  {region.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Source
            <input value={satelliteForm.source} onChange={(event) => setSatelliteForm({ ...satelliteForm, source: event.target.value })} />
          </label>
          <label>
            Change type
            <select value={satelliteForm.change_type} onChange={(event) => setSatelliteForm({ ...satelliteForm, change_type: event.target.value })}>
              {CHANGE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </label>
          <label>
            Severity score
            <input type="number" min="0" max="1" step="0.01" value={satelliteForm.severity_score} onChange={(event) => setSatelliteForm({ ...satelliteForm, severity_score: event.target.value })} required />
          </label>
          <label>
            Confidence
            <input type="number" min="0" max="1" step="0.01" value={satelliteForm.confidence} onChange={(event) => setSatelliteForm({ ...satelliteForm, confidence: event.target.value })} required />
          </label>
          <label>
            Latitude
            <input type="number" step="any" value={satelliteForm.latitude} onChange={(event) => setSatelliteForm({ ...satelliteForm, latitude: event.target.value })} required />
          </label>
          <label>
            Longitude
            <input type="number" step="any" value={satelliteForm.longitude} onChange={(event) => setSatelliteForm({ ...satelliteForm, longitude: event.target.value })} required />
          </label>
          <label>
            Description
            <textarea value={satelliteForm.description} onChange={(event) => setSatelliteForm({ ...satelliteForm, description: event.target.value })} placeholder="Manual canopy-loss observation near a sensor" />
          </label>
          <button type="submit" disabled={!isAdmin}>Create satellite change</button>
        </form>

        <section className="control-card fusion-card" aria-label="Fusion controls">
          <h2>Fusion</h2>
          <p className="card-help">Runs the default 14-day / 500m rule against acoustic alerts and manual satellite changes.</p>
          <button type="button" disabled={!isAdmin} onClick={() => submitWithLocalError(onRunFusion)}>
            Run Fusion
          </button>
          {fusionResult && (
            <p className="fusion-result">
              Created {fusionResult.created_count} alert(s); matched {fusionResult.matched_count} pair(s).
              {fusionResult.matched_count === 0 && ' No acoustic/satellite matches were found.'}
            </p>
          )}
        </section>

        <button className="export-button" type="button" disabled={!isAdmin} onClick={() => submitWithLocalError(onExportAlerts)}>
          Export alerts CSV
        </button>
      </section>

      <section className="dashboard-grid">
        <MapPanel alerts={alerts} sensors={sensors} satelliteChanges={satelliteChanges} />
        <aside className="sidebar" aria-label="Recent alerts">
          <h2>Recent alerts</h2>
          {!alerts.length && <p>No alerts yet. Upload an audio clip to create the first placeholder alert.</p>}
          {alerts.map((alert) => (
            <article className={`alert-card ${alert.metadata?.fusion_score !== undefined ? 'fused-alert-card' : ''}`} key={alert.id}>
              <div>
                <span className={`pill ${alert.priority}`}>{alert.priority}</span>
                <span className="pill muted">{alert.type}</span>
                <span className="pill status">{alert.status}</span>
              </div>
              <h3>{alert.description}</h3>
              <p>
                {alert.location.lat.toFixed(4)}, {alert.location.lon.toFixed(4)} · sensor {alert.sensor_id ?? 'none'}
              </p>
              {alert.classifier_label && (
                <p>
                  Classifier: {alert.classifier_label} ({formatPercent(alert.classifier_confidence)}) ·{' '}
                  {alert.classifier_model_version}
                </p>
              )}
              {alert.metadata?.fusion_score !== undefined && (
                <p className="fusion-metadata">
                  Fusion score: {Number(alert.metadata.fusion_score).toFixed(4)} · acoustic alert {alert.metadata.acoustic_alert_id} · satellite change{' '}
                  {alert.metadata.satellite_change_id}
                </p>
              )}
              <label>
                Update status
                <select
                  value=""
                  disabled={!isAdmin}
                  onChange={(event) => {
                    if (event.target.value) submitWithLocalError(() => onUpdateAlertStatus(alert.id, event.target.value))
                  }}
                >
                  <option value="">Choose status</option>
                  {ALERT_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {status}
                    </option>
                  ))}
                </select>
              </label>
            </article>
          ))}
        </aside>


        <aside className="sidebar ndvi-list" aria-label="NDVI ingestion batches">
          <h2>NDVI ingestion batches</h2>
          {!ndviBatches.length && <p>No NDVI CSV batches yet. Admins can upload sample NDVI comparison data.</p>}
          {ndviBatches.map((batch) => (
            <article className="satellite-change-card" key={batch.id}>
              <div>
                <span className="pill satellite">batch #{batch.id}</span>
                <span className="pill muted">{batch.status}</span>
              </div>
              <p>
                Region: {regionName(regions, batch.region_id)} · file {batch.filename || 'n/a'} · rows {batch.row_count} · changes {batch.created_change_count}
              </p>
              <p>
                Created {new Date(batch.created_at).toLocaleString()} · processed {batch.processed_at ? new Date(batch.processed_at).toLocaleString() : 'pending'}
              </p>
              {batch.error_message && <p className="fusion-metadata">Error: {batch.error_message}</p>}
            </article>
          ))}
        </aside>

        <aside className="sidebar satellite-list" aria-label="Satellite changes">
          <h2>Satellite changes</h2>
          {!satelliteChanges.length && <p>No satellite-change events yet. Admins can create a manual event near a sensor.</p>}
          {satelliteChanges.map((change) => (
            <article className="satellite-change-card" key={change.id}>
              <div>
                <span className="pill satellite">#{change.id}</span>
                <span className="pill muted">{change.change_type}</span>
              </div>
              <p>
                Region: {regionName(regions, change.region_id)} · severity {formatPercent(change.severity_score)} · confidence {formatPercent(change.confidence)}
              </p>
              <p>
                {change.latitude !== null && change.longitude !== null
                  ? `${Number(change.latitude).toFixed(4)}, ${Number(change.longitude).toFixed(4)}`
                  : 'No point location'} · {new Date(change.created_at).toLocaleString()}
              </p>
              {change.description && <p>{change.description}</p>}
            </article>
          ))}
        </aside>
      </section>
    </main>
  )
}
