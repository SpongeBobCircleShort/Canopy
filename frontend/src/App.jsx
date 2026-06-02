import { Route, Routes } from 'react-router-dom'

import DashboardApp from './DashboardApp.jsx'
import LandingPage from './components/LandingPage.jsx'
import AuthPage from './components/AuthPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<AuthPage />} />
      <Route path="/app/*" element={<DashboardApp />} />
    </Routes>
  )
}
