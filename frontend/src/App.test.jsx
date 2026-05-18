import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.jsx'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }) => <div data-testid="map">{children}</div>,
  TileLayer: () => <div />,
  CircleMarker: ({ children }) => <div>{children}</div>,
  Popup: ({ children }) => <div>{children}</div>,
  useMapEvents: () => ({
    getZoom: () => 6,
  }),
}))

function jsonResponse(body, status = 200) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) })
}

beforeEach(() => {
  window.history.pushState({}, 'Test page', '/')
  window.localStorage.clear()
  vi.stubGlobal(
    'fetch',
    vi.fn((url) => {
      const path = String(url)
      if (path.endsWith('/api/health')) return jsonResponse({ status: 'ok', service: 'canopy-api' })
      if (path.endsWith('/api/auth/me')) {
        return jsonResponse({ id: 1, name: 'Admin', email: 'admin@example.org', role: 'admin', org_id: 1, organization: { id: 1, name: 'Demo Org' } })
      }
      if (path.endsWith('/api/regions')) return jsonResponse([{ id: 10, name: 'North Sector' }])
      if (path.endsWith('/api/sensors')) return jsonResponse([])
      if (path.endsWith('/api/satellite-changes')) return jsonResponse([])
      if (path.endsWith('/api/ndvi/batches')) return jsonResponse([])
      if (path.includes('/api/organizations/1/invites')) return jsonResponse([])
      if (path.endsWith('/api/alerts')) return jsonResponse([])
      return jsonResponse([])
    }),
  )
})

describe('App', () => {
  it('renders the auth prompt when not logged in', async () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: /CANOPY/i })).toBeInTheDocument()
    expect(screen.getByText(/Open-source forest monitoring/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Authenticate/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Log in/i })).toBeInTheDocument()
  })

  it('renders dashboard overview and can navigate to ingestion', async () => {
    window.localStorage.setItem('canopy_token', 'demo-token')
    render(<App />)

    expect(await screen.findByRole('heading', { name: /Global Overview/i })).toBeInTheDocument()
    expect(screen.getByTestId('map')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: /Data Ingestion/i }))

    expect(await screen.findByRole('heading', { name: /Data Ingestion & Fusion/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Manual satellite change/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Run Fusion/i })).toBeEnabled()
    expect(screen.getByRole('heading', { name: /Upload NDVI CSV/i })).toBeInTheDocument()
    expect(screen.getByText(/Run 14-day\/500m rule/i)).toBeInTheDocument()
  })

  it('can navigate to settings page', async () => {
    window.localStorage.setItem('canopy_token', 'demo-token')
    render(<App />)

    expect(await screen.findByRole('heading', { name: /Global Overview/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: /Configuration/i }))

    expect(await screen.findByRole('heading', { name: /Configuration & Settings/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Create sensor/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Create region/i })).toBeInTheDocument()
  })

  it('toggles live simulation state', async () => {
    window.localStorage.setItem('canopy_token', 'demo-token')
    render(<App />)

    const simulateButton = await screen.findByRole('button', { name: /Simulate Live Data/i })
    expect(simulateButton).toBeInTheDocument()

    fireEvent.click(simulateButton)
    expect(await screen.findByRole('button', { name: /Stop Simulation/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Stop Simulation/i }))
    expect(await screen.findByRole('button', { name: /Simulate Live Data/i })).toBeInTheDocument()
  })
})
