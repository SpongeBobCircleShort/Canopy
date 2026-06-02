import re
import sys

def update_file(path, processor):
    try:
        with open(path, 'r') as f:
            content = f.read()
        new_content = processor(content)
        if new_content != content:
            with open(path, 'w') as f:
                f.write(new_content)
            print(f"Updated {path}")
        else:
            print(f"No changes for {path}")
    except Exception as e:
        print(f"Error updating {path}: {e}")

# 1. LandingPage.jsx
def process_landing_page(content):
    # Add hero-divider
    if '<div className="hero-divider" />' not in content:
        content = content.replace('<div className="landing-hero-heading">', '<div className="hero-divider" />\n          <div className="landing-hero-heading">')
    return content

update_file('frontend/src/components/LandingPage.jsx', process_landing_page)

# 2. Layout.jsx
def process_layout(content):
    # Fix CANOPY wordmark and version string
    content = re.sub(r'<div className="text-heading" style={{.*?}}>CANOPY</div>', r'<div style={{ fontFamily: "var(--font-label)", fontWeight: 600, fontSize: "0.85rem", letterSpacing: "0.12em", color: "#1A2E1A" }}>CANOPY</div>', content)
    content = re.sub(r'<span className="eyebrow".*?v0\.2\.0 / {health\.status}</span>', r'<span style={{ fontFamily: "var(--font-body)", fontWeight: 300, fontSize: "0.72rem", color: "#999" }}>v0.2.0 / {isDemoMode ? "DEMO" : health.status.toUpperCase()}</span>', content)
    
    # Bottom org area
    content = re.sub(r'<div className="org-info">.*?<strong>(.*?)</strong>.*?<span>(.*?)</span>.*?</div>', r'<div className="org-info" style={{ display: "flex", flexDirection: "column" }}>\n              <strong style={{ fontFamily: "var(--font-body)", fontWeight: 300, color: "#1A2E1A", fontSize: "0.85rem" }}>\1</strong>\n              <span style={{ fontFamily: "var(--font-body)", fontWeight: 300, color: "#999", fontSize: "0.72rem" }}>\2</span>\n            </div>', content, flags=re.DOTALL)
    
    # Reset Demo button
    content = re.sub(r'<button className="logout-btn".*?>(\{isDemoMode.*?\})</button>', r'<button className="logout-btn" style={{ background: "transparent", border: "1px solid #1A2E1A", color: "#1A2E1A", fontFamily: "var(--font-label)", textTransform: "uppercase", fontSize: "0.75rem", padding: "10px 16px", borderRadius: "3px", width: "calc(100% - 64px)", margin: "0 32px" }} onClick={onLogout}>\1</button>', content, flags=re.DOTALL)
    
    # Sidebar styles handled in CSS
    return content

update_file('frontend/src/components/Layout.jsx', process_layout)

