import { useState } from 'react'
import ToastStack from './ToastStack.jsx'
import SentinelIngestCard from './SentinelIngestCard.jsx'

const CHANGE_TYPES = ['ndvi_drop', 'canopy_loss', 'vegetation_stress', 'burn_scar', 'unknown']

function regionName(regions, regionId) {
  return regions.find((r) => r.id === regionId)?.name || (regionId ? `region ${regionId}` : 'No region')
}

export default function DataIngestion({
  sensors,
  regions,
  ndviBatches,
  satelliteChanges,
  fusionResult,
  ndviUploadResult,
  isAuthenticated,
  isAdmin,
  onUploadClip,
  onUploadNdviCsv,
  onCreateSatelliteChange,
  onRunFusion,
  onExportAlerts,
  onIngestSentinel
}) {
  const [clipForm, setClipForm] = useState({ sensorId: '', file: null })
  const [ndviForm, setNdviForm] = useState({ regionId: '', lossThreshold: '-0.15', defaultConfidence: '0.75', file: null })
  const [satelliteForm, setSatelliteForm] = useState({
    region_id: '', source: 'manual', change_type: 'ndvi_drop',
    severity_score: '0.7', confidence: '0.8', latitude: '', longitude: '', description: ''
  })
  
  const [fusionForm, setFusionForm] = useState({
    time_decay_halflife_days: '7.0',
    spatial_sigma_meters: '200.0',
  })
  
  const [localError, setLocalError] = useState('')
  const [localSuccess, setLocalSuccess] = useState('')

  async function submitWithLocalError(action, successMsg = '') {
    setLocalError('')
    setLocalSuccess('')
    try { 
      await action() 
      if (successMsg) setLocalSuccess(successMsg)
    } catch (err) { 
      setLocalError(err.message) 
    }
  }

  return (
    <div className="page-content">
      <header className="page-header">
        <h2>Data Ingestion & Fusion</h2>
        <div className="header-actions">
          <button className="export-button" onClick={() => submitWithLocalError(onExportAlerts, 'Alerts CSV exported successfully.')} disabled={!isAdmin}>
            Export CSV
          </button>
        </div>
      </header>
      
      <ToastStack 
        toasts={[
          localError ? { id: `ingestion-error-${localError}`, type: 'error', message: localError } : null,
          localSuccess ? { id: `ingestion-success-${localSuccess}`, type: 'success', message: localSuccess } : null,
        ].filter(Boolean)} 
      />

      <section className="workflow-grid">
        <form className="control-card" onSubmit={(e) => { e.preventDefault(); submitWithLocalError(() => onUploadClip(clipForm), 'Audio clip uploaded successfully.'); }}>
          <h2>Upload audio clip</h2>
          <label>Sensor
            <select value={clipForm.sensorId} onChange={(e) => setClipForm({ ...clipForm, sensorId: e.target.value })} required>
              <option value="">Select a sensor</option>
              {sensors.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label>Audio file
            <input type="file" accept="audio/*" onChange={(e) => setClipForm({ ...clipForm, file: e.target.files[0] })} required />
          </label>
          <button type="submit" disabled={!isAuthenticated || !sensors.length}>Upload clip</button>
        </form>

        <form className="control-card ndvi-card" onSubmit={(e) => { e.preventDefault(); submitWithLocalError(() => onUploadNdviCsv(ndviForm), 'NDVI CSV processed successfully.'); }}>
          <h2>Upload NDVI CSV</h2>
          <label>Region
            <select value={ndviForm.regionId} onChange={(e) => setNdviForm({ ...ndviForm, regionId: e.target.value })}>
              <option value="">No region</option>
              {regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </label>
          <label>Loss threshold
            <input type="number" step="0.01" max="0" value={ndviForm.lossThreshold} onChange={(e) => setNdviForm({ ...ndviForm, lossThreshold: e.target.value })} />
          </label>
          <label>NDVI CSV file
            <input type="file" accept=".csv" onChange={(e) => setNdviForm({ ...ndviForm, file: e.target.files[0] })} required />
          </label>
          <button type="submit" disabled={!isAdmin || !ndviForm.file}>Upload NDVI</button>
          {ndviUploadResult && (
            <p className="fusion-result">Batch {ndviUploadResult.batch_id}: {ndviUploadResult.created_change_count} changes.</p>
          )}
        </form>

        {/* Sentinel-2 STAC Ingestion UI Card */}
        <SentinelIngestCard 
          regions={regions} 
          onIngestSentinel={onIngestSentinel} 
          isAdmin={isAdmin} 
        />

        <form className="control-card satellite-card" onSubmit={(e) => { e.preventDefault(); submitWithLocalError(() => onCreateSatelliteChange({...satelliteForm, severity_score: Number(satelliteForm.severity_score), confidence: Number(satelliteForm.confidence), latitude: Number(satelliteForm.latitude), longitude: Number(satelliteForm.longitude)}), 'Satellite change created successfully.'); }}>
          <h2>Manual satellite change</h2>
          <label>Region
            <select value={satelliteForm.region_id} onChange={(e) => setSatelliteForm({ ...satelliteForm, region_id: e.target.value })}>
              <option value="">No region</option>
              {regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </label>
          <label>Type
            <select value={satelliteForm.change_type} onChange={(e) => setSatelliteForm({ ...satelliteForm, change_type: e.target.value })}>
              {CHANGE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>Lat
            <input type="number" step="any" value={satelliteForm.latitude} onChange={(e) => setSatelliteForm({ ...satelliteForm, latitude: e.target.value })} required />
          </label>
          <label>Lon
            <input type="number" step="any" value={satelliteForm.longitude} onChange={(e) => setSatelliteForm({ ...satelliteForm, longitude: e.target.value })} required />
          </label>
          <button type="submit" disabled={!isAdmin}>Create</button>
        </form>

        <section className="control-card fusion-card">
          <h2>Fusion Engine v2</h2>
          <p className="card-help">Run spatiotemporal decay rule v2.</p>
          <label>Time Decay Half-life (days)
            <input 
              type="number" 
              step="0.1" 
              min="0.1" 
              value={fusionForm.time_decay_halflife_days} 
              onChange={(e) => setFusionForm({ ...fusionForm, time_decay_halflife_days: e.target.value })} 
            />
          </label>
          <label>Spatial Sigma (meters)
            <input 
              type="number" 
              step="1" 
              min="1" 
              value={fusionForm.spatial_sigma_meters} 
              onChange={(e) => setFusionForm({ ...fusionForm, spatial_sigma_meters: e.target.value })} 
            />
          </label>
          <button 
            type="button" 
            disabled={!isAdmin} 
            onClick={() => submitWithLocalError(() => onRunFusion({
              time_decay_halflife_days: Number(fusionForm.time_decay_halflife_days),
              spatial_sigma_meters: Number(fusionForm.spatial_sigma_meters)
            }), 'Fusion execution complete.')}
          >
            Run Fusion
          </button>
          {fusionResult && (
            <div style={{ marginTop: '12px' }} className="animate-fade-slide-up">
              <p className="fusion-result" style={{ margin: 0, fontWeight: 500 }}>
                Created {fusionResult.created_count} alert(s); matched {fusionResult.matched_count} pair(s).
              </p>
            </div>
          )}
        </section>
      </section>

      <div className="dashboard-grid">
        <aside className="sidebar ndvi-list">
          <h2>NDVI Batches</h2>
          {ndviBatches.map((batch) => (
            <article className="satellite-change-card" key={batch.id}>
              <div><span className="pill satellite">#{batch.id}</span></div>
              <p>Region: {regionName(regions, batch.region_id)} · rows {batch.row_count} · changes {batch.created_change_count}</p>
            </article>
          ))}
        </aside>
        
        <aside className="sidebar satellite-list">
          <h2>Satellite changes</h2>
          {satelliteChanges.map((change) => (
            <article className="satellite-change-card" key={change.id}>
              <div><span className="pill satellite">#{change.id}</span> <span className="pill muted">{change.change_type}</span></div>
              <p>{Number(change.latitude).toFixed(4)}, {Number(change.longitude).toFixed(4)}</p>
            </article>
          ))}
        </aside>
      </div>
    </div>
  )
}
