import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import '../auth.css'

export default function AuthPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  function handleLogin(e) {
    e.preventDefault()
    // Mock login that forwards to dashboard
    navigate('/')
  }

  return (
    <div className="auth-page">
      <div className="auth-left">
        <div className="texture-grain"></div>
        <div className="auth-left-content">
          <div className="auth-brand">
            <span className="text-label" style={{ color: 'var(--moss)' }}>CANOPY</span>
          </div>
          <div className="auth-hero">
            <h1 className="text-display-lg" style={{ color: 'var(--white)', marginBottom: '16px' }}>
              Get Started <em>with Canopy</em>
            </h1>
            <p className="text-body" style={{ color: 'rgba(255,255,255,0.6)', maxWidth: '40ch' }}>
              Join the open source forest monitoring platform fusing acoustic intelligence with geospatial data.
            </p>
          </div>
          
          <div className="auth-steps">
            <div className="auth-step-card">
              <span className="step-num text-label">01</span>
              <span>Connect sensors</span>
            </div>
            <div className="auth-step-card">
              <span className="step-num text-label">02</span>
              <span>Upload NDVI</span>
            </div>
            <div className="auth-step-card">
              <span className="step-num text-label">03</span>
              <span>Review fused alerts</span>
            </div>
          </div>
        </div>
      </div>
      
      <div className="auth-right">
        <div className="auth-form-container">
          <h2 className="text-heading" style={{ color: 'var(--white)', marginBottom: '32px' }}>Sign In</h2>
          
          <div className="oauth-buttons">
            <button type="button" className="oauth-btn" onClick={handleLogin}>
              Continue with Google
            </button>
            <button type="button" className="oauth-btn" onClick={handleLogin}>
              Continue with GitHub
            </button>
          </div>
          
          <div className="auth-divider">
            <span className="text-label" style={{ color: 'var(--gray-400)' }}>or use email</span>
          </div>
          
          <form className="auth-form" onSubmit={handleLogin}>
            <label className="auth-label">
              Email Address
              <input 
                type="email" 
                className="auth-input" 
                placeholder="forester@example.com" 
                value={email}
                onChange={e => setEmail(e.target.value)}
                required 
              />
            </label>
            <label className="auth-label">
              Password
              <input 
                type="password" 
                className="auth-input" 
                placeholder="••••••••" 
                value={password}
                onChange={e => setPassword(e.target.value)}
                required 
              />
            </label>
            <button type="submit" className="auth-submit">Sign In</button>
          </form>
        </div>
      </div>
    </div>
  )
}