# 3. Overview.jsx
def process_overview(content):
    # Remove public demo dashboard banner or replace with small pill
    # Wait, the prompt says replace the "Showing public demo dashboard..." banner. The banner might be in DashboardApp.jsx
    
    # Page title GLOBAL OVERVIEW
    content = re.sub(r'<h2 className="text-heading".*?>GLOBAL OVERVIEW</h2>', r'<h2 style={{ fontFamily: "var(--font-label)", fontWeight: 600, letterSpacing: "0.10em", fontSize: "1.4rem", color: "#FFFFFF", margin: 0 }}>GLOBAL OVERVIEW</h2>', content)
    
    # RECENT ALERTS
    content = re.sub(r'<h2 className="text-heading".*?>RECENT ALERTS</h2>', r'<h2 style={{ fontFamily: "var(--font-label)", textTransform: "uppercase", letterSpacing: "0.10em", fontSize: "0.78rem", color: "#FFFFFF", fontWeight: 500, marginBottom: "20px" }}>RECENT ALERTS</h2>', content)
    
    # Update status label
    content = re.sub(r'<label>\s*Update status', r'<label style={{ fontFamily: "var(--font-label)", textTransform: "uppercase", letterSpacing: "0.09em", fontSize: "0.65rem", color: "#555" }}>\n                Update status', content)

    # Dropdown chevron handled via CSS class 'status-select'
    content = content.replace('<select\n', '<select className="status-select"\n')

    # Alert Title
    content = re.sub(r'<h3 style={{.*?}}>\s*(\{alert\.description\})\s*</h3>', r'<h3 style={{ fontFamily: "var(--font-body)", fontSize: "0.875rem", fontWeight: 500, color: "#FFFFFF", textTransform: "none", lineHeight: 1.4, marginBottom: "8px", marginTop: "12px" }}>\n                \1\n              </h3>', content)

    # Alert Meta
    content = re.sub(r'<p>\s*(\{alert\.location\.lat.*?)\s*</p>', r'<p style={{ fontFamily: "var(--font-body)", fontWeight: 300, fontSize: "0.78rem", color: "#666", lineHeight: 1.6 }}>\n                \1\n              </p>', content, flags=re.DOTALL)
    
    # Classifier Meta
    content = re.sub(r'<p>\s*Classifier:(.*?)</p>', r'<p style={{ fontFamily: "var(--font-body)", fontWeight: 300, fontSize: "0.78rem", color: "#666", lineHeight: 1.6 }}>\n                  Classifier:\1</p>', content, flags=re.DOTALL)

    return content

update_file('frontend/src/components/Overview.jsx', process_overview)

# 4. DashboardApp.jsx (for the banner)
def process_dashboard_app(content):
    banner_match = re.search(r'<div className="demo-banner">.*?</div>', content, re.DOTALL)
    if banner_match:
        pill = '<div style={{ position: "absolute", top: "32px", right: "40px", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.10)", borderRadius: "100px", padding: "4px 12px", fontFamily: "var(--font-body)", fontWeight: 300, fontSize: "0.72rem", color: "#888", display: "flex", alignItems: "center", zIndex: 10 }}>Demo mode · API not connected</div>'
        content = content.replace(banner_match.group(0), pill)
    return content

update_file('frontend/src/DashboardApp.jsx', process_dashboard_app)

