/**
 * Canopy Institutional Deck Updater
 * Run in Figma Slides: Plugins → Development → Import plugin → select this folder
 * Then: Plugins → Canopy Institutional Deck Updater
 *
 * Updates text layers per slide (top-to-bottom). Expects at least 1 TEXT node per slide.
 * Best results: name layers Title / Subtitle / Body (optional); otherwise uses Y-order.
 */

const SLIDES = [
  {
    title: 'Canopy',
    subtitle: 'Integrated geospatial and acoustic monitoring for forest conservation',
    body: 'Arjun Tyagi · Penn State · Open source\n\nOverview for institutional review and pilot data support',
  },
  {
    title: 'Why this matters for India',
    body: '• Critical forest carbon and biodiversity under increasing pressure\n• Patrol and community guardians cannot cover vast remote areas\n• Early, location-specific alerts reduce response time for logging, fire, and encroachment\n• Tools must work with existing government and NGO GIS — not replace them',
  },
  {
    title: 'The monitoring gap',
    body: 'Satellite / NDVI only\n• Cloud, seasonality, coarse timing\n• Weak for “happening now”\n\nAcoustic sensors only\n• Local signal but weak landscape context\n• Higher false alarms without vegetation context\n\nSeparate dashboards → no shared alert lifecycle\n\nOpportunity: Fuse complementary signals with auditable provenance',
  },
  {
    title: 'Vision — one platform: Hear · See · Act',
    body: '1. Deploy or integrate Forest Listening Units (geolocated sensors)\n2. Ingest vegetation change (NDVI drops, canopy loss events)\n3. Fuse by space and time → prioritized alerts\n4. Map + workflow (acknowledge → investigate → resolve)\n5. Export for rangers, researchers, and institutional reporting\n\nOpen architecture — API-first, PostGIS-native, deployable on-prem or cloud',
  },
  {
    title: 'Who Canopy serves',
    body: '• State forest departments and geospatial teams (NIC, state GIS)\n• Conservation NGOs monitoring multiple field sites\n• Wildlife researchers needing auditable sensor and event data\n• Community forest protection groups (low-bandwidth workflows)\n• Government analysts reviewing deforestation and threat patterns',
  },
  {
    title: 'System architecture',
    body: 'Field\n→ Forest Listening Units · Audio upload\n\nGeospatial\n→ NDVI / satellite pipeline · Region boundaries (GIS)\n\nPlatform\n→ Canopy API (FastAPI) → PostgreSQL + PostGIS\n→ Fusion engine → Dashboard (React + Leaflet map)\n\nModular stack — Docker locally; deployable API and dashboard',
  },
  {
    title: 'Geospatial foundation',
    body: '• SRID 4326 — interoperable with Leaflet, QGIS, GeoJSON\n• Regions: optional polygon boundaries (GeoJSON → PostGIS)\n• Sensors and alerts: point geometry with spatial indexes\n• Alert queries: bounding-box filter on map\n• Tenant model: organization-scoped data (NGO / department / project)',
  },
  {
    title: 'NDVI ingestion → satellite change events',
    body: 'Input: CSV or worker output with lat/lon, baseline & recent NDVI\n→ Compute ndvi_delta and severity_score\n→ Skip rows below loss threshold\n→ Create satellite_change_events with batch provenance\n\nndvi_delta = recent_ndvi - baseline_ndvi\nseverity_score = min(|ndvi_delta| / 0.5, 1.0)\n\nNext: Sentinel / Bhuvan / state raster pipeline → same schema',
  },
  {
    title: 'Acoustic threat detection',
    body: 'Classes: chainsaw · gunshot · vehicle · fire_crackle · background_unknown\n\n• Research prototype on public + curated datasets\n• MVP API uses placeholder until model integration\n• Future: field-labeled Indian forest audio via data partnership',
  },
  {
    title: 'Spatiotemporal fusion',
    body: 'Match acoustic alert ↔ nearest satellite change within distance (e.g. 500 m) and time window (e.g. 14 days)\n\nfusion_score =\n  0.45 × acoustic_confidence\n+ 0.35 × satellite_severity_score\n+ 0.10 × satellite_confidence\n+  0.10 × recurrence_bonus\n\nOutput: fused alert with linked IDs, distance, scores — in CSV export',
  },
  {
    title: 'Dashboard and governance',
    body: '• Web dashboard: map, metrics, alert lifecycle\n• Roles: admin (ingest, fusion, export) · member (read, upload)\n• Organization invites for team onboarding\n• Filtered CSV export with fusion and classifier metadata\n\nSuitable for pilot evaluation before national-scale rollout',
  },
  {
    title: 'Current status (honest)',
    body: '✅ PostGIS schema, API, auth, org RBAC\n✅ Map dashboard, alert workflow, CSV export\n✅ NDVI CSV → satellite change events\n✅ Rule-based fusion\n🔜 Live Sentinel / GEE automation\n🔜 Production acoustic ML in API\n\nTechnical demo completed — ready for real geospatial pilot data',
  },
  {
    title: 'Roadmap',
    body: 'Pilot (requested)\n→ 1–2 Indian sites, real boundaries + NDVI, validation with partners\n\nv1\n→ Live satellite/NDVI worker, production classifier, notifications\n\nv2\n→ Offline field app, QGIS plugin, scale ingestion, institutional integrations',
  },
  {
    title: 'Data request — India pilot',
    body: 'Tier 1 — Minimum\n• 1–2 protected area boundaries (GeoJSON / SHP)\n• NDVI time series or bi-date comparisons (CSV, GeoTIFF, API)\n• Site metadata (name, agency, contact)\n\nTier 2 — Validation\n• Historical disturbance / fire records · land cover · sensor locations\n\nTier 3 — Scale\n• Sentinel / Bhuvan / state GIS feeds · Indian field audio labels\n\nData: pilot scope only; org-scoped; no redistribution without permission',
  },
  {
    title: 'Proposed 6-month pilot',
    body: 'Scope: One state forest or NGO landscape (≈10²–10⁴ km²)\n\nMonth 1–2: Ingest boundaries + NDVI\nMonth 3–4: Fusion review with geospatial lead\nMonth 5–6: Pilot report (precision, fusion uplift, scale recommendation)\n\nRoles\n• Institution: data access, validation, introductions\n• Arjun / Penn State: platform, ingestion, reporting\n• Field partner (optional): ground-truth\n\nDeliverable: institutional recommendation',
  },
  {
    title: 'Request and next steps',
    body: 'We request:\n1. Endorsement for limited geospatial data pilot\n2. Introduction to forest department / NGO data custodians\n3. Guidance on compliant data-sharing under government norms\n\nNext steps:\n• MoU or collaboration letter if required\n• Define pilot polygon + data format\n• Technical onboarding (API / CSV ingestion)\n\nThank you for supporting this pilot forward.',
  },
  {
    title: 'Appendix — supported data formats',
    body: 'A. Region boundary: GeoJSON Polygon, SRID 4326\nB. NDVI CSV: latitude, longitude, baseline_ndvi, recent_ndvi (+ optional dates)\nC. Satellite change: type, severity, confidence, lat/lon, source\nD. Acoustic: clip + sensor_id + geolocated sensor\nE. Outputs: alert list + CSV with fusion metadata (decision-support, not legal evidence)',
  },
]

