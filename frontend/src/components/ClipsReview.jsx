import { useState } from 'react'
import ToastStack from './ToastStack.jsx'

const LABEL_PRESETS = ['chainsaw', 'gunshot', 'vehicle', 'fire_crackle', 'background_unknown', 'other']

function formatPct(v) {
  return v === undefined || v === null ? 'n/a' : `${Math.round(Number(v) * 100)}%`
}

function basename(url) {
  return url?.split('/').pop() || url || '—'
}

function ClipCard({ clip, sensors, onAddLabel }) {
  const [labelInput, setLabelInput] = useState('')
  const [labels, setLabels] = useState(null)
  const [expanded, setExpanded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const sensor = sensors.find((s) => s.id === clip.sensor_id)

  async function handleExpand() {
    if (!expanded && labels === null) {
      setLoading(true)
      try {
        const fetched = await onAddLabel(clip.id, null)
        setLabels(fetched)
      } catch {
        setLabels([])
      } finally {
        setLoading(false)
      }
    }
    setExpanded((v) => !v)
  }

  async function handleSubmit(label) {
    if (!label.trim()) return
    setError('')
    setLoading(true)
    try {
      const newLabel = await onAddLabel(clip.id, { label: label.trim() })
      setLabels((prev) => [newLabel, ...(prev || [])])
      setLabelInput('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <article className="glass-card" style={{ marginBottom: 12, padding: '14px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
            {clip.classifier_label && (
              <span className="pill medium" style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem' }}>
                {clip.classifier_label}
              </span>
            )}
            <span className="pill muted" style={{ fontSize: '0.68rem' }}>
              {formatPct(clip.classifier_confidence)}
            </span>
            {clip.classifier_model_version && (
              <span className="pill status" style={{ fontSize: '0.68rem' }}>
                {clip.classifier_model_version}
              </span>
            )}
          </div>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: '#888', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {basename(clip.file_url)}
          </p>
          <p style={{ fontSize: '0.7rem', color: '#666', margin: '4px 0 0' }}>
            Sensor: {sensor?.name ?? (clip.sensor_id ? `#${clip.sensor_id}` : '—')} · {new Date(clip.created_at).toLocaleString()}
          </p>
        </div>
        <button
          className="export-button"
          style={{ padding: '4px 10px', fontSize: '0.72rem', whiteSpace: 'nowrap' }}
          onClick={handleExpand}
          type="button"
        >
          {expanded ? 'Hide' : 'Review'}
        </button>
      </div>

      {expanded && (
        <div style={{ marginTop: 14, borderTop: '1px solid rgba(255,255,255,0.07)', paddingTop: 12 }}>
          {error && <p style={{ color: 'var(--priority-high)', fontSize: '0.78rem', marginBottom: 8 }}>{error}</p>}

          <div style={{ marginBottom: 12 }}>
            <p style={{ fontSize: '0.72rem', color: '#888', margin: '0 0 8px', fontFamily: 'var(--font-label)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Quick label</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {LABEL_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => handleSubmit(preset)}
                  disabled={loading}
                  className="export-button"
                  style={{ padding: '3px 8px', fontSize: '0.7rem', opacity: loading ? 0.5 : 1 }}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <input
              value={labelInput}
              onChange={(e) => setLabelInput(e.target.value)}
              placeholder="Custom label..."
              style={{ flex: 1, fontSize: '0.78rem' }}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSubmit(labelInput) } }}
            />
            <button type="button" onClick={() => handleSubmit(labelInput)} disabled={loading || !labelInput.trim()} className="export-button">
              Submit
            </button>
          </div>

          {loading && !labels && <p style={{ fontSize: '0.72rem', color: '#666' }}>Loading labels…</p>}
          {labels !== null && labels.length === 0 && (
            <p style={{ fontSize: '0.72rem', color: '#666' }}>No human labels yet.</p>
          )}
          {labels && labels.length > 0 && (
            <div>
              <p style={{ fontSize: '0.72rem', color: '#888', fontFamily: 'var(--font-label)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Human labels</p>
              {labels.map((lbl) => (
                <div key={lbl.id} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4, fontSize: '0.75rem' }}>
                  <span className="pill status" style={{ fontSize: '0.68rem' }}>{lbl.label}</span>
                  {lbl.confidence != null && <span style={{ color: '#888' }}>{formatPct(lbl.confidence)}</span>}
                  <span style={{ color: '#555', marginLeft: 'auto' }}>{new Date(lbl.labeled_at).toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </article>
  )
}

export default function ClipsReview({ clips, sensors, onFetchLabels, onAddLabel, onExportLabels, isAdmin }) {
  const [localError, setLocalError] = useState('')
  const [localSuccess, setLocalSuccess] = useState('')
  const [exporting, setExporting] = useState(false)

  async function handleClipAction(clipId, payload) {
    if (payload === null) {
      return onFetchLabels(clipId)
    }
    const result = await onAddLabel(clipId, payload)
    setLocalSuccess(`Label '${payload.label}' added.`)
    return result
  }

  async function handleExport() {
    if (!onExportLabels) return
    setExporting(true)
    try {
      await onExportLabels()
    } catch (err) {
      setLocalError(err.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="page-content">
      <header className="page-header">
        <div>
          <p className="page-kicker">[ SIGNAL VERIFICATION ]</p>
          <h2>Clips Review</h2>
        </div>
        {isAdmin && (
          <button className="export-button" onClick={handleExport} disabled={exporting} type="button">
            {exporting ? 'Exporting…' : 'Export CSV'}
          </button>
        )}
      </header>

      <ToastStack
        toasts={[
          localError ? { id: `clips-error-${localError}`, type: 'error', message: localError } : null,
          localSuccess ? { id: `clips-success-${localSuccess}`, type: 'success', message: localSuccess } : null,
        ].filter(Boolean)}
      />

      <section className="workflow-grid" style={{ gridTemplateColumns: '1fr' }}>
        <div className="control-card glass-card">
          <h2>Audio clips ({clips.length})</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 16 }}>
            Review classifier predictions and add human labels to improve model accuracy. Labels are stored per clip and exported with alerts.
          </p>
          {clips.length === 0 && (
            <p style={{ color: '#666', fontSize: '0.85rem' }}>No clips yet. Upload audio on the Data Ingestion page to get started.</p>
          )}
          {clips.map((clip) => (
            <ClipCard
              key={clip.id}
              clip={clip}
              sensors={sensors}
              onAddLabel={handleClipAction}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
