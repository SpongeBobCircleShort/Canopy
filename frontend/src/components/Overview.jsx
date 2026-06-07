import MapPanel from './MapPanel.jsx'

export default function Overview({
  alerts,
  sensors,
  regions,
  satelliteChanges,
  onUpdateAlertStatus,
  isAdmin,
  isSimulating,
  setIsSimulating
}) {
  const openAlerts = alerts.filter((a) => a.status === 'open')
  const fusedAlerts = alerts.filter((a) => a.type === 'fusion' || a.type === 'fused_logging_risk')
  const onlineSensors = sensors.filter((s) => s.status === 'online').length
  const offlineSensors = sensors.filter((s) => s.status === 'offline').length

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
        <div className="glass-card">
          <strong>{alerts.length}</strong>
          <span>Total alerts</span>
        </div>
        <div className="glass-card">
          <strong>{openAlerts.length}</strong>
          <span>Open alerts</span>
        </div>
        <div className="glass-card">
          <strong>{onlineSensors}</strong>
          <span>Online</span>
        </div>
        <div className="glass-card">
          <strong>{offlineSensors}</strong>
          <span>Offline</span>
        </div>
        <div className="glass-card">
          <strong>{satelliteChanges.length}</strong>
          <span>Sat changes</span>
        </div>
        <div className="glass-card">
          <strong>{fusedAlerts.length}</strong>
          <span>Fused</span>
        </div>
      </div>

      <div className="dashboard-grid">
        <MapPanel alerts={alerts} sensors={sensors} satelliteChanges={satelliteChanges} regions={regions} />
        
        <aside className="sidebar" aria-label="Recent alerts">
          {/* Priority Distribution CSS Chart */}
          <div style={{ marginBottom: '32px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '20px' }}>
            <h2 style={{ fontFamily: "var(--font-label)", textTransform: "uppercase", letterSpacing: "0.10em", fontSize: "0.78rem", color: "#FFFFFF", fontWeight: 500, marginBottom: "12px" }}>Priority Distribution</h2>
            <div className="priority-chart">
              {(() => {
                const priorityCounts = alerts.reduce(
                  (acc, alert) => {
                    const p = alert.priority?.toLowerCase() || 'low'
                    acc[p] = (acc[p] || 0) + 1
                    return acc
                  },
                  { critical: 0, high: 0, medium: 0, low: 0 }
                )
                const maxCount = Math.max(1, ...Object.values(priorityCounts))
                return ['critical', 'high', 'medium', 'low'].map((p) => {
                  const count = priorityCounts[p] || 0
                  const percent = (count / maxCount) * 100
                  return (
                    <div key={p} className="chart-bar-row">
                      <span className="chart-label">{p}</span>
                      <div className="chart-track">
                        <div className={`chart-fill ${p}`} style={{ width: `${percent}%` }} />
                      </div>
                      <span className="chart-value">{count}</span>
                    </div>
                  )
                })
              })()}
            </div>
          </div>

          <h2 style={{ fontFamily: "var(--font-label)", textTransform: "uppercase", letterSpacing: "0.10em", fontSize: "0.78rem", color: "#FFFFFF", fontWeight: 500, marginBottom: "20px" }}>RECENT ALERTS</h2>
          {!alerts.length && <p>No alerts yet.</p>}
          {alerts.map((alert) => (
            <article className={`alert-card ${alert.metadata?.fusion_score !== undefined ? 'fused-alert-card' : ''} animate-fade-slide-up`} key={alert.id}>
              <div>
                <span className={`pill ${alert.priority}`}>{alert.priority}</span>
                <span className="pill muted">{alert.type}</span>
                <span className="pill status">{alert.status}</span>
                {alert.metadata?.fusion_rule_version && (
                  <span className="pill status">{alert.metadata.fusion_rule_version === 'rule-fusion-v2' ? 'v2 engine' : alert.metadata.fusion_rule_version}</span>
                )}
              </div>
              <h3 style={{ fontFamily: "var(--font-body)", fontSize: "0.875rem", fontWeight: 500, color: "#FFFFFF", textTransform: "none", lineHeight: 1.4, marginBottom: "8px", marginTop: "12px" }}>
                {alert.description}
              </h3>
              <p style={{ fontFamily: "var(--font-body)", fontWeight: 300, fontSize: "0.78rem", color: "#999", lineHeight: 1.6 }}>
                {alert.location.lat.toFixed(4)}, {alert.location.lon.toFixed(4)} · sensor {alert.sensor_id ?? 'none'}
              </p>
              {alert.classifier_label && (
                <p style={{ fontFamily: "var(--font-body)", fontWeight: 300, fontSize: "0.78rem", color: "#999", lineHeight: 1.6 }}>
                  Classifier: {alert.classifier_label} ({formatPercent(alert.classifier_confidence)})
                  {alert.metadata?.model_domain ? ` · ${alert.metadata.model_domain}` : ''}
                </p>
              )}
              {alert.metadata?.fusion_score !== undefined && (
                <div className="fusion-metadata" style={{ marginTop: '10px', padding: '8px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', fontSize: '0.78rem' }}>
                  <p style={{ margin: '0 0 6px', fontWeight: 500 }}>
                    Fusion Score: <span style={{ color: 'var(--db-green)' }}>{Number(alert.metadata.fusion_score).toFixed(4)}</span>
                    {alert.metadata.fusion_scoring_mode ? ` (${alert.metadata.fusion_scoring_mode})` : ''}
                  </p>
                  <p style={{ margin: '4px 0', fontSize: '0.74rem', color: '#999' }}>
                    IDs: Acoustic #{alert.metadata.acoustic_alert_id} · Satellite #{alert.metadata.satellite_change_id}
                  </p>
                  
                  {/* v2 specific rendering */}
                  {alert.metadata.fusion_rule_version === 'rule-fusion-v2' && (
                    <>
                      <div className="decay-container">
                        <div className="decay-row">
                          <span>Temporal Decay: {alert.metadata.temporal_decay ? Number(alert.metadata.temporal_decay).toFixed(2) : 'n/a'}</span>
                          <div className="decay-bar-bg">
                            <div className="decay-bar-fill temporal" style={{ width: `${(alert.metadata.temporal_decay || 0) * 100}%` }} />
                          </div>
                        </div>
                        <div className="decay-row">
                          <span>Spatial Decay: {alert.metadata.spatial_decay ? Number(alert.metadata.spatial_decay).toFixed(2) : 'n/a'}</span>
                          <div className="decay-bar-bg">
                            <div className="decay-bar-fill spatial" style={{ width: `${(alert.metadata.spatial_decay || 0) * 100}%` }} />
                          </div>
                        </div>
                      </div>
                      
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px', fontSize: '0.72rem', color: '#8f9f8b' }}>
                        <div>Corroborated: <strong>{alert.metadata.corroborating_change_count || 1} change(s)</strong></div>
                        <div>Quality Multiplier: <strong>{alert.metadata.source_quality_multiplier ? alert.metadata.source_quality_multiplier.toFixed(2) : '1.0'}x</strong></div>
                      </div>
                    </>
                  )}
                </div>
              )}
              <label style={{ fontFamily: "var(--font-label)", textTransform: "uppercase", letterSpacing: "0.09em", fontSize: "0.65rem", color: "#888" }}>
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
