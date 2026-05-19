import { useState } from 'react'

import ToastStack from './ToastStack.jsx'

export default function LoginPage({ onAuth, error, message }) {
  const [authMode, setAuthMode] = useState('login')
  const [authForm, setAuthForm] = useState({ name: '', email: '', password: '', organization_name: '', invite_token: '' })
  const [localError, setLocalError] = useState('')

  async function handleAuthSubmit(event) {
    event.preventDefault()
    setLocalError('')
    try {
      await onAuth(authMode, authForm)
    } catch (err) {
      setLocalError(err.message)
    }
  }

  return (
    <div className="login-page">
      <div className="login-container">
        <h1>CANOPY</h1>
        <p className="eyebrow">Open-source forest monitoring</p>
        
        <form className="control-card login-card" onSubmit={handleAuthSubmit}>
          <h2>{authMode === 'signup' ? 'Create an Account' : 'Authenticate'}</h2>
          
          <div className="auth-toggle">
            <button 
              type="button" 
              className={authMode === 'login' ? 'active' : ''} 
              onClick={() => setAuthMode('login')}
            >
              Login
            </button>
            <button 
              type="button" 
              className={authMode === 'signup' ? 'active' : ''} 
              onClick={() => setAuthMode('signup')}
            >
              Signup
            </button>
          </div>

          {authMode === 'signup' && (
            <>
              <label>
                Name
                <input value={authForm.name} onChange={(e) => setAuthForm({ ...authForm, name: e.target.value })} required />
              </label>
              <label>
                Invite token (Optional)
                <input
                  value={authForm.invite_token}
                  onChange={(e) => setAuthForm({ ...authForm, invite_token: e.target.value, organization_name: e.target.value ? '' : authForm.organization_name })}
                  placeholder="Paste token to join org"
                />
              </label>
              {!authForm.invite_token && (
                <label>
                  Organization name
                  <input
                    value={authForm.organization_name}
                    onChange={(e) => setAuthForm({ ...authForm, organization_name: e.target.value })}
                    placeholder="Demo Conservation Team"
                    required
                  />
                </label>
              )}
            </>
          )}
          
          <label>
            Email
            <input
              type="email"
              value={authForm.email}
              onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={authForm.password}
              onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
              required
            />
          </label>
          
          <button type="submit" className="submit-auth-btn">
            {authMode === 'signup' ? 'Sign up' : 'Log in'}
          </button>
        </form>
        
        <ToastStack
          toasts={[
            localError ? { id: `login-local-${localError}`, type: 'error', message: localError } : null,
            error ? { id: `login-error-${error}`, type: 'error', message: error } : null,
            message ? { id: `login-message-${message}`, type: 'success', message } : null,
          ].filter(Boolean)}
        />
      </div>
    </div>
  )
}
