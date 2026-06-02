import { useMemo } from 'react'
import { Link } from 'react-router-dom'

function buildWaveBars() {
  const bars = []
  let seed = 29
  const rand = () => {
    seed = (seed * 16807) % 2147483647
    return seed / 2147483647
  }

  for (let index = 0; index < 64; index += 1) {
    const wave = Math.sin(index * 0.42) * 18 + Math.sin(index * 0.13) * 12
    const height = Math.max(18, Math.min(96, 48 + wave + rand() * 26))
    bars.push({ height, delay: `${index * -70}ms` })
  }
  return bars
}

function Waveform() {
  const bars = useMemo(buildWaveBars, [])

  return (
    <div className="landing-waveform" aria-hidden="true">
      <svg width="100%" height="100%" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        {bars.map((bar, index) => (
          <rect
            key={index}
            x={`${(index / 64) * 100}%`}
            y={`${100 - bar.height}%`}
            width={`${100 / 64 - 0.2}%`}
            height={`${bar.height}%`}
            fill="var(--ink)"
            className="waveform-bar"
            style={{
              animation: `waveform-rise 4.8s var(--ease-out) infinite`,
              animationDelay: bar.delay,
              transformOrigin: 'bottom'
            }}
          />
        ))}
      </svg>
    </div>
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
          <Link to="/app" className="nav-cta">Dashboard</Link>
        </nav>
      </header>

      <main className="landing-main">
        <div className="landing-hero">
          <Waveform />
          <div className="hero-divider" />
          <div className="landing-hero-heading">
            <p className="landing-eyebrow">Forest monitoring</p>
            <h1>
              Scale conservation intelligence across <em>India’s forest landscapes.</em>
            </h1>
          </div>
          <div className="landing-hero-copy">
            <p className="landing-lead">
              Canopy fuses satellite vegetation signals with acoustic threat detection on one map — built for NGOs,
              researchers, and government GIS teams. PostGIS-native. Pilot-ready.
            </p>
            <div className="landing-cta">
              <a className="landing-btn primary" href="/deck.html">
                View full presentation
              </a>
              <Link className="landing-btn ghost" to="/app">
                Open dashboard
              </Link>
            </div>
          </div>
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
      </main>

      <footer className="landing-footer">
        Arjun Tyagi · Penn State · Open source · Institutional overview for geospatial data pilot
      </footer>
    </div>
  )
}
