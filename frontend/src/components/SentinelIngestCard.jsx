import { useState } from 'react'

export default function SentinelIngestCard({ regions, onIngestSentinel, isAdmin }) {
  const [regionId, setRegionId] = useState('')
  const [bbox, setBbox] = useState({
    minLon: '78.95',
    minLat: '20.58',
    maxLon: '78.97',
    maxLat: '20.60',
  })
  
  // Default date ranges in ISO format (YYYY-MM-DD)
  const [baselineStart, setBaselineStart] = useState('2026-01-01')
  const [baselineEnd, setBaselineEnd] = useState('2026-03-01')
  const [observationStart, setObservationStart] = useState('2026-03-02')
  const [observationEnd, setObservationEnd] = useState('2026-06-01')
  
  const [maxCloudCover, setMaxCloudCover] = useState(10.0)
  const [lossThreshold, setLossThreshold] = useState(-0.10)
  const [gridResolution, setGridResolution] = useState(10)
  
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  // Pre-configured bounding boxes for regional presets
  const presets = {
    '': { minLon: '78.95', minLat: '20.58', maxLon: '78.97', maxLat: '20.60' }, // Default
    'western-ghats': { minLon: '73.80', minLat: '15.40', maxLon: '73.90', maxLat: '15.50' },
    'sunderbans': { minLon: '88.70', minLat: '21.80', maxLon: '88.90', maxLat: '22.00' },
  }

  function handlePresetChange(e) {
    const presetVal = e.target.value
    if (presets[presetVal]) {
      setBbox(presets[presetVal])
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    
    const minLonNum = Number(bbox.minLon)
    const minLatNum = Number(bbox.minLat)
    const maxLonNum = Number(bbox.maxLon)
    const maxLatNum = Number(bbox.maxLat)
    
    if (isNaN(minLonNum) || minLonNum < -180 || minLonNum > 180 ||
        isNaN(maxLonNum) || maxLonNum < -180 || maxLonNum > 180 ||
        isNaN(minLatNum) || minLatNum < -90 || minLatNum > 90 ||
        isNaN(maxLatNum) || maxLatNum < -90 || maxLatNum > 90) {
      setError('Bounding box coordinates must be valid longitude (-180 to 180) and latitude (-90 to 90).')
      return
    }
    
    if (minLonNum >= maxLonNum || minLatNum >= maxLatNum) {
      setError('Min coordinates must be less than max coordinates.')
      return
    }

    if (!baselineStart || !baselineEnd || !observationStart || !observationEnd) {
      setError('All date ranges are required.')
      return
    }

    setLoading(true)
    try {
      const payload = {
        region_id: regionId ? Number(regionId) : null,
        bbox: [minLonNum, minLatNum, maxLonNum, maxLatNum],
        baseline_start: new Date(baselineStart).toISOString(),
        baseline_end: new Date(baselineEnd).toISOString(),
        observation_start: new Date(observationStart).toISOString(),
        observation_end: new Date(observationEnd).toISOString(),
        max_cloud_cover: Number(maxCloudCover),
        loss_threshold: Number(lossThreshold),
        grid_resolution: Number(gridResolution),
      }
      
      const res = await onIngestSentinel(payload)
      setResult(res)
    } catch (err) {
      setError(err.message || 'Sentinel Ingestion failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="control-card glass-card sentinel-card" onSubmit={handleSubmit} style={{ gridColumn: 'span 2' }}>
      <h2>Sentinel-2 STAC Ingest</h2>
      <p className="card-help">
        Trigger a live query against Sentinel-2 STAC records, calculate NDVI values, and detect canopy loss cells.
      </p>
      
      <div className="sentinel-grid-inputs">
        <label>Region Preset
          <select onChange={handlePresetChange}>
            <option value="">Custom Coordinates</option>
            <option value="western-ghats">Western Ghats Preserve</option>
            <option value="sunderbans">Sunderbans Tiger Reserve</option>
          </select>
        </label>
        
        <label>Target Region ID (Optional)
          <select value={regionId} onChange={(e) => setRegionId(e.target.value)}>
            <option value="">No region assignment</option>
            {regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </label>
      </div>

      <div style={{ marginTop: '12px' }}>
        <label style={{ margin: '0 0 6px' }}>Bounding Box [min_lon, min_lat, max_lon, max_lat]</label>
        <div className="sentinel-bbox-grid">
          <input 
            type="number" 
            step="0.0001" 
            placeholder="Min Lon" 
            value={bbox.minLon} 
            onChange={(e) => setBbox({ ...bbox, minLon: e.target.value })} 
            required 
          />
          <input 
            type="number" 
            step="0.0001" 
            placeholder="Min Lat" 
            value={bbox.minLat} 
            onChange={(e) => setBbox({ ...bbox, minLat: e.target.value })} 
            required 
          />
          <input 
            type="number" 
            step="0.0001" 
            placeholder="Max Lon" 
            value={bbox.maxLon} 
            onChange={(e) => setBbox({ ...bbox, maxLon: e.target.value })} 
            required 
          />
          <input 
            type="number" 
            step="0.0001" 
            placeholder="Max Lat" 
            value={bbox.maxLat} 
            onChange={(e) => setBbox({ ...bbox, maxLat: e.target.value })} 
            required 
          />
        </div>
      </div>

      <div className="sentinel-grid-inputs" style={{ marginTop: '12px' }}>
        <label>Baseline Start
          <input type="date" value={baselineStart} onChange={(e) => setBaselineStart(e.target.value)} required />
        </label>
        <label>Baseline End
          <input type="date" value={baselineEnd} onChange={(e) => setBaselineEnd(e.target.value)} required />
        </label>
      </div>

      <div className="sentinel-grid-inputs" style={{ marginTop: '12px' }}>
        <label>Observation Start
          <input type="date" value={observationStart} onChange={(e) => setObservationStart(e.target.value)} required />
        </label>
        <label>Observation End
          <input type="date" value={observationEnd} onChange={(e) => setObservationEnd(e.target.value)} required />
        </label>
      </div>

      <div className="sentinel-grid-inputs" style={{ marginTop: '12px' }}>
        <label>Grid Resolution ({gridResolution}x{gridResolution})
          <input 
            type="range" 
            min="2" 
            max="30" 
            value={gridResolution} 
            onChange={(e) => setGridResolution(Number(e.target.value))} 
          />
        </label>
        <label>Cloud Cover Max ({maxCloudCover}%)
          <input 
            type="range" 
            min="0" 
            max="100" 
            value={maxCloudCover} 
            onChange={(e) => setMaxCloudCover(Number(e.target.value))} 
          />
        </label>
      </div>

      <div className="sentinel-grid-inputs" style={{ marginTop: '12px' }}>
        <label>Loss Threshold ({lossThreshold})
          <input 
            type="range" 
            min="-0.50" 
            max="-0.01" 
            step="0.01" 
            value={lossThreshold} 
            onChange={(e) => setLossThreshold(Number(e.target.value))} 
          />
        </label>
      </div>

      <div style={{ marginTop: '16px' }}>
        <button type="submit" disabled={!isAdmin || loading}>
          {loading ? 'Ingesting Scenes...' : 'Trigger Sentinel Ingestion'}
        </button>
      </div>

      {error && (
        <div style={{ marginTop: '12px', padding: '10px', background: 'rgba(192, 57, 43, 0.15)', border: '1px solid rgba(192, 57, 43, 0.3)', borderRadius: '6px', color: '#ef8f85', fontSize: '0.8rem' }} className="animate-fade-slide-up">
          {error}
        </div>
      )}

      {result && (
        <div style={{ marginTop: '12px', padding: '12px', background: 'rgba(74, 124, 89, 0.15)', border: '1px solid rgba(74, 124, 89, 0.3)', borderRadius: '6px', fontSize: '0.82rem' }} className="animate-fade-slide-up">
          <h4 style={{ margin: '0 0 8px', color: '#FFFFFF' }}>Ingestion Complete</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', color: 'var(--db-text-2)' }}>
            <div>Baseline scenes: <strong>{result.baseline_scene_count}</strong></div>
            <div>Observation scenes: <strong>{result.observation_scene_count}</strong></div>
            <div>Cells evaluated: <strong>{result.grid_cells_evaluated}</strong></div>
            <div>Changes created: <strong style={{ color: '#2ecc71' }}>{result.created_change_count}</strong></div>
            <div>Changes skipped: <strong>{result.skipped_count}</strong></div>
          </div>
        </div>
      )}
    </form>
  )
}
