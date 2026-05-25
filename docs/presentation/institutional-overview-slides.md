# Canopy — Institutional Overview Deck

**Use:** Forwardable presentation for Gollavilli Srikanth / NIC / forest data partners  
**Format:** Copy each slide block into Figma (Title → H1, Subtitle → H2, bullets → body)  
**Frames:** 1920×1080, dark bg `#0a0a0a`, accent `#d4ff00`, text `#f0f0f0`, font Inter

---

## Slide 1 — Title

**Title:** Canopy  
**Subtitle:** Integrated geospatial and acoustic monitoring for forest conservation  
**Footer:** Arjun Tyagi · Penn State · Open source  
**Tagline:** Overview for institutional review and pilot data support

---

## Slide 2 — Why this matters (India)

**Title:** Why this matters for India

**Bullets:**
- Critical forest carbon and biodiversity under increasing pressure
- Patrol and community guardians cannot cover vast remote areas
- Early, location-specific alerts reduce response time for logging, fire, and encroachment
- Tools must work with existing government and NGO GIS — not replace them

---

## Slide 3 — The gap today

**Title:** The monitoring gap

**Table / two columns:**

| Satellite / NDVI only | Acoustic sensors only |
| Cloud, seasonality, coarse timing | Local signal but weak landscape context |
| Weak for “happening now” | Higher false alarms without vegetation context |

**Bottom line:** Separate dashboards → no shared alert lifecycle or field-ready export

**Opportunity:** Fuse complementary signals with auditable provenance

---

## Slide 4 — Vision

**Title:** Vision — one platform: Hear · See · Act

**Bullets:**
1. Deploy or integrate Forest Listening Units (geolocated sensors)
2. Ingest vegetation change (NDVI drops, canopy loss events)
3. Fuse by space and time → prioritized alerts
4. Map + workflow (acknowledge → investigate → resolve)
5. Export for rangers, researchers, and institutional reporting

**Footer:** Open architecture — API-first, PostGIS-native, deployable on-prem or cloud

---

## Slide 5 — Primary users

**Title:** Who Canopy serves

**Bullets:**
- State forest departments and geospatial teams (NIC, state GIS)
- Conservation NGOs monitoring multiple field sites
- Wildlife researchers needing auditable sensor and event data
- Community forest protection groups (low-bandwidth workflows)
- Government analysts reviewing deforestation and threat patterns

---

## Slide 6 — System architecture

**Title:** System architecture

**Diagram labels (build in Figma):**

```
Field: Forest Listening Units → Audio upload
Geospatial: NDVI / satellite pipeline + Region boundaries (GIS)
Platform: Canopy API (FastAPI) → PostgreSQL + PostGIS
         → Fusion engine → Dashboard (React + Leaflet map)
```

**Caption:** Modular stack — Docker locally; API and dashboard deployable independently

---

## Slide 7 — Geospatial foundation

**Title:** Geospatial foundation

**Bullets:**
- SRID 4326 — interoperable with Leaflet, QGIS, GeoJSON
- Regions: optional polygon boundaries (GeoJSON → PostGIS geometry)
- Sensors and alerts: point geometry with spatial indexes
- Alert queries: bounding-box filter (`bbox=min_lon,min_lat,max_lon,max_lat`)
- Tenant model: organization-scoped data (NGO / department / project)

---

## Slide 8 — NDVI → operational events

**Title:** NDVI ingestion → satellite change events

**Table:**

| Input | Processing |
| CSV or worker output: lat/lon, baseline & recent NDVI | Compute ndvi_delta, severity_score |
| Rows below loss threshold | Skipped to reduce noise |
| Valid vegetation-loss rows | Auto-create satellite_change_events with batch provenance |

**Formula (mono font):**
```
ndvi_delta = recent_ndvi - baseline_ndvi
severity_score = min(|ndvi_delta| / 0.5, 1.0)
```

**Metadata preserved:** baseline_ndvi, recent_ndvi, ndvi_delta, threshold, ingestion_batch_id, row_number

**Next step:** Automated Sentinel / Bhuvan / state raster pipeline → same event schema

---

## Slide 9 — Acoustic threat detection

**Title:** Acoustic threat detection

**Classes (accent chips):** chainsaw · gunshot · vehicle · fire_crackle · background_unknown

**Bullets:**
- Research prototype on public + curated datasets (separate from API runtime today)
- MVP API uses placeholder classifier until model integration
- Designed for Indian forest soundscapes via future field-labeled data partnership

---

## Slide 10 — Fusion logic

**Title:** Spatiotemporal fusion (core differentiator)

**Matching rule:** Acoustic alert ↔ nearest satellite change within configurable distance (e.g. 500 m) and time window (e.g. 14 days)

**Formula (mono, large):**
```
fusion_score =
  0.45 × acoustic_confidence
+ 0.35 × satellite_severity_score
+ 0.10 × satellite_confidence
+  0.10 × recurrence_bonus
```

