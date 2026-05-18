import { Link, Outlet, useLocation } from 'react-router-dom'

export default function Layout({ profile, onLogout, health }) {
  const location = useLocation()
  
  return (
    <div className="layout-container">
      <aside className="main-sidebar">
        <div className="sidebar-header">
          <h1>CANOPY</h1>
          <span className="eyebrow">v0.2.0 / {health.status}</span>
        </div>
        
        <nav className="sidebar-nav">
          <Link to="/" className={location.pathname === '/' ? 'active' : ''}>Overview</Link>
          <Link to="/ingestion" className={location.pathname === '/ingestion' ? 'active' : ''}>Data Ingestion</Link>
          <Link to="/settings" className={location.pathname === '/settings' ? 'active' : ''}>Configuration</Link>
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
        <Outlet />
      </main>
    </div>
  )
}
