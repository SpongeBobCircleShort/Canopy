import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.jsx'
import ToastStack from './components/ToastStack.jsx'

const { apiData, mockMap } = vi.hoisted(() => ({
  apiData: {
    alerts: [],
    sensors: [],
    satelliteChanges: [],
  },
  mockMap: {
    fitBounds: vi.fn(),
    getZoom: vi.fn(() => 6),
    setView: vi.fn(),
  },
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }) => <div data-testid="map">{children}</div>,
  TileLayer: () => <div />,
  CircleMarker: ({ children }) => <div>{children}</div>,
  Popup: ({ children }) => <div>{children}</div>,
  useMap: () => mockMap,
  useMapEvents: () => mockMap,
}))

function jsonResponse(body, status = 200) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) })
}

beforeEach(() => {
  window.history.pushState({}, 'Test page', '/')
  window.localStorage.clear()
  apiData.alerts = []
  apiData.sensors = []
  apiData.satelliteChanges = []
  mockMap.fitBounds.mockClear()
  mockMap.getZoom.mockClear()
  mockMap.setView.mockClear()
  vi.stubGlobal(
    'fetch',
    vi.fn((url) => {
      const path = String(url)
      if (path.endsWith('/api/health')) return jsonResponse({ status: 'ok', service: 'canopy-api' })
      if (path.endsWith('/api/auth/me')) {
        return jsonResponse({ id: 1, name: 'Admin', email: 'admin@example.org', role: 'admin', org_id: 1, organization: { id: 1, name: 'Demo Org' } })
      }
      if (path.endsWith('/api/regions')) return jsonResponse([{ id: 10, name: 'North Sector' }])
      if (path.endsWith('/api/sensors')) return jsonResponse(apiData.sensors)
      if (path.endsWith('/api/satellite-changes')) return jsonResponse(apiData.satelliteChanges)
      if (path.endsWith('/api/ndvi/batches')) return jsonResponse([])
      if (path.includes('/api/organizations/1/invites')) return jsonResponse([])
      if (path.endsWith('/api/alerts')) return jsonResponse(apiData.alerts)
      return jsonResponse([])
    }),
  )
})

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App', () => {
  it('renders the public landing page at /', async () => {
    renderAt('/')

    expect(screen.getByText(/Scale conservation intelligence/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /View full presentation/i })).toHaveAttribute('href', '/deck.html')
    expect(screen.getByRole('link', { name: /Open dashboard/i })).toHaveAttribute('href', '/app')
  })

  it('renders dashboard overview and can navigate to ingestion', async () => {
    window.localStorage.setItem('canopy_token', 'demo-token')
    renderAt('/app')

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
    renderAt('/app')

    expect(await screen.findByRole('heading', { name: /Global Overview/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: /Configuration/i }))

    expect(await screen.findByRole('heading', { name: /Configuration & Settings/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Create sensor/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Create region/i })).toBeInTheDocument()
  })

  it('toggles live simulation state', async () => {
    window.localStorage.setItem('canopy_token', 'demo-token')
    renderAt('/app')

    const simulateButton = await screen.findByRole('button', { name: /Simulate Live Data/i })
    expect(simulateButton).toBeInTheDocument()

    fireEvent.click(simulateButton)
    expect(await screen.findByRole('button', { name: /Stop Simulation/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Stop Simulation/i }))
    expect(await screen.findByRole('button', { name: /Simulate Live Data/i })).toBeInTheDocument()
  })

  it('opens and closes the responsive navigation menu', async () => {
    window.localStorage.setItem('canopy_token', 'demo-token')
    renderAt('/app')

    await screen.findByRole('heading', { name: /Global Overview/i })

    const openMenuButton = screen.getByRole('button', { name: /Open navigation menu/i })
    expect(openMenuButton).toHaveAttribute('aria-expanded', 'false')

    fireEvent.click(openMenuButton)
    expect(screen.getByRole('button', { name: /Close navigation menu/i, expanded: true })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: /Data Ingestion/i }))
    expect(await screen.findByRole('button', { name: /Open navigation menu/i })).toHaveAttribute('aria-expanded', 'false')
  })

  it('auto-fits the map to available markers', async () => {
    window.localStorage.setItem('canopy_token', 'demo-token')
    apiData.sensors = [{ id: 1, name: 'North Sensor', status: 'active', location: { lat: 21.1, lon: 78.2 } }]
    apiData.alerts = [{ id: 2, type: 'audio', status: 'open', priority: 'high', description: 'Audio alert', location: { lat: 22.3, lon: 79.4 } }]

    render(<App />)

    await screen.findByRole('heading', { name: /Global Overview/i })
    await waitFor(() => {
      expect(mockMap.fitBounds).toHaveBeenCalledWith(
        [
          [22.3, 79.4],
          [21.1, 78.2],
        ],
        { animate: true, maxZoom: 10, padding: [48, 48] },
      )
    })
  })

  it('renders dismissible toast notifications', () => {
    render(<ToastStack toasts={[{ id: 'demo-error', type: 'error', message: 'Something failed' }]} />)

    expect(screen.getByText(/Something failed/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Dismiss error notification/i }))
    expect(screen.queryByText(/Something failed/i)).not.toBeInTheDocument()
  })
})
