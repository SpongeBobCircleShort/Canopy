import { useMemo } from 'react'
import { MapContainer, Rectangle, Popup, TileLayer } from 'react-leaflet'
import { demoIndiaNdviCells } from '../demoData.js'

// NDVI-loss colour ramp: deep forest green → red as canopy loss deepens.
const LOSS_BANDS = [
  { min: 0.30, color: '#b91c1c', label: 'Severe loss (≥0.30)' },
  { min: 0.15, color: '#ea580c', label: 'Moderate (0.15–0.30)' },
  { min: 0.07, color: '#f59e0b', label: 'Mild (0.07–0.15)' },
  { min: 0.03, color: '#84cc16', label: 'Slight (0.03–0.07)' },
  { min: 0.0, color: '#15803d', label: 'Healthy forest (<0.03)' },
]

function lossColor(delta) {
  const loss = Math.max(0, -delta)
  return (LOSS_BANDS.find((band) => loss >= band.min) || LOSS_BANDS[LOSS_BANDS.length - 1]).color
}

const pct = (value) => `${Math.round(value * 100)}%`

export default function ForestLossMap({ cells = demoIndiaNdviCells }) {
  const stats = useMemo(() => {
    const lossCells = cells.filter((c) => c.ndvi_delta <= -0.07)
    const severe = cells.filter((c) => c.ndvi_delta <= -0.30)
    const meanLoss = lossCells.length
      ? lossCells.reduce((sum, c) => sum + -c.ndvi_delta, 0) / lossCells.length
      : 0

    const bySite = new Map()
    for (const c of cells) {
      const entry = bySite.get(c.site) || { site: c.site, total: 0, loss: 0, worst: 0, lat: c.lat, lon: c.lon }
      entry.total += 1
      if (c.ndvi_delta <= -0.07) entry.loss += 1
      entry.worst = Math.min(entry.worst, c.ndvi_delta)
      bySite.set(c.site, entry)
    }
    const sites = [...bySite.values()].sort((a, b) => a.worst - b.worst)
    return { lossCells, severe, meanLoss, sites }
  }, [cells])

  return (
    <section className="forest-loss-view">
      <header className="page-header">
        <h1>Forest Loss — India</h1>
        <p className="page-subtitle">
          Sentinel-2 NDVI change across monitored Indian forest landscapes. Each cell compares
          baseline vs recent NDVI; warmer cells are deeper canopy loss.
        </p>
      </header>

      <div className="metrics-grid" aria-label="Forest loss metrics">
        <div className="glass-card">
          <strong>{cells.length}</strong>
          <span>NDVI cells</span>
        </div>
        <div className="glass-card">
          <strong style={{ color: '#f59e0b' }}>{stats.lossCells.length}</strong>
          <span>Forest-loss cells</span>
        </div>
        <div className="glass-card">
          <strong style={{ color: '#b91c1c' }}>{stats.severe.length}</strong>
          <span>Severe hotspots</span>
        </div>
        <div className="glass-card">
          <strong>{pct(stats.meanLoss)}</strong>
          <span>Mean canopy loss</span>
        </div>
      </div>

      <div className="forest-loss-legend">
        {LOSS_BANDS.map((band) => (
          <span className="legend-item" key={band.color}>
            <span className="legend-swatch" style={{ background: band.color }} />
            {band.label}
          </span>
        ))}
      </div>

      <MapContainer center={[22.5, 80]} zoom={5} scrollWheelZoom className="map-canvas forest-loss-map">
        <TileLayer
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        {cells.map((cell) => {
          const h = cell.cell_size_deg / 2
          const bounds = [
            [cell.lat - h, cell.lon - h],
            [cell.lat + h, cell.lon + h],
          ]
          const color = lossColor(cell.ndvi_delta)
          return (
            <Rectangle
              key={cell.id}
              bounds={bounds}
              pathOptions={{
                color,
                weight: 0.3,
                fillColor: color,
                fillOpacity: cell.ndvi_delta <= -0.03 ? 0.7 : 0.4,
              }}
            >
              <Popup>
                <strong>{cell.site}</strong>
                <br />
                {cell.lat.toFixed(3)}, {cell.lon.toFixed(3)}
                <br />
                Baseline NDVI {cell.baseline_ndvi.toFixed(2)} → recent {cell.recent_ndvi.toFixed(2)}
                <br />
                ΔNDVI {cell.ndvi_delta.toFixed(2)} · severity {pct(cell.severity)}
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
              <th>Worst ΔNDVI</th>
            </tr>
          </thead>
          <tbody>
            {stats.sites.map((site) => (
              <tr key={site.site}>
                <td>{site.site}</td>
                <td>{site.loss} / {site.total}</td>
                <td style={{ color: lossColor(site.worst), fontWeight: 600 }}>{site.worst.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
