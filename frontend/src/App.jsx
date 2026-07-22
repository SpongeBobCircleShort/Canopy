import { Navigate, Route, Routes } from 'react-router-dom'

import DashboardApp from './DashboardApp.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/app/*" element={<DashboardApp />} />
      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  )
}
