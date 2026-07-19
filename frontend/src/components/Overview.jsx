import { useMemo, useState } from 'react'
import MapPanel from './MapPanel.jsx'
import AnomalyLikelihood from './AnomalyLikelihood.jsx'

// ── Trend chart helpers ────────────────────────────────────────────────────

function bucketAlertsByWeek(alerts, weekCount = 8) {
  const now = Date.now()
  const MS_PER_WEEK = 7 * 24 * 60 * 60 * 1000
  const buckets = Array.from({ length: weekCount }, (_, i) => {
    const weekStart = now - (weekCount - i) * MS_PER_WEEK
    const weekEnd = weekStart + MS_PER_WEEK
    const label = new Date(weekStart).toLocaleDateString([], { month: 'short', day: 'numeric' })
    return { label, count: 0, weekStart, weekEnd }
  })
  for (const alert of alerts) {
    const ts = new Date(alert.created_at).getTime()
    const bucket = buckets.find((b) => ts >= b.weekStart && ts < b.weekEnd)
    if (bucket) bucket.count++
  }
  return buckets
}

function AlertTrendChart({ data }) {
  if (data.length < 2) {
    return <p style={{ fontSize: '0.72rem', color: '#666' }}>Not enough data.</p>
  }
  const W = 360
  const H = 120
  const PAD = { top: 10, right: 8, bottom: 24, left: 28 }
  const chartW = W - PAD.left - PAD.right
  const chartH = H - PAD.top - PAD.bottom
  const maxCount = Math.max(1, ...data.map((d) => d.count))
  const points = data.map((d, i) => ({
    x: PAD.left + (i / (data.length - 1)) * chartW,
    y: PAD.top + chartH - (d.count / maxCount) * chartH,
    ...d,
  }))
  const linePoints = points.map((p) => `${p.x},${p.y}`).join(' ')
  const areaPath =
    `M ${points[0].x},${points[0].y} ` +
    points.slice(1).map((p) => `L ${p.x},${p.y}`).join(' ') +
    ` L ${points[points.length - 1].x},${PAD.top + chartH}` +
    ` L ${points[0].x},${PAD.top + chartH} Z`

  const labelIndices = [0, Math.floor(points.length / 2), points.length - 1]

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: '100%', height: '140px', display: 'block', overflow: 'visible' }}
      aria-label="Alert trend over last 8 weeks"
    >
      <defs>
        <linearGradient id="canopy-trendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#94a878" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#94a878" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {[0, 0.5, 1].map((t) => {
        const y = PAD.top + chartH * (1 - t)
        return <line key={t} x1={PAD.left} y1={y} x2={PAD.left + chartW} y2={y} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
      })}
      <path d={areaPath} fill="url(#canopy-trendFill)" />
      <polyline points={linePoints} fill="none" stroke="#94a878" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      {points.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="3" fill="#94a878" stroke="#040404" strokeWidth="1.5">
          <title>{p.label}: {p.count} alert{p.count !== 1 ? 's' : ''}</title>
        </circle>
      ))}
      {points.filter((_, i) => labelIndices.includes(i)).map((p) => (
        <text key={p.label} x={p.x} y={H - 4} textAnchor="middle" fill="rgba(232,228,218,0.4)" fontSize="9" fontFamily="Inter, system-ui, sans-serif">
          {p.label}
        </text>
      ))}
      <text x={PAD.left - 4} y={PAD.top + 4} textAnchor="end" fill="rgba(232,228,218,0.4)" fontSize="9" fontFamily="Inter, system-ui, sans-serif">
        {maxCount}
      </text>
    </svg>
  )
}

// ── Overview ───────────────────────────────────────────────────────────────

