import { useMemo } from 'react'
import { MapContainer, Rectangle, Popup, TileLayer } from 'react-leaflet'
import { demoIndiaNdviCells } from '../demoData.js'

// Change-severity colour ramp: deep forest green → red as canopy change deepens.
// Magnitude is loss-magnitude for NDVI demo cells (−Δ) and severity for the live
// AlphaEarth-embedding cells — both in the same 0–1 range so one ramp serves both.
const CHANGE_BANDS = [
  { min: 0.30, color: '#e05a3a', label: 'Severe (≥0.30)' },
  { min: 0.15, color: '#d8843f', label: 'Moderate (0.15–0.30)' },
  { min: 0.07, color: '#d8b45a', label: 'Mild (0.07–0.15)' },
  { min: 0.03, color: '#b9c98a', label: 'Slight (0.03–0.07)' },
  { min: 0.0, color: '#6f8f5f', label: 'Healthy forest (<0.03)' },
]

// Dynamic World land-cover transitions → human-facing cause.
const TRANSITION_LEGEND = [
  { label: 'Trees → Bare / Crops / Built = canopy loss' },
  { label: 'Trees → Shrub = degradation' },
]

function colorForMagnitude(magnitude) {
  const m = Math.max(0, magnitude)
  return (CHANGE_BANDS.find((band) => m >= band.min) || CHANGE_BANDS[CHANGE_BANDS.length - 1]).color
}

const pct = (value) => `${Math.round(value * 100)}%`

// Normalise either cell shape (synthetic NDVI demo, or live AlphaEarth/Dynamic
// World embedding cells) into one render contract.
function normalizeCell(cell) {
  const isEmbedding = cell.embedding_change !== undefined || cell.dw_transition_class !== undefined
  if (isEmbedding) {
    const severity = cell.severity ?? 0
    const tClass = cell.dw_transition_class
    return {
      kind: 'embedding',
      id: cell.id,
      site: cell.site,
      lat: cell.lat,
      lon: cell.lon,
      cellSize: cell.cell_size_deg ?? 0.09,
      magnitude: severity,
      severity,
      embeddingChange: cell.embedding_change,
      transition: tClass
        ? `trees → ${tClass}${cell.dw_transition_prob != null ? ` (${pct(cell.dw_transition_prob)})` : ''}`
        : 'unattributed',
    }
  }
  const loss = Math.max(0, -(cell.ndvi_delta ?? 0))
  return {
    kind: 'ndvi',
    id: cell.id,
    site: cell.site,
    lat: cell.lat,
    lon: cell.lon,
    cellSize: cell.cell_size_deg ?? 0.05,
    magnitude: loss,
    severity: cell.severity ?? Math.min(loss / 0.5, 1),
    baselineNdvi: cell.baseline_ndvi,
    recentNdvi: cell.recent_ndvi,
    ndviDelta: cell.ndvi_delta,
  }
}

export default function ForestLossMap({ cells = demoIndiaNdviCells }) {
  const normalized = useMemo(() => cells.map(normalizeCell), [cells])

  const stats = useMemo(() => {
    const lossCells = normalized.filter((c) => c.magnitude >= 0.07)
    const severe = normalized.filter((c) => c.magnitude >= 0.30)
    const meanLoss = lossCells.length
      ? lossCells.reduce((sum, c) => sum + c.magnitude, 0) / lossCells.length
      : 0

    const bySite = new Map()
    for (const c of normalized) {
      const entry = bySite.get(c.site) || { site: c.site, total: 0, loss: 0, worst: 0 }
      entry.total += 1
      if (c.magnitude >= 0.07) entry.loss += 1
      entry.worst = Math.max(entry.worst, c.magnitude)
      bySite.set(c.site, entry)
    }
    const sites = [...bySite.values()].sort((a, b) => b.worst - a.worst)
    return { lossCells, severe, meanLoss, sites }
  }, [normalized])

  return (
    <section className="forest-loss-view">
      <header className="page-header">
        <div>
          <p className="page-kicker">[ SATELLITE CROSS-CHECK ]</p>
          <h1>Forest loss · India</h1>
        </div>
        <p className="page-subtitle">
          Satellite change across monitored Indian forest landscapes. The live pipeline scores
          AlphaEarth annual embedding change, attributed by Dynamic World land-cover transitions;
          warmer cells are deeper canopy loss. (Demo data shows NDVI change.)
        </p>
      </header>

      <div className="metrics-grid" aria-label="Forest loss metrics">
        <div className="glass-card">
          <strong>{normalized.length}</strong>
          <span>Change cells</span>
        </div>
        <div className="glass-card">
          <strong style={{ color: '#d8b45a' }}>{stats.lossCells.length}</strong>
          <span>Forest-loss cells</span>
        </div>
        <div className="glass-card">
          <strong style={{ color: '#e05a3a' }}>{stats.severe.length}</strong>
          <span>Severe hotspots</span>
        </div>
        <div className="glass-card">
          <strong>{pct(stats.meanLoss)}</strong>
          <span>Mean canopy loss</span>
        </div>
      </div>

      <div className="forest-loss-legend">
        {CHANGE_BANDS.map((band) => (
          <span className="legend-item" key={band.color}>
            <span className="legend-swatch" style={{ background: band.color }} />
            {band.label}
          </span>
        ))}
      </div>
      <div className="forest-loss-legend forest-loss-legend--transitions">
        {TRANSITION_LEGEND.map((item) => (
          <span className="legend-item" key={item.label}>{item.label}</span>
        ))}
      </div>

      <MapContainer center={[22.5, 80]} zoom={5} scrollWheelZoom className="map-canvas forest-loss-map">
        <TileLayer
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        {normalized.map((cell) => {
          const h = cell.cellSize / 2
          const bounds = [
            [cell.lat - h, cell.lon - h],
            [cell.lat + h, cell.lon + h],
          ]
          const color = colorForMagnitude(cell.magnitude)
          return (
            <Rectangle
              key={cell.id}
              bounds={bounds}
              pathOptions={{
                color,
                weight: 0.3,
                fillColor: color,
                fillOpacity: cell.magnitude >= 0.03 ? 0.7 : 0.4,
              }}
            >
              <Popup>
                <strong>{cell.site}</strong>
                <br />
                {cell.lat.toFixed(3)}, {cell.lon.toFixed(3)}
                <br />
                {cell.kind === 'embedding' ? (
                  <>
                    AlphaEarth change {cell.embeddingChange?.toFixed(3)}
                    <br />
                    Dynamic World: {cell.transition}
                    <br />
                    severity {pct(cell.severity)}
                  </>
                ) : (
                  <>
                    Baseline NDVI {cell.baselineNdvi.toFixed(2)} → recent {cell.recentNdvi.toFixed(2)}
                    <br />
                    ΔNDVI {cell.ndviDelta.toFixed(2)} · severity {pct(cell.severity)}
                  </>
                )}
              </Popup>
            </Rectangle>
          )
        })}
      </MapContainer>

      <div className="forest-loss-sites glass-card">
        <h2>Landscape breakdown</h2>
        <table className="sites-table">
          <thead>
            <tr>
              <th>Landscape</th>
              <th>Loss cells</th>
              <th>Worst change</th>
            </tr>
          </thead>
          <tbody>
            {stats.sites.map((site) => (
              <tr key={site.site}>
                <td>{site.site}</td>
                <td>{site.loss} / {site.total}</td>
                <td style={{ color: colorForMagnitude(site.worst), fontWeight: 600 }}>{pct(site.worst)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
