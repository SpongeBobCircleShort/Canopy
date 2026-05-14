# Canopy Product Specification

Canopy is an open-source, AI-assisted conservation monitoring platform that combines forest acoustic sensing with satellite vegetation analysis to identify threats such as illegal logging, poaching, fire risk, and rapid canopy loss.

## MVP scope

The first implementation focuses on a simple end-to-end monitoring loop:

1. Register forest listening units with geospatial coordinates.
2. Upload or ingest acoustic clips and event metadata.
3. Generate initial audio alerts through a classification stub.
4. Store satellite and NDVI change outputs as planned alert sources.
5. Display sensors and alerts on a responsive React dashboard.
6. Provide export-ready alert data for field teams and researchers.

## Primary users

- Conservation NGO managers who monitor multiple field sites.
- Park rangers who need actionable patrol intelligence.
- Wildlife researchers who need auditable event and sensor data.
- Local community guardians who need simple, low-bandwidth alerts.
- Government analysts who review deforestation and threat patterns.

## Roadmap

- **MVP:** Auth scaffold, sensors, alerts, audio upload stub, map dashboard, PostGIS schema.
- **Version 1:** Real acoustic classification, NDVI processing pipeline, notifications, RBAC, labeling UI.
- **Version 2:** Offline PWA, QGIS plugin, anomaly detection, larger-scale ingestion, external integrations.