# 5. styles.css
def process_styles(content):
    # Global cleanup of neon
    content = re.sub(r'#b5ff00|#CCFF00|#c8ff00|#a8e000', '#6B8F6B', content, flags=re.IGNORECASE)
    
    # Add new CSS to the end to override previous ones
    new_css = """
/* POLISH PASS OVERRIDES */

/* Dashboard Cohesion */
.main-sidebar {
  background: #FFFFFF !important;
  border-right: 1px solid #E8E8E8 !important;
}
.sidebar-nav a {
  font-family: var(--font-label) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  font-size: 0.78rem !important;
  color: #999 !important;
  background: transparent !important;
  border-left: 2px solid transparent !important;
  padding: 10px 20px 10px 18px !important;
  font-weight: 500 !important;
}
.sidebar-nav a.active {
  color: #1A2E1A !important;
  background: rgba(26,46,26,0.06) !important;
  border-left-color: #2D4A2D !important;
}
.metrics-grid div {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  border-radius: 6px !important;
  padding: 24px !important;
}
.metrics-grid strong {
  font-family: var(--font-display) !important;
  font-size: 2.5rem !important;
  color: #FFFFFF !important;
  font-weight: 400 !important;
}
.metrics-grid span {
  font-family: var(--font-label) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.09em !important;
  font-size: 0.68rem !important;
  color: #666 !important;
  margin-top: 8px !important;
}
.map-panel {
  border-radius: 8px !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  box-shadow: none !important;
}
.alert-card, .satellite-change-card {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  border-radius: 6px !important;
  padding: 16px !important;
}
.alert-card.fused-alert-card {
  border-left: 2px solid #6B8F6B !important;
  background: rgba(107,143,107,0.08) !important;
}
.pill {
  background: transparent !important;
  border: 1px solid rgba(255,255,255,0.20) !important;
  border-radius: 100px !important;
  padding: 2px 8px !important;
  font-size: 0.65rem !important;
  font-family: var(--font-label) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  color: #999 !important;
}
.pill.high, .pill.critical {
  border-color: #C0392B !important;
  color: #C0392B !important;
}
.pill.medium {
  border-color: #E67E22 !important;
  color: #E67E22 !important;
}
.pill.low, .pill.open {
  border-color: #6B8F6B !important;
  color: #6B8F6B !important;
}
.status-select {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 4px;
  color: #FFFFFF;
  font-family: var(--font-body);
  font-weight: 300;
  font-size: 0.85rem;
  appearance: none;
  padding: 8px 32px 8px 12px;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  width: 100%;
  margin-top: 6px;
}

/* Landing Page Edge Polish */
.landing-hero {
  position: relative;
}
.hero-divider {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(26,46,26,0.10);
  mask-image: linear-gradient(to bottom, transparent, var(--ink) 20%, var(--ink) 80%, transparent);
  -webkit-mask-image: linear-gradient(to bottom, transparent, var(--ink) 20%, var(--ink) 80%, transparent);
}
.landing-hero-heading, .landing-hero-copy {
  padding: 56px 48px !important;
}
.landing-hero-copy {
  display: flex !important;
  flex-direction: column !important;
  justify-content: flex-end !important;
}
.landing-cta {
  display: flex !important;
  gap: 12px !important;
  flex-wrap: wrap !important;
  flex-direction: row !important;
}
.landing-btn {
  font-family: var(--font-label) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  font-size: 0.75rem !important;
  border-radius: 3px !important;
  padding: 12px 24px !important;
  text-decoration: none !important;
  box-shadow: none !important;
  transition: background 200ms ease, color 200ms ease !important;
}
.landing-btn.primary {
  background: var(--ink) !important;
  color: var(--white) !important;
  border: none !important;
}
.landing-btn.ghost {
  background: transparent !important;
  border: 1px solid var(--ink) !important;
  color: var(--ink) !important;
}
.landing-btn.ghost:hover {
  background: var(--ink) !important;
  color: var(--white) !important;
}
.landing-feat {
  background: transparent !important;
  box-shadow: none !important;
  border-radius: 0 !important;
  border-top: 1px solid rgba(26,46,26,0.12) !important;
  padding: 32px 0 0 0 !important;
}
.landing-feat-icon svg {
  width: 24px !important;
  height: 24px !important;
  stroke-width: 1.5 !important;
  color: var(--ink) !important;
  margin-bottom: 20px !important;
}
.landing-feat h3 {
  font-family: var(--font-label) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  font-size: 0.78rem !important;
  color: var(--ink) !important;
  font-weight: 500 !important;
}
.landing-feat p {
  font-family: var(--font-body) !important;
  font-weight: 300 !important;
  font-size: 0.875rem !important;
  color: var(--sage) !important;
  line-height: 1.6 !important;
  max-width: 30ch !important;
}
.landing-topbar {
  height: 60px !important;
  padding: 0 40px !important;
}
.landing-brand {
  font-family: var(--font-label) !important;
  font-size: 0.85rem !important;
  font-weight: 600 !important;
  letter-spacing: 0.12em !important;
  color: var(--ink) !important;
}
.landing-nav a {
  transition: color 150ms ease !important;
}
.landing-nav .nav-cta {
  padding: 8px 18px !important;
  border-radius: 3px !important;
  font-size: 0.75rem !important;
}

/* Global Cleanup */
body {
  line-height: 1.65;
}
.dashboard-grid {
  line-height: 1.6;
}
* {
  text-shadow: none !important;
}
"""
    return content + "\n" + new_css

update_file('frontend/src/styles.css', process_styles)
