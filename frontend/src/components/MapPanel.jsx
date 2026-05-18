import { CircleMarker, MapContainer, Popup, TileLayer, useMapEvents } from 'react-leaflet'
import { useState } from 'react'

function alertStyle(alert, scale) {
  const base = { color: '#111111', weight: Math.max(1, 4 * scale), fillOpacity: 1 }
  switch (alert.priority) {
    case 'critical':
      return { ...base, fillColor: '#d32f2f' } // Muted Crimson
    case 'high':
      return { ...base, fillColor: '#d98218' } // Ochre / Burnt Orange
    case 'medium':
      return { ...base, fillColor: '#85b91b' } // Apple Green
    case 'low':
    default:
      return { ...base, fillColor: '#267bc4' } // Steel Blue
  }
}

function DynamicMarkers({ alerts, sensors, satelliteChanges }) {
  const map = useMapEvents({
    zoom() {
      setZoom(map.getZoom())
    }
  })
  const [zoom, setZoom] = useState(map.getZoom())

  // Scale factor: 1.0 at zoom 6. Shrinks down to 0.2 when zoomed out, grows up to 2.0 when zoomed in.
  const scale = Math.min(2.0, Math.max(0.15, zoom / 6))

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
              {change.change_type} · severity {Math.round(change.severity_score * 100)}%
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

export default function MapPanel({ alerts, sensors, satelliteChanges = [] }) {
  const firstSatellitePoint = satelliteChanges.find((change) => change.latitude !== null && change.longitude !== null)
  const center = alerts[0]?.location ?? sensors[0]?.location ?? (firstSatellitePoint ? { lat: firstSatellitePoint.latitude, lon: firstSatellitePoint.longitude } : { lat: 21.0, lon: 78.0 })

  return (
    <section className="map-panel" aria-label="Canopy map">
      <MapContainer center={[center.lat, center.lon]} zoom={6} scrollWheelZoom className="map-canvas">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <DynamicMarkers alerts={alerts} sensors={sensors} satelliteChanges={satelliteChanges} />
      </MapContainer>
    </section>
  )
}
