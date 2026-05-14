import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'

export default function MapPanel({ alerts, sensors }) {
  const center = alerts[0]?.location ?? sensors[0]?.location ?? { lat: 0, lon: 0 }

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
        {alerts.map((alert) => (
          <CircleMarker
            key={`alert-${alert.id}`}
            center={[alert.location.lat, alert.location.lon]}
            pathOptions={{ color: '#b91c1c', fillColor: '#ef4444', fillOpacity: 0.8 }}
            radius={11}
          >
            <Popup>
              <strong>{alert.type} alert</strong>
              <br />
              {alert.description}
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </section>
  )
}
