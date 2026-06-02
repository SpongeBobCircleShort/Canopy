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
      <header className="page-header" style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontFamily: "var(--font-label)", fontWeight: 600, letterSpacing: "0.10em", fontSize: "1.4rem", color: "#FFFFFF", margin: 0 }}>GLOBAL OVERVIEW</h2>
        
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          {!isAdmin && (
            <div style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.10)", borderRadius: "100px", padding: "4px 12px", fontFamily: "var(--font-body)", fontWeight: 300, fontSize: "0.72rem", color: "#888", display: "flex", alignItems: "center" }}>
              Demo mode · API not connected
            </div>
          )}
          <div className="header-actions">
            <button 
              className={`export-button simulation-button ${isSimulating ? 'active' : ''}`}
              onClick={() => setIsSimulating(!isSimulating)}
            >
              {isSimulating ? 'Stop Simulation' : 'Simulate Live Data'}
            </button>
          </div>
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
          <h2 style={{ fontFamily: "var(--font-label)", textTransform: "uppercase", letterSpacing: "0.10em", fontSize: "0.78rem", color: "#FFFFFF", fontWeight: 500, marginBottom: "20px" }}>RECENT ALERTS</h2>
          {!alerts.length && <p>No alerts yet.</p>}
          {alerts.map((alert) => (
            <article className={`alert-card ${alert.metadata?.fusion_score !== undefined ? 'fused-alert-card' : ''}`} key={alert.id}>
              <div>
                <span className={`pill ${alert.priority}`}>{alert.priority}</span>
                <span className="pill muted">{alert.type}</span>
                <span className="pill status">{alert.status}</span>
              </div>
              <h3 style={{ fontFamily: "var(--font-body)", fontSize: "0.875rem", fontWeight: 500, color: "#FFFFFF", textTransform: "none", lineHeight: 1.4, marginBottom: "8px", marginTop: "12px" }}>
                {alert.description}
              </h3>
              <p style={{ fontFamily: "var(--font-body)", fontWeight: 300, fontSize: "0.78rem", color: "#666", lineHeight: 1.6 }}>
                {alert.location.lat.toFixed(4)}, {alert.location.lon.toFixed(4)} · sensor {alert.sensor_id ?? 'none'}
              </p>
              {alert.classifier_label && (
                <p style={{ fontFamily: "var(--font-body)", fontWeight: 300, fontSize: "0.78rem", color: "#666", lineHeight: 1.6 }}>
                  Classifier: {alert.classifier_label} ({formatPercent(alert.classifier_confidence)})
                  {alert.metadata?.model_domain ? ` · ${alert.metadata.model_domain}` : ''}
                </p>
              )}
              {alert.metadata?.fusion_score !== undefined && (
                <p className="fusion-metadata">
                  Fusion score: {Number(alert.metadata.fusion_score).toFixed(4)}<br/>
                  Acoustic: {alert.metadata.acoustic_alert_id} | Satellite: {alert.metadata.satellite_change_id}
                  {alert.metadata.fusion_scoring_mode ? ` | ${alert.metadata.fusion_scoring_mode}` : ''}
                </p>
              )}
              <label style={{ fontFamily: "var(--font-label)", textTransform: "uppercase", letterSpacing: "0.09em", fontSize: "0.65rem", color: "#555" }}>
                Update status
                <select className="status-select"
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
