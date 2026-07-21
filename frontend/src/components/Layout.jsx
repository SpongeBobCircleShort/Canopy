import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'

import ToastStack from './ToastStack.jsx'

const PAGE_TITLES = {
  '/app': 'Overview',
  '/app/forest-loss': 'Forest Loss',
  '/app/ingestion': 'Data Ingestion',
  '/app/clips': 'Clips Review',
  '/app/settings': 'Configuration',
}

const PRIMARY_LINKS = [
  ['/app', 'Overview'],
  ['/app/forest-loss', 'Forest Loss'],
]

const MENU_LINKS = [
  ['/app/ingestion', 'Data Ingestion'],
  ['/app/clips', 'Clips Review'],
  ['/app/settings', 'Configuration'],
]

export default function Layout({ profile, onLogout, health, message, error, isDemoMode = false }) {
  const location = useLocation()
  const [isMenuOpen, setIsMenuOpen] = useState(false)

  useEffect(() => {
    const page = PAGE_TITLES[location.pathname]
    document.title = page ? `Canopy · ${page}` : 'Canopy'
  }, [location.pathname])

  useEffect(() => {
    function onKey(event) {
      if (event.key === 'Escape') setIsMenuOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  function closeMenu() {
    setIsMenuOpen(false)
  }

  const healthClass = isDemoMode ? 'demo' : (health.status === 'ok' || health.status === 'healthy') ? 'ok' : 'error'

  return (
    <div className="layout-container">
      <header className="top-bar">
        <div className="top-bar-left">
          <button
            className="menu-toggle"
            type="button"
            aria-label={isMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={isMenuOpen}
            onClick={() => setIsMenuOpen((current) => !current)}
          >
            <span />
            <span />
            <span />
          </button>
          <a href="/" className="sidebar-wordmark" aria-label="Back to landing page">CANOPY</a>
        </div>

        <nav className="top-nav-pills" aria-label="Primary">
          {PRIMARY_LINKS.map(([to, label]) => (
            <Link key={to} to={to} className={location.pathname === to ? 'active' : ''} onClick={closeMenu}>
              {label}
            </Link>
          ))}
        </nav>

        <div className="top-bar-right">
          <span className={`health-dot ${healthClass}`} />
          <span>v0.2.0 / {isDemoMode ? 'DEMO' : (health.status || '').toUpperCase()}</span>
        </div>

        {isMenuOpen && (
          <nav className="menu-panel" aria-label="More pages">
            {MENU_LINKS.map(([to, label]) => (
              <Link key={to} to={to} className={location.pathname === to ? 'active' : ''} onClick={closeMenu}>
                {label}
              </Link>
            ))}
            <hr className="menu-rule" />
            {profile?.organization && (
              <div className="org-info">
                <strong>{profile.organization.name}</strong>
                <span>{profile.role}</span>
              </div>
            )}
            <button className="logout-btn" onClick={() => { closeMenu(); onLogout() }}>
              {isDemoMode ? 'Reset Demo' : 'Log Out'}
            </button>
          </nav>
        )}
      </header>
      {isMenuOpen && <button className="menu-scrim" type="button" aria-label="Close navigation menu" onClick={closeMenu} />}

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
            <a href="/">Landing</a>
            <a href="/deck.html">View presentation</a>
          </nav>
        </footer>
      </main>
    </div>
  )
}
