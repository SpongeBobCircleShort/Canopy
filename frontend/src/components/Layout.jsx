import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'

import ToastStack from './ToastStack.jsx'

const PAGE_TITLES = {
  '/': 'Overview',
  '/forest-loss': 'Forest Loss',
  '/ingestion': 'Data Ingestion',
  '/clips': 'Clips Review',
  '/settings': 'Configuration',
}

export default function Layout({ profile, onLogout, health, message, error, isDemoMode = false }) {
  const location = useLocation()
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  useEffect(() => {
    const page = PAGE_TITLES[location.pathname]
    document.title = page ? `Canopy · ${page}` : 'Canopy'
  }, [location.pathname])

  function closeSidebar() {
    setIsSidebarOpen(false)
  }

  return (
    <div className="layout-container">
      <button
        className="sidebar-toggle"
        type="button"
        aria-label={isSidebarOpen ? 'Close navigation menu' : 'Open navigation menu'}
        aria-expanded={isSidebarOpen}
        onClick={() => setIsSidebarOpen((current) => !current)}
      >
        <span />
        <span />
        <span />
      </button>
      {isSidebarOpen && <button className="sidebar-scrim" type="button" aria-label="Close navigation menu" onClick={closeSidebar} />}

      <aside className={`main-sidebar glass-sidebar ${isSidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-wordmark">CANOPY</div>
          <div className="sidebar-version">
            <span className={`health-dot ${isDemoMode ? 'demo' : (health.status === 'ok' || health.status === 'healthy') ? 'ok' : 'error'}`} />
            v0.2.0 / {isDemoMode ? 'DEMO' : (health.status || '').toUpperCase()}
          </div>
        </div>
        <hr className="sidebar-header-rule" />

        <nav className="sidebar-nav">
          <Link to="/" className={location.pathname === '/' ? 'active' : ''} onClick={closeSidebar}>Overview</Link>
          <Link to="/forest-loss" className={location.pathname === '/forest-loss' ? 'active' : ''} onClick={closeSidebar}>Forest Loss</Link>
          <Link to="/ingestion" className={location.pathname === '/ingestion' ? 'active' : ''} onClick={closeSidebar}>Data Ingestion</Link>
          <Link to="/clips" className={location.pathname === '/clips' ? 'active' : ''} onClick={closeSidebar}>Clips Review</Link>
          <Link to="/settings" className={location.pathname === '/settings' ? 'active' : ''} onClick={closeSidebar}>Configuration</Link>
        </nav>

        <div className="sidebar-footer">
          {profile?.organization && (
            <div className="org-info">
              <strong>{profile.organization.name}</strong>
              <span>{profile.role}</span>
            </div>
          )}
          <button className="logout-btn" onClick={onLogout}>{isDemoMode ? 'Reset Demo' : 'Log Out'}</button>
        </div>
      </aside>

      <main className="layout-content">
        <ToastStack
          toasts={[
            error ? { id: `layout-error-${error}`, type: 'error', message: error } : null,
            message ? { id: `layout-message-${message}`, type: 'success', message } : null,
          ].filter(Boolean)}
        />
        <div className="layout-page">
          <Outlet />
        </div>
        <footer className="layout-footer">
          <span>Arjun Tyagi · Penn State · Open source · Institutional overview for geospatial data pilot</span>
          <nav className="layout-footer-links">
            <a href="/deck.html">View presentation</a>
          </nav>
        </footer>
      </main>
    </div>
  )
}
