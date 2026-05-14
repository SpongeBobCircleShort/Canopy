import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'

function alertStyle(alert) {
  if (alert.metadata?.fusion_score !== undefined || alert.type === 'fusion' || alert.type === 'fused_logging_risk') {
    return { color: '#6d28d9', fillColor: '#8b5cf6', fillOpacity: 0.9 }
  }
  if (alert.type === 'audio') return { color: '#b45309', fillColor: '#f59e0b', fillOpacity: 0.8 }
  return { color: '#b91c1c', fillColor: '#ef4444', fillOpacity: 0.8 }
}

export default function MapPanel({ alerts, sensors, satelliteChanges = [] }) {
  const firstSatellitePoint = satelliteChanges.find((change) => change.latitude !== null && change.longitude !== null)
  const center = alerts[0]?.location ?? sensors[0]?.location ?? (firstSatellitePoint ? { lat: firstSatellitePoint.latitude, lon: firstSatellitePoint.longitude } : { lat: 0, lon: 0 })

  return (
    <section className="map-panel" aria-label="Canopy map">
      <MapContainer center={[center.lat, center.lon]} zoom={6} scrollWheelZoom className="map-canvas">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {sensors.map((sensor) => (
          <CircleMarker
            key={`sensor-${sensor.id}`}
            center={[sensor.location.lat, sensor.location.lon]}
            pathOptions={{ color: '#0f766e', fillColor: '#14b8a6', fillOpacity: 0.8 }}
            radius={8}
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
              pathOptions={{ color: '#1d4ed8', fillColor: '#60a5fa', fillOpacity: 0.75 }}
              radius={10}
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
            pathOptions={alertStyle(alert)}
            radius={alert.metadata?.fusion_score !== undefined ? 14 : 11}
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
      </MapContainer>
    </section>
  )
}
