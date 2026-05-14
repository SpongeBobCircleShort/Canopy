import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App.jsx'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }) => <div data-testid="map">{children}</div>,
  TileLayer: () => <div />,
  CircleMarker: ({ children }) => <div>{children}</div>,
  Popup: ({ children }) => <div>{children}</div>,
}))

vi.stubGlobal(
  'fetch',
  vi.fn((url) => {
    if (url.endsWith('/api/health')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ status: 'ok', service: 'canopy-api' }) })
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) })
  }),
)

describe('App', () => {
  it('renders the Canopy dashboard and auth prompt', async () => {
    window.localStorage.clear()
    render(<App />)

    expect(screen.getByRole('heading', { name: /Canopy conservation dashboard/i })).toBeInTheDocument()
    expect(screen.getByText(/Log in or sign up to load organization-scoped/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Sign up or log in/i })).toBeInTheDocument()
    expect(screen.getByTestId('map')).toBeInTheDocument()
  })
})
