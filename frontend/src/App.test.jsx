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

vi.mock('./api.js', () => ({
  fetchHealth: vi.fn(() => Promise.resolve({ status: 'ok' })),
  fetchMe: vi.fn(() =>
    Promise.resolve({
      id: 1,
      name: 'Admin',
      email: 'admin@example.org',
      role: 'admin',
      org_id: 1,
      organization: { id: 1, name: 'Demo Org' },
    }),
  ),
  fetchAlerts: vi.fn(() => Promise.resolve(apiData.alerts)),
  fetchSensors: vi.fn(() => Promise.resolve(apiData.sensors)),
  fetchRegions: vi.fn(() => Promise.resolve([{ id: 10, name: 'North Sector' }])),
  fetchSatelliteChanges: vi.fn(() => Promise.resolve(apiData.satelliteChanges)),
  fetchNdviBatches: vi.fn(() => Promise.resolve([])),
  fetchInvites: vi.fn(() => Promise.resolve([])),
  login: vi.fn(),
  signup: vi.fn(),
  logout: vi.fn(),
  createInvite: vi.fn(),
  revokeInvite: vi.fn(),
  createRegion: vi.fn(),
  createSensor: vi.fn(),
  uploadClip: vi.fn(),
  createSatelliteChange: vi.fn(),
  uploadNdviCsv: vi.fn(),
  runFusion: vi.fn(),
  updateAlertStatus: vi.fn(),
  downloadAlertsCsv: vi.fn(),
}))

afterEach(() => {
  cleanup()
})

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }) => <div data-testid="map">{children}</div>,
  TileLayer: () => <div />,
  CircleMarker: ({ children }) => <div>{children}</div>,
  Popup: ({ children }) => <div>{children}</div>,
  useMap: () => mockMap,
  useMapEvents: () => mockMap,
}))

beforeEach(() => {
  window.localStorage.clear()
  apiData.alerts = []
  apiData.sensors = []
  apiData.satelliteChanges = []
  mockMap.fitBounds.mockClear()
  mockMap.getZoom.mockClear()
  mockMap.setView.mockClear()
})

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App', () => {
  it('renders the public landing page at /', () => {
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
    apiData.alerts = [
      {
        id: 2,
        type: 'audio',
        status: 'open',
        priority: 'high',
        description: 'Audio alert',
        location: { lat: 22.3, lon: 79.4 },
      },
    ]

    renderAt('/app')

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