function getSlidesInOrder() {
  const grid = figma.getSlideGrid()
  return grid.flat()
}

function textNodesOnSlide(slide) {
  return slide
    .findAll((n) => n.type === 'TEXT')
    .sort((a, b) => a.y - b.y || a.x - b.x)
}

function pickByName(nodes, names) {
  for (const name of names) {
    const hit = nodes.find((n) => n.name.toLowerCase().includes(name))
    if (hit) return hit
  }
  return null
}

function applyContent(slide, content, index) {
  const nodes = textNodesOnSlide(slide)
  if (!nodes.length) {
    console.warn(`Slide ${index + 1}: no TEXT nodes found`)
    return 0
  }

  let updated = 0
  const titleNode = pickByName(nodes, ['title', 'heading', 'h1']) || nodes[0]
  const subtitleNode = pickByName(nodes, ['subtitle', 'tagline', 'h2'])
  const bodyNode = pickByName(nodes, ['body', 'content', 'bullet', 'text']) || nodes[nodes.length - 1]

  async function setText(node, text) {
    if (!node || !text) return
    await figma.loadFontAsync(node.fontName)
    node.characters = text
    updated += 1
  }

  return (async () => {
    await setText(titleNode, content.title)
    if (content.subtitle) {
      const sub = subtitleNode && subtitleNode !== titleNode ? subtitleNode : nodes[1]
      if (sub && sub !== titleNode) await setText(sub, content.subtitle)
    }
    const bodyTarget =
      bodyNode && bodyNode !== titleNode && bodyNode !== subtitleNode
        ? bodyNode
        : nodes.find((n) => n !== titleNode && n !== subtitleNode) || nodes[nodes.length - 1]
    await setText(bodyTarget, content.body)
    return updated
  })()
}

async function main() {
  const slides = getSlidesInOrder()
  if (!slides.length) {
    figma.closePlugin('No slides found. Open your Canopy deck in Figma Slides.')
    return
  }

  let total = 0
  const count = Math.min(slides.length, SLIDES.length)

  for (let i = 0; i < count; i++) {
    total += await applyContent(slides[i], SLIDES[i], i)
  }

  const extra = slides.length - SLIDES.length
  const missing = SLIDES.length - slides.length
  let msg = `Updated ${count} slide(s), ${total} text layer(s).`
  if (missing > 0) msg += ` Add ${missing} more slide(s) in Figma for full deck.`
  if (extra > 0) msg += ` ${extra} slide(s) in file had no content mapping.`

  figma.closePlugin(msg)
}

main()
