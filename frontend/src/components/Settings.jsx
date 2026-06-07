import { useState } from 'react'

import ToastStack from './ToastStack.jsx'

export default function Settings({
  regions,
  invites,
  isAdmin,
  webhooks,
  emails,
  fusionSchedule,
  onCreateInvite,
  onRevokeInvite,
  onCreateRegion,
  onCreateSensor,
  onSaveWebhooks,
  onSaveEmails,
}) {
  const [inviteForm, setInviteForm] = useState({ email: '', role: 'member' })
  const [regionForm, setRegionForm] = useState({ name: '', description: '', boundary: '' })
  const [sensorForm, setSensorForm] = useState({ name: '', device_type: 'forest-listening-unit', region_id: '', lat: '', lon: '' })
  const [webhookInput, setWebhookInput] = useState(webhooks?.join('\n') ?? '')
  const [emailInput, setEmailInput] = useState(emails?.join('\n') ?? '')

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

  const handleSensorSubmit = (e) => {
    e.preventDefault()
    setLocalError('')
    setLocalSuccess('')
    
    const latNum = Number(sensorForm.lat)
    const lonNum = Number(sensorForm.lon)
    
    if (isNaN(latNum) || latNum < -90 || latNum > 90) {
      setLocalError('Latitude must be a valid number between -90 and 90.')
      return
    }
    if (isNaN(lonNum) || lonNum < -180 || lonNum > 180) {
      setLocalError('Longitude must be a valid number between -180 and 180.')
      return
    }
    
    submitWithLocalError(
      () => onCreateSensor({
        ...sensorForm,
        region_id: sensorForm.region_id ? Number(sensorForm.region_id) : null,
        location: { lat: latNum, lon: lonNum }
      }),
      'Sensor created successfully.'
    )
  }

  return (
    <div className="page-content">
      <header className="page-header">
        <h2>Configuration & Settings</h2>
      </header>
      
      <ToastStack 
        toasts={[
          localError ? { id: `settings-error-${localError}`, type: 'error', message: localError } : null,
          localSuccess ? { id: `settings-success-${localSuccess}`, type: 'success', message: localSuccess } : null,
        ].filter(Boolean)} 
      />

      <section className="workflow-grid">
        <form className="control-card glass-card" onSubmit={(e) => { e.preventDefault(); submitWithLocalError(() => onCreateInvite(inviteForm), 'Invite sent successfully.'); }}>
          <h2>Invite member</h2>
          <label>Email
            <input type="email" value={inviteForm.email} onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })} required />
          </label>
          <label>Role
            <select value={inviteForm.role} onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })}>
              <option value="member">member</option>
            </select>
          </label>
          <button type="submit" disabled={!isAdmin}>Create invite</button>
          {isAdmin && invites?.length > 0 && (
            <div className="invite-list" style={{ marginTop: 16 }}>
              {invites.map((invite) => (
                <article key={invite.id} style={{ display: 'flex', justifycontent: 'space-between', alignItems: 'center', marginBottom: 8, fontSize: '0.85rem' }}>
                  <span><strong>{invite.email}</strong> ({invite.status})</span>
                  {invite.status === 'pending' && (
                    <button type="button" style={{ width: 'auto', padding: '4px 8px', fontSize: '0.7rem' }} onClick={() => submitWithLocalError(() => onRevokeInvite(invite.id), 'Invite revoked.')}>Revoke</button>
                  )}
                </article>
              ))}
            </div>
          )}
        </form>

        <form className="control-card glass-card" onSubmit={(e) => { e.preventDefault(); submitWithLocalError(() => onCreateRegion(regionForm), 'Region created successfully.'); }}>
          <h2>Create region</h2>
          <label>Name
            <input value={regionForm.name} onChange={(e) => setRegionForm({ ...regionForm, name: e.target.value })} required />
          </label>
          <button type="submit" disabled={!isAdmin}>Create region</button>
        </form>

        <form className="control-card glass-card" onSubmit={handleSensorSubmit}>
          <h2>Create sensor</h2>
          <label>Name
            <input value={sensorForm.name} onChange={(e) => setSensorForm({ ...sensorForm, name: e.target.value })} required />
          </label>
          <label>Region
            <select value={sensorForm.region_id} onChange={(e) => setSensorForm({ ...sensorForm, region_id: e.target.value })}>
              <option value="">No region</option>
              {regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </label>
          <label>Latitude
            <input type="number" step="any" value={sensorForm.lat} onChange={(e) => setSensorForm({ ...sensorForm, lat: e.target.value })} required />
          </label>
          <label>Longitude
            <input type="number" step="any" value={sensorForm.lon} onChange={(e) => setSensorForm({ ...sensorForm, lon: e.target.value })} required />
          </label>
          <button type="submit" disabled={!isAdmin}>Create sensor</button>
        </form>

        <form
          className="control-card glass-card"
          onSubmit={(e) => {
            e.preventDefault()
            const urls = webhookInput.split('\n').map((u) => u.trim()).filter(Boolean)
            submitWithLocalError(() => onSaveWebhooks(urls), 'Webhook settings saved.')
          }}
        >
          <h2>Alert webhooks</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 8 }}>
            Canopy will POST high/critical alerts to each URL (one per line). Slack incoming webhooks and custom endpoints are both supported.
          </p>
          <label>
            Webhook URLs
            <textarea
              rows={4}
              placeholder={'https://hooks.slack.com/services/...\nhttps://your-server.example/canopy-alerts'}
              value={webhookInput}
              onChange={(e) => setWebhookInput(e.target.value)}
              disabled={!isAdmin}
              style={{ fontFamily: 'monospace', fontSize: '0.8rem', resize: 'vertical' }}
            />
          </label>
          <button type="submit" disabled={!isAdmin}>Save webhooks</button>
        </form>

        <form
          className="control-card glass-card"
          onSubmit={(e) => {
            e.preventDefault()
            const addrs = emailInput.split('\n').map((a) => a.trim()).filter(Boolean)
            submitWithLocalError(() => onSaveEmails(addrs), 'Email recipients saved.')
          }}
        >
          <h2>Email notifications</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 8 }}>
            Canopy will email high/critical alerts to each address (one per line). Requires SMTP to be configured on the server.
          </p>
          <label>
            Recipients
            <textarea
              rows={4}
              placeholder={'ranger1@example.org\nops-team@example.org'}
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              disabled={!isAdmin}
              style={{ fontFamily: 'monospace', fontSize: '0.8rem', resize: 'vertical' }}
            />
          </label>
          <button type="submit" disabled={!isAdmin}>Save recipients</button>
        </form>

        <div className="control-card glass-card">
          <h2>Auto-fusion schedule</h2>
          {fusionSchedule ? (
            <>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <span className={`pill ${fusionSchedule.enabled ? 'high' : 'muted'}`}>
                  {fusionSchedule.enabled ? `Every ${fusionSchedule.interval_minutes} min` : 'Disabled'}
                </span>
              </div>
              {fusionSchedule.last_run_at ? (
                <p style={{ fontSize: '0.78rem', color: '#888' }}>
                  Last run: {new Date(fusionSchedule.last_run_at).toLocaleString()} · {fusionSchedule.last_run_orgs} org(s) · {fusionSchedule.last_run_created} alert(s) created
                </p>
              ) : (
                <p style={{ fontSize: '0.78rem', color: '#666' }}>No run yet this session.</p>
              )}
            </>
          ) : (
            <p style={{ fontSize: '0.78rem', color: '#666' }}>Not connected to API.</p>
          )}
          <p style={{ fontSize: '0.75rem', color: '#555', marginTop: 10 }}>
            Set <code>FUSION_AUTO_INTERVAL_MINUTES</code> in the API environment to enable automatic fusion runs. Set to <code>0</code> to disable.
          </p>
        </div>
      </section>
    </div>
  )
}
