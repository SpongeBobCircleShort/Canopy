import { Fragment, useEffect, useMemo, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'

function alertStyle(alert, scale) {
  const base = { color: '#040404', weight: Math.max(1, 4 * scale), fillOpacity: 1 }

  if (alert.priority === 'critical') {
    base.className = 'marker-pulse'
  }

  if (alert.metadata?.fusion_score !== undefined || alert.type === 'fusion' || alert.type === 'fused_logging_risk') {
    return { ...base, fillColor: '#e8e4da' }
  }

  switch (alert.priority) {
    case 'critical':
      return { ...base, fillColor: '#e05a3a' }
    case 'high':
      return { ...base, fillColor: '#d8b45a' }
    case 'medium':
      return { ...base, fillColor: '#94a878' }
    case 'low':
    default:
      return { ...base, fillColor: '#6f7a68' }
  }
}

function satelliteChangeColor(source) {
  switch (source) {
    case 'sentinel_2':
      return '#7f96a8' // Bright cyan
    case 'csv_ndvi':
      return '#c9c39a' // Yellow
    case 'manual':
    default:
      return '#e8e4da' // Cream
  }
}

function DynamicMarkers({ alerts, sensors, satelliteChanges, regions = [] }) {
  const map = useMapEvents({
    zoom() {
      setZoom(map.getZoom())
    },
  })
  const [zoom, setZoom] = useState(map.getZoom())
  const scale = Math.min(2, Math.max(0.15, zoom / 6))

  return (
    <>
      {regions.filter((r) => r.boundary).map((region) => {
        let geo
        try { geo = typeof region.boundary === 'string' ? JSON.parse(region.boundary) : region.boundary } catch { return null }
        return (
          <GeoJSON
            key={`region-${region.id}`}
            data={geo}
            style={{ color: '#94a878', weight: 1.5, fillOpacity: 0.07, dashArray: '6 4' }}
          >
            <Popup><strong>{region.name}</strong></Popup>
          </GeoJSON>
        )
      })}
      {sensors.map((sensor) => {
        if (!sensor.location?.lat || !sensor.location?.lon) return null
        return (
          <CircleMarker
            key={`sensor-${sensor.id}`}
            center={[sensor.location.lat, sensor.location.lon]}
            pathOptions={{ color: '#040404', weight: Math.max(1, 3 * scale), fillColor: '#94a878', fillOpacity: 1 }}
            radius={Math.max(2, 8 * scale)}
          >
            <Popup>
              <strong>{sensor.name}</strong>
              <br />
              Sensor status: {sensor.status}
            </Popup>
          </CircleMarker>
        )
      })}
      {satelliteChanges
        .filter((change) => change.latitude !== null && change.longitude !== null)
        .map((change) => (
          <CircleMarker
            key={`satellite-change-${change.id}`}
            center={[change.latitude, change.longitude]}
            pathOptions={{ color: '#040404', weight: Math.max(1, 3 * scale), fillColor: satelliteChangeColor(change.source), fillOpacity: 1 }}
            radius={Math.max(2.5, 10 * scale)}
          >
            <Popup>
              <strong>Satellite change #{change.id}</strong>
              <br />
              {change.change_type} severity {Math.round(change.severity_score * 100)}%
              <br />
              Source: {change.source}
              {change.image_date && (
                <>
                  <br />
                  Image Date: {new Date(change.image_date).toLocaleDateString()}
                </>
              )}
              {change.description && (
                <>
                  <br />
                  {change.description}
                </>
              )}
              {change.metadata?.discriminators && (
                <>
                  <br />
                  <span style={{ fontSize: '0.85em', color: '#555' }}>
                    {change.metadata.discriminators.likely_regional
                      ? '⚠ likely regional (weather/season)'
                      : '✓ local anomaly vs region'}
                    {' · residual '}
                    {Number(change.metadata.discriminators.local_residual).toFixed(2)}
                    {' · '}
                    {Math.round((change.metadata.discriminators.valid_fraction ?? 0) * 100)}% clear
                  </span>
                </>
              )}
            </Popup>
          </CircleMarker>
        ))}
      {alerts.map((alert) => {
        if (!alert.location?.lat || !alert.location?.lon) return null
        const isFused = alert.metadata?.fusion_score !== undefined
        const spatialDecay = alert.metadata?.spatial_decay
        return (
          <Fragment key={`alert-group-${alert.id}`}>
            {isFused && spatialDecay !== undefined && (
              <CircleMarker
                center={[alert.location.lat, alert.location.lon]}
                pathOptions={{
                  color: '#94a878',
                  weight: 1,
                  fillColor: '#94a878',
                  fillOpacity: spatialDecay * 0.25,
                  dashArray: '4, 4',
                }}
                radius={Math.max(12, 32 * scale)}
                interactive={false}
              />
            )}
            <CircleMarker
              center={[alert.location.lat, alert.location.lon]}
              pathOptions={alertStyle(alert, scale)}
              radius={isFused ? Math.max(3, 14 * scale) : Math.max(2.5, 11 * scale)}
            >
              <Popup>
                <strong>{isFused ? 'Fused' : alert.type} alert</strong>
                <br />
                {alert.description}
                {isFused && (
                  <>
                    <br />
                    Fusion score: {Number(alert.metadata.fusion_score).toFixed(4)}
                  </>
                )}
              </Popup>
            </CircleMarker>
          </Fragment>
        )
      })}
    </>
  )
}

function markerPoints(alerts, sensors, satelliteChanges) {
  return [
    ...alerts.filter((alert) => alert.location?.lat && alert.location?.lon).map((alert) => [alert.location.lat, alert.location.lon]),
    ...sensors.filter((sensor) => sensor.location?.lat && sensor.location?.lon).map((sensor) => [sensor.location.lat, sensor.location.lon]),
    ...satelliteChanges
      .filter((change) => change.latitude !== null && change.longitude !== null)
      .map((change) => [change.latitude, change.longitude]),
  ]
}

function AutoFitBounds({ alerts, sensors, satelliteChanges }) {
  const map = useMap()
  const points = useMemo(() => markerPoints(alerts, sensors, satelliteChanges), [alerts, sensors, satelliteChanges])
  const boundsKey = points.map(([lat, lon]) => `${lat}:${lon}`).join('|')

  useEffect(() => {
    if (!points.length) return
    if (points.length === 1) {
      map.setView(points[0], Math.max(map.getZoom(), 8), { animate: true })
      return
    }
    map.fitBounds(points, { animate: true, maxZoom: 10, padding: [48, 48] })
  }, [boundsKey, map, points])

  return null
}

export default function MapPanel({ alerts, sensors, satelliteChanges = [], regions = [] }) {
  const firstSatellitePoint = satelliteChanges.find((change) => change.latitude !== null && change.longitude !== null)
  const center = alerts[0]?.location ?? sensors[0]?.location ?? (firstSatellitePoint ? { lat: firstSatellitePoint.latitude, lon: firstSatellitePoint.longitude } : { lat: 21, lon: 78 })

  return (
    <section className="map-panel" aria-label="Canopy map">
      <MapContainer center={[center.lat, center.lon]} zoom={6} scrollWheelZoom className="map-canvas">
        <TileLayer
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <AutoFitBounds alerts={alerts} sensors={sensors} satelliteChanges={satelliteChanges} />
        <DynamicMarkers alerts={alerts} sensors={sensors} satelliteChanges={satelliteChanges} regions={regions} />
      </MapContainer>
    </section>
  )
}