export default function Overview({
  alerts,
  sensors,
  regions,
  satelliteChanges,
  onUpdateAlertStatus,
  isAdmin,
  isSimulating,
  setIsSimulating,
  lastUpdatedAt,
  onRefresh,
}) {
  const openAlerts = alerts.filter((a) => a.status === 'open')
  const fusedAlerts = alerts.filter((a) => a.type === 'fusion' || a.type === 'fused_logging_risk')
  const onlineSensors = sensors.filter((s) => s.status === 'online').length
  const offlineSensors = sensors.filter((s) => s.status === 'offline').length

  const [filterStatus, setFilterStatus] = useState('all')
  const [filterType, setFilterType] = useState('all')
  const [filterPriority, setFilterPriority] = useState('all')

  const filteredAlerts = useMemo(() => alerts.filter((a) => {
    if (filterStatus !== 'all' && a.status !== filterStatus) return false
    if (filterType !== 'all' && a.type !== filterType) return false
    if (filterPriority !== 'all' && a.priority !== filterPriority) return false
    return true
  }), [alerts, filterStatus, filterType, filterPriority])

  const weeklyBuckets = useMemo(() => bucketAlertsByWeek(alerts, 8), [alerts])

  function formatPercent(value) {
    return value === undefined || value === null ? 'n/a' : `${Math.round(Number(value) * 100)}%`
  }

  function formatTime(iso) {
    if (!iso) return null
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  const ALERT_STATUSES = ['acknowledged', 'investigating', 'resolved', 'dismissed']

  const selectStyle = { minHeight: 0, padding: '6px 8px', fontSize: '0.72rem' }
  const filterLabelStyle = {
    display: 'flex', flexDirection: 'column', gap: '4px',
    fontFamily: 'var(--font-label)', fontSize: '0.60rem',
    letterSpacing: '0.08em', textTransform: 'uppercase',
    color: 'var(--db-text-3)', margin: 0,
  }

  return (
    <div className="page-content">
      <header className="page-header" style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <p className="page-kicker">[ CONTROL ROOM · RECEIVING ]</p>
          <h2>Global overview</h2>
        </div>

        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          {lastUpdatedAt && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontFamily: 'var(--font-body)', fontSize: '0.72rem', fontWeight: 300, color: '#888' }}>
              <span>Updated {formatTime(lastUpdatedAt)}</span>
              <button className="simulation-button" style={{ padding: '6px 14px', fontSize: '0.68rem', minHeight: 0 }} onClick={onRefresh}>
                Refresh
              </button>
            </div>
          )}
          {!isAdmin && (
            <div style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)', borderRadius: '100px', padding: '4px 12px', fontFamily: 'var(--font-body)', fontWeight: 300, fontSize: '0.72rem', color: '#888', display: 'flex', alignItems: 'center' }}>
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

          {/* Detection Activity Trend Chart */}
          <div style={{ marginBottom: '28px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '20px' }}>
            <h2 style={{ fontFamily: 'var(--font-label)', textTransform: 'uppercase', letterSpacing: '0.10em', fontSize: '0.72rem', color: 'var(--db-text-2)', fontWeight: 400, marginBottom: '8px' }}>
              Detection Activity
              <span style={{ fontWeight: 300, fontSize: '0.68rem', color: '#666', marginLeft: '8px', textTransform: 'none', letterSpacing: 0 }}>
                last 8 weeks
              </span>
            </h2>
            <AlertTrendChart data={weeklyBuckets} />
          </div>

          {/* Priority Distribution Chart */}
          <div style={{ marginBottom: '32px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '20px' }}>
            <h2 style={{ fontFamily: 'var(--font-label)', textTransform: 'uppercase', letterSpacing: '0.10em', fontSize: '0.72rem', color: 'var(--db-text-2)', fontWeight: 400, marginBottom: '12px' }}>Priority Distribution</h2>
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

          {/* Alert Filters + List */}
          <div style={{ marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <h2 style={{ fontFamily: 'var(--font-label)', textTransform: 'uppercase', letterSpacing: '0.10em', fontSize: '0.72rem', color: 'var(--db-text-2)', fontWeight: 400, margin: 0 }}>RECENT ALERTS</h2>
              <span style={{ fontFamily: 'var(--font-body)', fontSize: '0.70rem', color: '#666' }}>
                {filteredAlerts.length} of {alerts.length}
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px', marginBottom: '16px' }}>
              <label style={filterLabelStyle}>
                Status
                <select className="status-select" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} style={selectStyle}>
                  <option value="all">All</option>
                  <option value="open">Open</option>
                  <option value="acknowledged">Ack'd</option>
                  <option value="investigating">Investig.</option>
                  <option value="resolved">Resolved</option>
                </select>
              </label>
              <label style={filterLabelStyle}>
                Type
                <select className="status-select" value={filterType} onChange={(e) => setFilterType(e.target.value)} style={selectStyle}>
                  <option value="all">All</option>
                  <option value="anomaly">Anomaly</option>
                  <option value="audio">Audio</option>
                  <option value="satellite">Satellite</option>
                  <option value="fusion">Fusion</option>
                </select>
              </label>
              <label style={filterLabelStyle}>
                Priority
                <select className="status-select" value={filterPriority} onChange={(e) => setFilterPriority(e.target.value)} style={selectStyle}>
                  <option value="all">All</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
            </div>
          </div>

          <div className="alert-feed" aria-label="Alert feed">
          {filteredAlerts.length === 0 && (
            <p style={{ color: '#666', fontSize: '0.82rem' }}>
              {alerts.length === 0 ? 'No alerts yet.' : 'No alerts match the active filters.'}
            </p>
          )}
          {filteredAlerts.map((alert) => (
            <article className={`alert-card ${alert.metadata?.fusion_score !== undefined ? 'fused-alert-card' : ''} animate-fade-slide-up`} key={alert.id}>
              <div>
                <span className={`pill ${alert.priority}`}>{alert.priority}</span>
                <span className="pill muted">{alert.type}</span>
                <span className="pill status">{alert.status}</span>
                {alert.metadata?.fusion_rule_version && (
                  <span className="pill status">{alert.metadata.fusion_rule_version === 'rule-fusion-v2' ? 'v2 engine' : alert.metadata.fusion_rule_version}</span>
                )}
              </div>
              <h3 style={{ fontFamily: 'var(--font-body)', fontSize: '0.875rem', fontWeight: 500, color: '#FFFFFF', textTransform: 'none', lineHeight: 1.4, marginBottom: '8px', marginTop: '12px' }}>
                {alert.description}
              </h3>
              <p style={{ fontFamily: 'var(--font-body)', fontWeight: 300, fontSize: '0.78rem', color: '#999', lineHeight: 1.6 }}>
                {alert.location.lat.toFixed(4)}, {alert.location.lon.toFixed(4)} · sensor {alert.sensor_id ?? 'none'}
              </p>
              {alert.metadata?.anomaly_score !== undefined && (
                <AnomalyLikelihood
                  anomalyScore={alert.metadata.anomaly_score}
                  isAnomaly={alert.metadata.is_anomaly}
                  likelihoods={alert.metadata.likelihoods}
                />
              )}
              {alert.metadata?.anomaly_score === undefined && alert.classifier_label && (
                <p style={{ fontFamily: 'var(--font-body)', fontWeight: 300, fontSize: '0.78rem', color: '#999', lineHeight: 1.6 }}>
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
              <label style={{ fontFamily: 'var(--font-label)', textTransform: 'uppercase', letterSpacing: '0.09em', fontSize: '0.65rem', color: '#888' }}>
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
          </div>
        </aside>
      </div>
    </div>
  )
}
