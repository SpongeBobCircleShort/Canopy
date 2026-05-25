# Project Canopy — Executive Summary (One Page)

**Proposer:** Arjun Tyagi, Pennsylvania State University  
**Purpose:** Institutional overview to support a India-focused geospatial data pilot

---

## Problem

Forest departments, NGOs, and research groups monitor large remote areas with limited patrol capacity. Acoustic sensing (illegal logging, gunshots, vehicles) and satellite vegetation indices (NDVI / canopy change) are typically analyzed in **separate systems**, increasing false alarms and delaying response.

## Approach

**Canopy** is an open-source platform that:

1. Ingests **geolocated acoustic events** from forest listening units  
2. Ingests **vegetation-change signals** (NDVI comparisons → satellite change events)  
3. **Fuses** acoustic and geospatial signals by **location and time** into prioritized alerts  
4. Presents alerts on a **map dashboard** with **audit-ready CSV export** and organization-scoped access control  

## Technical foundation

- **Database:** PostgreSQL + PostGIS (SRID 4326, bbox queries, region polygons)  
- **Backend:** FastAPI with org-scoped RBAC  
- **Frontend:** React + Leaflet map dashboard  
- **Fusion:** Configurable distance (e.g. 500 m) and time window (e.g. 14 days); scored alerts with full provenance in exports  

## Current maturity

| Delivered | Planned |
|-----------|---------|
| Working MVP with demo | Live Sentinel / Bhuvan automation |
| NDVI CSV → satellite events | Production acoustic ML in API |
| Rule-based fusion + CSV export | Notifications, QGIS plugin, scale |

A technical demonstration has been completed. The platform is ready for **real geospatial pilot data**.

## India relevance

Designed for government and NGO workflows: batch NDVI ingestion, low-bandwidth operation, exportable metadata, open architecture suitable for NIC or state-forest collaboration.

## Data request (pilot)

**Minimum:** 1–2 protected-area boundaries (GeoJSON/SHP) + NDVI or canopy-change time series (CSV, GeoTIFF, or API)  
**Optional:** Historical disturbance records, land-cover context, existing sensor locations  
**Use:** Sandbox pilot only; org-scoped storage; no redistribution without permission  

## Proposed pilot

- **Scope:** One landscape (state forest or NGO reserve)  
- **Duration:** 6 months  
- **Outcome:** Report on alert quality, fusion benefit vs. single-source monitoring, recommendation to scale or refine  

## Ask

1. Endorsement for a limited geospatial data pilot  
2. Introduction to forest department / NGO data custodians  
3. Guidance on compliant data-sharing pathways  

**Contact:** Arjun Tyagi · [email] · [repository URL]
