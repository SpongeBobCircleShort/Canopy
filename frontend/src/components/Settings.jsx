import { useState } from 'react'

import ToastStack from './ToastStack.jsx'

export default function Settings({
  regions,
  invites,
  isAdmin,
  onCreateInvite,
  onRevokeInvite,
  onCreateRegion,
  onCreateSensor
}) {
  const [inviteForm, setInviteForm] = useState({ email: '', role: 'member' })
  const [regionForm, setRegionForm] = useState({ name: '', description: '', boundary: '' })
  const [sensorForm, setSensorForm] = useState({ name: '', device_type: 'forest-listening-unit', region_id: '', lat: '', lon: '' })
  
  const [localError, setLocalError] = useState('')

  async function submitWithLocalError(action) {
    setLocalError('')
    try { await action() } catch (err) { setLocalError(err.message) }
  }

  return (
    <div className="page-content">
      <header className="page-header">
        <h2>Configuration & Settings</h2>
      </header>
      
      <ToastStack toasts={localError ? [{ id: `settings-error-${localError}`, type: 'error', message: localError }] : []} />

      <section className="workflow-grid">
        <form className="control-card" onSubmit={(e) => { e.preventDefault(); submitWithLocalError(() => onCreateInvite(inviteForm)); }}>
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
                <article key={invite.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, fontSize: '0.85rem' }}>
                  <span><strong>{invite.email}</strong> ({invite.status})</span>
                  {invite.status === 'pending' && (
                    <button type="button" style={{ width: 'auto', padding: '4px 8px', fontSize: '0.7rem' }} onClick={() => submitWithLocalError(() => onRevokeInvite(invite.id))}>Revoke</button>
                  )}
                </article>
              ))}
            </div>
          )}
        </form>

        <form className="control-card" onSubmit={(e) => { e.preventDefault(); submitWithLocalError(() => onCreateRegion(regionForm)); }}>
          <h2>Create region</h2>
          <label>Name
            <input value={regionForm.name} onChange={(e) => setRegionForm({ ...regionForm, name: e.target.value })} required />
          </label>
          <button type="submit" disabled={!isAdmin}>Create region</button>
        </form>

        <form className="control-card" onSubmit={(e) => { e.preventDefault(); submitWithLocalError(() => onCreateSensor({...sensorForm, region_id: sensorForm.region_id ? Number(sensorForm.region_id) : null, location: { lat: Number(sensorForm.lat), lon: Number(sensorForm.lon) }})); }}>
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
      </section>
    </div>
  )
}
