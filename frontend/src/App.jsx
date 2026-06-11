import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import DashboardApp from './DashboardApp.jsx'
import AuthPage from './components/AuthPage.jsx'

function LegacyAppRedirect() {
  const location = useLocation()
  const target = location.pathname.replace(/^\/app/, '') || '/'
  return <Navigate to={`${target}${location.search}`} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route path="/app/*" element={<LegacyAppRedirect />} />
      <Route path="/*" element={<DashboardApp />} />
    </Routes>
  )
}
