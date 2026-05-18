import MapPanel from './MapPanel.jsx'

export default function Overview({ 
  alerts, 
  sensors, 
  satelliteChanges, 
  onUpdateAlertStatus, 
  isAdmin,
  isSimulating,
  setIsSimulating
}) {
  const openAlerts = alerts.filter((a) => a.status === 'open')
  const fusedAlerts = alerts.filter((a) => a.type === 'fusion' || a.type === 'fused_logging_risk')

  function formatPercent(value) {
    return value === undefined || value === null ? 'n/a' : `${Math.round(Number(value) * 100)}%`
  }

  const ALERT_STATUSES = ['acknowledged', 'investigating', 'resolved', 'dismissed']

  return (
    <div className="page-content">
      <header className="page-header">
        <h2>Global Overview</h2>
        <div className="header-actions">
          <button 
            className="export-button" 
            onClick={() => setIsSimulating(!isSimulating)}
            style={{ 
              background: isSimulating ? '#ff4444' : 'var(--accent)', 
              color: isSimulating ? '#fff' : '#000',
              animation: isSimulating ? 'pulse 2s infinite' : 'none'
            }}
          >
            {isSimulating ? '■ Stop Simulation' : '▶ Simulate Live Data'}
          </button>
        </div>
      </header>

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
          <span>Sensors</span>
        </div>
        <div>
          <strong>{satelliteChanges.length}</strong>
          <span>Sat changes</span>
        </div>
        <div>
          <strong>{fusedAlerts.length}</strong>
          <span>Fused</span>
        </div>
      </div>

      <div className="dashboard-grid">
        <MapPanel alerts={alerts} sensors={sensors} satelliteChanges={satelliteChanges} />
        
        <aside className="sidebar" aria-label="Recent alerts">
          <h2>Recent alerts</h2>
          {!alerts.length && <p>No alerts yet.</p>}
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
                  Classifier: {alert.classifier_label} ({formatPercent(alert.classifier_confidence)})
                </p>
              )}
              {alert.metadata?.fusion_score !== undefined && (
                <p className="fusion-metadata">
                  Fusion score: {Number(alert.metadata.fusion_score).toFixed(4)}<br/>
                  Acoustic: {alert.metadata.acoustic_alert_id} | Satellite: {alert.metadata.satellite_change_id}
                </p>
              )}
              <label>
                Update status
                <select
                  value=""
                  disabled={!isAdmin}
                  onChange={(event) => {
                    if (event.target.value) onUpdateAlertStatus(alert.id, event.target.value)
                  }}
                >
                  <option value="">Choose status</option>
                  {ALERT_STATUSES.map((status) => (
                    <option key={status} value={status}>{status}</option>
                  ))}
                </select>
              </label>
            </article>
          ))}
        </aside>
      </div>
    </div>
  )
}
