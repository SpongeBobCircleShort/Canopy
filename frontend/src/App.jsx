import { BrowserRouter, Route, Routes } from 'react-router-dom'

import DashboardApp from './DashboardApp.jsx'
import LandingPage from './components/LandingPage.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app/*" element={<DashboardApp />} />
      </Routes>
    </BrowserRouter>
  )
}
