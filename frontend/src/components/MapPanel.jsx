import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'

function alertStyle(alert, scale) {
  const base = { color: '#111111', weight: Math.max(1, 4 * scale), fillOpacity: 1 }

  if (alert.metadata?.fusion_score !== undefined || alert.type === 'fusion' || alert.type === 'fused_logging_risk') {
    return { ...base, fillColor: '#8b5cf6' }
  }

  switch (alert.priority) {
    case 'critical':
      return { ...base, fillColor: '#d32f2f' }
    case 'high':
      return { ...base, fillColor: '#d98218' }
    case 'medium':
      return { ...base, fillColor: '#85b91b' }
    case 'low':
    default:
      return { ...base, fillColor: '#267bc4' }
  }
}

function DynamicMarkers({ alerts, sensors, satelliteChanges }) {
  const map = useMapEvents({
    zoom() {
      setZoom(map.getZoom())
    },
  })
  const [zoom, setZoom] = useState(map.getZoom())
  const scale = Math.min(2, Math.max(0.15, zoom / 6))

  return (
    <>
      {sensors.map((sensor) => (
        <CircleMarker
          key={`sensor-${sensor.id}`}
          center={[sensor.location.lat, sensor.location.lon]}
          pathOptions={{ color: '#111111', weight: Math.max(1, 3 * scale), fillColor: '#62d2c1', fillOpacity: 1 }}
          radius={Math.max(2, 8 * scale)}
        >
          <Popup>
            <strong>{sensor.name}</strong>
            <br />
            Sensor status: {sensor.status}
          </Popup>
        </CircleMarker>
      ))}
      {satelliteChanges
        .filter((change) => change.latitude !== null && change.longitude !== null)
        .map((change) => (
          <CircleMarker
            key={`satellite-change-${change.id}`}
            center={[change.latitude, change.longitude]}
            pathOptions={{ color: '#111111', weight: Math.max(1, 3 * scale), fillColor: '#d4ff00', fillOpacity: 1 }}
            radius={Math.max(2.5, 10 * scale)}
          >
            <Popup>
              <strong>Satellite change #{change.id}</strong>
              <br />
              {change.change_type} severity {Math.round(change.severity_score * 100)}%
              {change.description && (
                <>
                  <br />
                  {change.description}
                </>
              )}
            </Popup>
          </CircleMarker>
        ))}
      {alerts.map((alert) => (
        <CircleMarker
          key={`alert-${alert.id}`}
          center={[alert.location.lat, alert.location.lon]}
          pathOptions={alertStyle(alert, scale)}
          radius={alert.metadata?.fusion_score !== undefined ? Math.max(3, 14 * scale) : Math.max(2.5, 11 * scale)}
        >
          <Popup>
            <strong>{alert.metadata?.fusion_score !== undefined ? 'Fused' : alert.type} alert</strong>
            <br />
            {alert.description}
            {alert.metadata?.fusion_score !== undefined && (
              <>
                <br />
                Fusion score: {Number(alert.metadata.fusion_score).toFixed(4)}
              </>
            )}
          </Popup>
        </CircleMarker>
      ))}
    </>
  )
}

function markerPoints(alerts, sensors, satelliteChanges) {
  return [
    ...alerts.map((alert) => [alert.location.lat, alert.location.lon]),
    ...sensors.map((sensor) => [sensor.location.lat, sensor.location.lon]),
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

export default function MapPanel({ alerts, sensors, satelliteChanges = [] }) {
  const firstSatellitePoint = satelliteChanges.find((change) => change.latitude !== null && change.longitude !== null)
  const center = alerts[0]?.location ?? sensors[0]?.location ?? (firstSatellitePoint ? { lat: firstSatellitePoint.latitude, lon: firstSatellitePoint.longitude } : { lat: 21, lon: 78 })

  return (
    <section className="map-panel" aria-label="Canopy map">
      <MapContainer center={[center.lat, center.lon]} zoom={6} scrollWheelZoom className="map-canvas">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <AutoFitBounds alerts={alerts} sensors={sensors} satelliteChanges={satelliteChanges} />
        <DynamicMarkers alerts={alerts} sensors={sensors} satelliteChanges={satelliteChanges} />
      </MapContainer>
    </section>
  )
}
