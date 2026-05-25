import { useMemo } from 'react'
import { Link } from 'react-router-dom'

function buildDotMap(highlightIndia) {
  const w = 56
  const h = 28
  const dots = []
  const india = (x, y) => x > 34 && x < 48 && y > 8 && y < 22
  const belt = (x, y) =>
    (x > 8 && x < 28 && y > 6 && y < 18) ||
    (x > 30 && x < 50 && y > 4 && y < 24) ||
    (highlightIndia && india(x, y))

  let seed = highlightIndia ? 42 : 7
  const rand = () => {
    seed = (seed * 16807) % 2147483647
    return seed / 2147483647
  }

  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      if (rand() > 0.38) {
        dots.push({ x, y, hi: belt(x, y) })
      }
    }
  }
  return { w, h, dots }
}

function DotMap({ highlightIndia }) {
  const { w, h, dots } = useMemo(() => buildDotMap(highlightIndia), [highlightIndia])

  return (
    <svg className="landing-map" viewBox={`0 0 ${w * 8} ${h * 8}`} preserveAspectRatio="xMidYMax meet" aria-hidden="true">
      {dots.map(({ x, y, hi }) => (
        <circle
          key={`${x}-${y}`}
          cx={x * 8 + 4}
          cy={y * 8 + 4}
          r={hi ? 3.2 : 2.2}
          fill={hi ? '#c8ff3e' : '#3a4a42'}
          opacity={hi ? 0.95 : 0.5}
        />
      ))}
    </svg>
  )
}

const FEATURES = [
  {
    title: 'Geospatial + acoustic',
    body: 'NDVI ingestion and forest listening units on a single alert model.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <path d="M2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20" />
      </svg>
    ),
  },
  {
    title: 'Auditable exports',
    body: 'CSV with fusion provenance for patrols and institutional review.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
  {
    title: 'India pilot',
    body: 'Open source platform seeking reserve boundaries and NDVI data partners.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="m12 3-1.9 5.8H4.4l4.8 3.5-1.8 5.7L12 14.3l4.6 3.7-1.8-5.7 4.8-3.5H13.9L12 3z" />
      </svg>
    ),
  },
]

export default function LandingPage() {
  return (
    <div className="landing-page">
      <header className="landing-topbar">
        <span className="landing-brand">Canopy</span>
        <nav className="landing-nav">
          <a href="/deck.html">Presentation</a>
          <Link to="/app">Dashboard</Link>
        </nav>
      </header>

      <main className="landing-main">
        <div className="landing-hero">
          <div>
            <p className="landing-eyebrow">Forest monitoring</p>
            <h1>
              Scale conservation intelligence across <span className="landing-accent">India’s forest landscapes.</span>
            </h1>
          </div>
          <p className="landing-lead">
            Canopy fuses satellite vegetation signals with acoustic threat detection on one map — built for NGOs,
            researchers, and government GIS teams. PostGIS-native. Pilot-ready.
          </p>
        </div>

        <div className="landing-features">
          {FEATURES.map((f) => (
            <div className="landing-feat" key={f.title}>
              <div className="landing-feat-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          ))}
        </div>

        <div className="landing-cta">
          <a className="landing-btn primary" href="/deck.html">
            View full presentation
          </a>
          <Link className="landing-btn ghost" to="/app">
            Open dashboard
          </Link>
        </div>

        <DotMap highlightIndia />
      </main>

      <footer className="landing-footer">
        Arjun Tyagi · Penn State · Open source · Institutional overview for geospatial data pilot
      </footer>
    </div>
  )
}
