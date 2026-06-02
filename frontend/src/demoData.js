const now = new Date().toISOString()

export const demoProfile = {
  id: 1,
  name: 'Demo Ranger',
  email: 'demo@example.org',
  role: 'admin',
  org_id: 1,
  organization: {
    id: 1,
    name: 'Canopy Demo Org',
  },
}

export const demoRegions = [
  {
    id: 1,
    org_id: 1,
    name: 'Demo Sector',
    description: 'Sample patrol area for the public dashboard.',
    boundary: null,
    created_at: now,
    updated_at: now,
  },
]

export const demoSensors = [
  {
    id: 1,
    org_id: 1,
    region_id: 1,
    name: 'FLU-Demo',
    device_type: 'forest-listening-unit',
    location: { lat: 20.5937, lon: 78.9629 },
    status: 'online',
    last_heard_at: now,
  },
]

export const demoSatelliteChanges = [
  {
    id: 1,
    org_id: 1,
    region_id: 1,
    source: 'csv_ndvi',
    change_type: 'ndvi_drop',
    severity_score: 0.48,
    confidence: 0.9,
    latitude: 20.5938,
    longitude: 78.963,
    description: 'Canopy loss near FLU-Demo acoustic sensor',
    metadata: { baseline_ndvi: 0.72, recent_ndvi: 0.48, ndvi_delta: -0.24, ingestion_batch_id: 1 },
    created_at: now,
    updated_at: now,
  },
  {
    id: 2,
    org_id: 1,
    region_id: 1,
    source: 'csv_ndvi',
    change_type: 'ndvi_drop',
    severity_score: 0.56,
    confidence: 0.88,
    latitude: 20.5932,
    longitude: 78.9623,
    description: 'High severity vegetation drop near demo sensor',
    metadata: { baseline_ndvi: 0.68, recent_ndvi: 0.4, ndvi_delta: -0.28, ingestion_batch_id: 1 },
    created_at: now,
    updated_at: now,
  },
]

export const demoAlerts = [
  {
    id: 2,
    org_id: 1,
    type: 'fusion',
    status: 'investigating',
    priority: 'medium',
    description: "Fusion alert: acoustic evidence 'chainsaw' matched satellite change 'ndvi_drop' within 16m.",
    location: { lat: 20.5937, lon: 78.9629 },
    sensor_id: 1,
    region_id: 1,
    classifier_label: 'chainsaw',
    classifier_confidence: 0.82,
    classifier_model_version: 'placeholder-v0',
    metadata: {
      acoustic_alert_id: 1,
      satellite_change_id: 1,
      acoustic_confidence: 0.82,
      acoustic_confidence_threshold: 0.65,
      acoustic_suppressed: false,
      acoustic_weight: 0.45,
      satellite_severity_score: 0.48,
      satellite_confidence: 0.9,
      distance_meters: 15.71,
      fusion_score: 0.637,
      fusion_scoring_mode: 'acoustic_satellite',
      fusion_rule_version: 'rule-fusion-v1',
      baseline_ndvi: 0.72,
      recent_ndvi: 0.48,
      ndvi_delta: -0.24,
      ingestion_batch_id: 1,
    },
    created_at: now,
    updated_at: now,
  },
  {
    id: 1,
    org_id: 1,
    type: 'audio',
    status: 'open',
    priority: 'high',
    description: "Audio classifier detected 'chainsaw' with 82% confidence.",
    location: { lat: 20.5937, lon: 78.9629 },
    sensor_id: 1,
    region_id: 1,
    classifier_label: 'chainsaw',
    classifier_confidence: 0.82,
    classifier_model_version: 'placeholder-v0',
    metadata: {},
    created_at: now,
    updated_at: now,
  },
]

export const demoNdviBatches = [
  {
    id: 1,
    org_id: 1,
    region_id: 1,
    source_type: 'csv',
    filename: 'ndvi_sample_current_window.csv',
    status: 'processed',
    row_count: 6,
    created_change_count: 2,
    created_at: now,
  },
]

export const demoInvites = []

export function freshDemoState() {
  return {
    profile: structuredClone(demoProfile),
    regions: structuredClone(demoRegions),
    sensors: structuredClone(demoSensors),
    alerts: structuredClone(demoAlerts),
    satelliteChanges: structuredClone(demoSatelliteChanges),
    ndviBatches: structuredClone(demoNdviBatches),
    invites: structuredClone(demoInvites),
  }
}