**Output:** Fused alert with linked acoustic_alert_id, satellite_change_id, distance_meters, fusion_score — included in CSV export

---

## Slide 11 — Dashboard & governance

**Title:** Dashboard and governance

**Bullets:**
- Web dashboard: map, metrics, alert lifecycle
- Roles: admin (ingest, fusion, export) · member (read, upload clips)
- Organization invites for team onboarding
- Filtered CSV export with fusion and classifier metadata

**Footer:** Suitable for pilot evaluation before national-scale rollout

---

## Slide 12 — What is built today

**Title:** Current status (honest)

| Component | Status |
| PostGIS schema, API, auth, org RBAC | ✅ Working |
| Map dashboard, alert workflow, CSV export | ✅ Working |
| NDVI CSV → satellite change events | ✅ Working |
| Rule-based fusion | ✅ Working |
| Live Sentinel / GEE automation | 🔜 Planned |
| Production acoustic ML in API | 🔜 Research → integration |

**Footer:** Technical demo completed; platform ready for real geospatial data in a controlled pilot

---

## Slide 13 — Roadmap

**Title:** Roadmap

| Phase | Deliverable |
| **Pilot (requested)** | 1–2 Indian sites, real boundaries + NDVI, validation with forest/NGO partners |
| **v1** | Live satellite/NDVI worker, production classifier, notifications |
| **v2** | Offline field app, QGIS plugin, scale ingestion, institutional integrations |

---

## Slide 14 — Data needed for India pilot

**Title:** Data request — India pilot

**Tier 1 — Minimum to start**

| Data | Format | Use |
| 1–2 protected area boundaries | GeoJSON / SHP | Region polygons in PostGIS |
| NDVI time series or bi-date comparisons | CSV, GeoTIFF, or API | Satellite change events |
| Site metadata | Name, agency, contact | Pilot documentation |

**Tier 2 — Stronger validation:** historical disturbance/fire records · land cover layer · existing sensor locations

**Tier 3 — Scale path:** operational Sentinel / Bhuvan / state GIS feeds · field-labeled Indian audio

**Footer:** Data used only for agreed pilot scope; org-scoped storage; no redistribution without permission

---

## Slide 15 — Proposed pilot structure

**Title:** Proposed 6-month pilot

**Scope:** One state or one NGO landscape (≈10²–10⁴ km² to start)

**Timeline:**
- Month 1–2: Ingest boundaries + NDVI samples
- Month 3–4: Fusion runs + false-positive review with geospatial lead
- Month 5–6: Pilot report and scale/no-scale recommendation

**Roles:**
- Institution: data access, domain validation, stakeholder introductions
- Arjun / Penn State: platform, ingestion, fusion, technical reporting
- Field partner (optional): ground-truth on selected alerts

**Deliverable:** Alert precision analysis, fusion uplift vs. single-source, institutional recommendation

---

## Slide 16 — Ask & next steps

**Title:** Request and next steps

**We request:**
1. Endorsement for a limited geospatial data pilot (boundaries + NDVI-related inputs)
2. Introduction to appropriate forest department / NGO / data custodian
3. Guidance on compliant data-sharing under government norms

**Immediate next steps:**
- MoU or collaboration letter (if required by data custodian)
- Define pilot polygon + data delivery format
- Technical onboarding (API / CSV ingestion walkthrough)

**Closing:** Thank you for the initial review and support in moving this pilot forward.

---

## Slide 17 — Appendix: Data formats (optional)

**Title:** Appendix — supported data formats

**A. Region boundary:** GeoJSON Polygon, SRID 4326, or shapefile converted to GeoJSON

**B. NDVI CSV (supported today):**  
Required: latitude, longitude, baseline_ndvi, recent_ndvi  
Optional: baseline_start, baseline_end, observation_start, observation_end, confidence, description

**C. Satellite change (manual or worker):** change_type, severity_score, confidence, lat/lon, observation dates, source

**D. Acoustic:** clip + sensor_id + timestamp; sensor registered with lat/lon

**E. Outputs to partners:** alert list + CSV with coordinates, fusion metadata — decision-support only, not legal evidence

---

## Executive summary (1-page — separate Figma frame or PDF)

**Project Canopy** — Integrated forest threat monitoring (geospatial + acoustic)

**Problem:** Acoustic and satellite monitoring are siloed; patrol capacity is limited; India needs auditable, location-aware alerts.

**Approach:** Open-source platform fusing NDVI/satellite change events with acoustic threats by space and time; PostGIS backend; map dashboard; CSV export.

**Maturity:** Working MVP (demo completed). Live Sentinel automation and production ML are next phases; data contract is ready.

**Request:** Sandbox pilot with reserve boundaries + NDVI/canopy data for 1–2 sites; guidance on Indian geospatial sources and data-sharing protocols.

**Contact:** Arjun Tyagi · [add email] · [add repo URL]
