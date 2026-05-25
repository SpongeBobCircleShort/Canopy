# Fix your Canopy Figma deck (after plugin)

**Easier option:** Use the ready-made HTML deck (same aesthetic): open `canopy-deck.html` in Chrome → Present or export PDF.

---

**First:** In Figma, press **Cmd+Z** many times until slides look like before the plugin ran.  
**Do not run the plugin again** — your deck order doesn’t match the 16-slide institutional template.

Paste only into the text boxes that already exist on each slide. Don’t run bulk updater.

---

## Slide 1 — Title (currently “Earthling”)

**Big title:** Canopy  

**Subtitle / line below:** Integrated geospatial and acoustic monitoring for forest conservation  

**Footer:** Arjun Tyagi · Penn State · Open source  

**Small line:** Overview for institutional review and pilot data support  

*(Keep your tree/brand image; only change words.)*

---

## Slide 2 — If this is “Problem” or intro (green slide)

**Title:** Why this matters for India  

**Bullets:**
- Critical forest carbon and biodiversity under increasing pressure
- Patrol and community guardians cannot cover vast remote areas
- Early, location-specific alerts reduce response time for logging, fire, and encroachment
- Tools must work with existing government and NGO GIS — not replace them

---

## Slide 3 — Agenda

**Title:** Agenda  

**List (replace the broken vertical text):**
1. Problem and monitoring gap
2. Vision and architecture
3. NDVI and acoustic pipelines
4. Fusion and dashboard
5. Pilot status and data request
6. Next steps

---

## Slide 4 — Current Gaps (dark slide, green box)

**Green box title:** Current gaps  

**Box body (short):**
- Satellite-only: cloud, seasonality, late for “right now”
- Acoustic-only: local but easy false alarms
- Separate tools: no shared alert lifecycle or export

**Main column title:** Vision — one platform  

**Bullets (main area, not overlapping the green box):**
1. Deploy geolocated Forest Listening Units
2. Ingest NDVI / vegetation change
3. Fuse by space and time → prioritized alerts
4. Map workflow + CSV export for field teams

---

## Slide 5 — THE SOLUTION (keep your table layout)

**Title:** THE SOLUTION  

**Subtitle:** Canopy combines what satellites see with what forests hear.  

**Row 1 — Satellite Data:** Detects vegetation loss and NDVI/canopy change (CSV today; Sentinel/Bhuvan path planned).  

**Row 2 — Acoustic AI:** Detects chainsaw, gunshot, vehicle, fire crackle (research model; MVP uses demo classifier).  

**Row 3 — Fused alerts:** Links acoustic + satellite events by location and time; scored alerts with provenance in export.  

---

## Slide 6 — CANOPY WORKS (keep your 5 bars)

**Title:** CANOPY WORKS  

**Bar 1:** Sign up · org-scoped regions and sensors  
**Bar 2:** Upload audio clips → acoustic alerts on map  
**Bar 3:** Ingest NDVI CSV → satellite change events  
**Bar 4:** Run fusion → prioritized fused alerts  
**Bar 5:** Export CSV · alert lifecycle for patrols  

---

## Slides 7+ — Add or edit to match institutional deck

If you have more slides, add these as **new slides** (duplicate your template) in this order:

| # | Slide title | Use content from |
|---|-------------|------------------|
| 7 | Geospatial foundation | institutional-overview-slides.md → Slide 7 |
| 8 | NDVI ingestion | Slide 8 |
| 9 | Acoustic detection | Slide 9 |
| 10 | Fusion logic | Slide 10 |
| 11 | Dashboard & governance | Slide 11 |
| 12 | Current status | Slide 12 |
| 13 | Roadmap | Slide 13 |
| 14 | Data request — India pilot | Slide 14 **(critical for Sir)** |
| 15 | 6-month pilot | Slide 15 |
| 16 | Request & next steps | Slide 16 |

Full text for 7–16: `institutional-overview-slides.md`

---

## For Srikanth — minimum viable deck

If short on time, polish only these **6 slides** and export PDF:

1. Title (Canopy + institutional subtitle)  
2. Why India  
3. THE SOLUTION (your table — updated copy above)  
4. CANOPY WORKS (5 bars)  
5. **Data request** (copy Slide 14 from institutional-overview-slides.md)  
6. **Request & next steps** (copy Slide 16)  

Attach `executive-summary-one-pager.md` as a second PDF page or email body.
