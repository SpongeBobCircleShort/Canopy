import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'

import ToastStack from './ToastStack.jsx'

export default function Layout({ profile, onLogout, health, message, error }) {
  const location = useLocation()
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

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

      <aside className={`main-sidebar ${isSidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h1>CANOPY</h1>
          <span className="eyebrow">v0.2.0 / {health.status}</span>
        </div>
        
        <nav className="sidebar-nav">
          <Link to="/app" className={location.pathname === '/app' ? 'active' : ''} onClick={closeSidebar}>Overview</Link>
          <Link to="/app/ingestion" className={location.pathname === '/app/ingestion' ? 'active' : ''} onClick={closeSidebar}>Data Ingestion</Link>
          <Link to="/app/settings" className={location.pathname === '/app/settings' ? 'active' : ''} onClick={closeSidebar}>Configuration</Link>
        </nav>
        
        <div className="sidebar-footer">
          {profile?.organization && (
            <div className="org-info">
              <strong>{profile.organization.name}</strong>
              <span>{profile.role}</span>
            </div>
          )}
          <button className="logout-btn" onClick={onLogout}>Log Out</button>
        </div>
      </aside>
      
      <main className="layout-content">
        <ToastStack
          toasts={[
            error ? { id: `layout-error-${error}`, type: 'error', message: error } : null,
            message ? { id: `layout-message-${message}`, type: 'success', message } : null,
          ].filter(Boolean)}
        />
        <Outlet />
      </main>
    </div>
  )
}
