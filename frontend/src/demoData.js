function daysAgo(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString()
}

export const demoProfile = {
  id: 1,
  name: 'Demo Ranger',
  email: 'demo@example.org',
  role: 'admin',
  org_id: 1,
  organization: { id: 1, name: 'Canopy Demo Org' },
}

export const demoRegions = [
  {
    id: 1, org_id: 1,
    name: 'Kanha — Banjar Corridor',
    description: 'Kanha Tiger Reserve buffer, Madhya Pradesh — primary logging pressure vector.',
    boundary: null,
    created_at: daysAgo(90), updated_at: daysAgo(1),
  },
  {
    id: 2, org_id: 1,
    name: 'Similipal — Meghasani',
    description: 'Similipal Tiger Reserve buffer zone, Odisha.',
    boundary: null,
    created_at: daysAgo(85), updated_at: daysAgo(2),
  },
  {
    id: 3, org_id: 1,
    name: 'Nagarhole — Kabini',
    description: 'Nagarhole National Park — southwestern edge surveillance, Western Ghats.',
    boundary: null,
    created_at: daysAgo(80), updated_at: daysAgo(3),
  },
]

export const demoSensors = [
  {
    id: 1, org_id: 1, region_id: 1,
    name: 'KNH-01', device_type: 'forest-listening-unit',
    location: { lat: 22.300, lon: 80.600 },
    status: 'online', last_heard_at: daysAgo(0),
  },
  {
    id: 2, org_id: 1, region_id: 1,
    name: 'KNH-02', device_type: 'forest-listening-unit',
    location: { lat: 22.375, lon: 80.475 },
    status: 'offline', last_heard_at: daysAgo(4),
  },
  {
    id: 3, org_id: 1, region_id: 2,
    name: 'SML-01', device_type: 'acoustic-logger',
    location: { lat: 21.600, lon: 86.300 },
    status: 'online', last_heard_at: daysAgo(0),
  },
  {
    id: 4, org_id: 1, region_id: 2,
    name: 'SML-02', device_type: 'acoustic-logger',
    location: { lat: 21.426, lon: 86.436 },
    status: 'online', last_heard_at: daysAgo(0),
  },
  {
    id: 5, org_id: 1, region_id: 3,
    name: 'NGH-01', device_type: 'forest-listening-unit',
    location: { lat: 12.000, lon: 76.100 },
    status: 'online', last_heard_at: daysAgo(0),
  },
]

export const demoSatelliteChanges = [
  // Kanha — progressive degradation
  {
    id: 1, org_id: 1, region_id: 1, source: 'csv_ndvi', change_type: 'ndvi_drop',
    severity_score: 0.31, confidence: 0.88,
    latitude: 22.302, longitude: 80.596,
    description: 'Early canopy thinning, northwest Kanha buffer grid A3',
    metadata: { baseline_ndvi: 0.74, recent_ndvi: 0.61, ndvi_delta: -0.13, ingestion_batch_id: 1 },
    created_at: daysAgo(78), updated_at: daysAgo(78),
  },
  {
    id: 2, org_id: 1, region_id: 1, source: 'csv_ndvi', change_type: 'ndvi_drop',
    severity_score: 0.44, confidence: 0.91,
    latitude: 22.297, longitude: 80.603,
    description: 'Canopy loss accelerating — grid A3 southeast corner',
    metadata: { baseline_ndvi: 0.74, recent_ndvi: 0.52, ndvi_delta: -0.22, ingestion_batch_id: 1 },
    created_at: daysAgo(52), updated_at: daysAgo(52),
  },
  {
    id: 3, org_id: 1, region_id: 1, source: 'csv_ndvi', change_type: 'ndvi_drop',
    severity_score: 0.63, confidence: 0.93,
    latitude: 22.290, longitude: 80.609,
    description: 'Significant vegetation loss, probable road clearing',
    metadata: { baseline_ndvi: 0.74, recent_ndvi: 0.41, ndvi_delta: -0.33, ingestion_batch_id: 1 },
    created_at: daysAgo(28), updated_at: daysAgo(28),
  },
  {
    id: 4, org_id: 1, region_id: 1, source: 'csv_ndvi', change_type: 'ndvi_drop',
    severity_score: 0.79, confidence: 0.95,
    latitude: 22.284, longitude: 80.616,
    description: 'Critical deforestation front — 2.1 ha cleared in 14 days',
    metadata: { baseline_ndvi: 0.74, recent_ndvi: 0.29, ndvi_delta: -0.45, ingestion_batch_id: 1 },
    created_at: daysAgo(7), updated_at: daysAgo(7),
  },
  // Similipal — Sentinel-2 + CSV
  {
    id: 5, org_id: 1, region_id: 2, source: 'sentinel_2', change_type: 'canopy_loss',
    severity_score: 0.38, confidence: 0.82,
    latitude: 21.596, longitude: 86.303,
    description: 'Sentinel-2 canopy loss detection, Similipal buffer boundary',
    metadata: { baseline_ndvi: 0.71, recent_ndvi: 0.58, ndvi_delta: -0.13, ingestion_batch_id: 2 },
    created_at: daysAgo(68), updated_at: daysAgo(68),
  },
  {
    id: 6, org_id: 1, region_id: 2, source: 'sentinel_2', change_type: 'canopy_loss',
    severity_score: 0.52, confidence: 0.87,
    latitude: 21.589, longitude: 86.289,
    description: 'Expanding clearing footprint — Similipal grid B7',
    metadata: { baseline_ndvi: 0.71, recent_ndvi: 0.47, ndvi_delta: -0.24, ingestion_batch_id: 2 },
    created_at: daysAgo(41), updated_at: daysAgo(41),
  },
  {
    id: 7, org_id: 1, region_id: 2, source: 'csv_ndvi', change_type: 'ndvi_drop',
    severity_score: 0.67, confidence: 0.90,
    latitude: 21.423, longitude: 86.440,
    description: 'High-severity drop near SML-02 — possible encroachment clearing',
    metadata: { baseline_ndvi: 0.68, recent_ndvi: 0.38, ndvi_delta: -0.30, ingestion_batch_id: 2 },
    created_at: daysAgo(19), updated_at: daysAgo(19),
  },
  {
    id: 8, org_id: 1, region_id: 2, source: 'csv_ndvi', change_type: 'ndvi_drop',
    severity_score: 0.84, confidence: 0.94,
    latitude: 21.419, longitude: 86.446,
    description: 'Critical: 4.3 ha bare soil visible in latest mosaic',
    metadata: { baseline_ndvi: 0.68, recent_ndvi: 0.22, ndvi_delta: -0.46, ingestion_batch_id: 2 },
    created_at: daysAgo(5), updated_at: daysAgo(5),
  },
  // Nagarhole — park boundary surveillance
  {
    id: 9, org_id: 1, region_id: 3, source: 'sentinel_2', change_type: 'canopy_loss',
    severity_score: 0.29, confidence: 0.80,
    latitude: 11.995, longitude: 76.105,
    description: 'Low-severity fragmentation near Nagarhole park boundary',
    metadata: { baseline_ndvi: 0.76, recent_ndvi: 0.65, ndvi_delta: -0.11, ingestion_batch_id: 3 },
    created_at: daysAgo(72), updated_at: daysAgo(72),
  },
  {
    id: 10, org_id: 1, region_id: 3, source: 'csv_ndvi', change_type: 'ndvi_drop',
    severity_score: 0.41, confidence: 0.85,
    latitude: 12.003, longitude: 76.092,
    description: 'Selective logging trail identified — Nagarhole southwest',
    metadata: { baseline_ndvi: 0.76, recent_ndvi: 0.55, ndvi_delta: -0.21, ingestion_batch_id: 3 },
    created_at: daysAgo(44), updated_at: daysAgo(44),
  },
  {
    id: 11, org_id: 1, region_id: 3, source: 'csv_ndvi', change_type: 'ndvi_drop',
    severity_score: 0.55, confidence: 0.89,
    latitude: 12.007, longitude: 76.081,
    description: 'Sustained canopy loss — 3 consecutive passes confirm activity',
    metadata: { baseline_ndvi: 0.76, recent_ndvi: 0.45, ndvi_delta: -0.31, ingestion_batch_id: 3 },
    created_at: daysAgo(21), updated_at: daysAgo(21),
  },
  {
    id: 12, org_id: 1, region_id: 3, source: 'sentinel_2', change_type: 'canopy_loss',
    severity_score: 0.72, confidence: 0.92,
    latitude: 12.011, longitude: 76.073,
    description: 'High severity — chainsaws and vehicle audio corroborating',
    metadata: { baseline_ndvi: 0.76, recent_ndvi: 0.34, ndvi_delta: -0.42, ingestion_batch_id: 3 },
    created_at: daysAgo(3), updated_at: daysAgo(3),
  },
]

export const demoAlerts = [
  // === OPEN-SET ANOMALY DETECTOR ===
  // Catch-all acoustic detector: flags deviation from normal forest background,
  // then reports a likelihood of what the anomaly seems to be (incl. "unknown").
  {
    id: 101, org_id: 1, type: 'anomaly', status: 'open', priority: 'high',
    description: 'Anomalous sound detected (94%) — likely chainsaw (71%) near KNH-01.',
    location: { lat: 22.298, lon: 80.601 },
    sensor_id: 1, region_id: 1,
    classifier_label: 'chainsaw', classifier_confidence: 0.71,
    classifier_model_version: 'anomaly-v1',
    metadata: {
      anomaly_score: 0.94, is_anomaly: true, predicted_kind: 'chainsaw',
      likelihoods: { chainsaw: 0.71, vehicle: 0.12, unknown: 0.17 },
      model_version: 'anomaly-v1',
    },
    created_at: daysAgo(1), updated_at: daysAgo(1),
  },
  {
    id: 102, org_id: 1, type: 'anomaly', status: 'investigating', priority: 'medium',
    description: 'Anomalous sound detected (88%) — unrecognized source (unknown 64%) near SML-01.',
    location: { lat: 21.605, lon: 86.293 },
    sensor_id: 3, region_id: 2,
    classifier_label: 'unknown', classifier_confidence: 0.64,
    classifier_model_version: 'anomaly-v1',
    metadata: {
      anomaly_score: 0.88, is_anomaly: true, predicted_kind: 'unknown',
      likelihoods: { unknown: 0.64, vehicle: 0.21, chainsaw: 0.15 },
      model_version: 'anomaly-v1',
    },
    created_at: daysAgo(2), updated_at: daysAgo(1),
  },
  // === KANHA THREAD ===
  {
    id: 1, org_id: 1, type: 'audio', status: 'resolved', priority: 'medium',
    description: "Audio classifier detected 'chainsaw' with 78% confidence near KNH-01.",
    location: { lat: 22.300, lon: 80.600 },
    sensor_id: 1, region_id: 1,
    classifier_label: 'chainsaw', classifier_confidence: 0.78,
    classifier_model_version: 'placeholder-v0',
    metadata: {},
    created_at: daysAgo(77), updated_at: daysAgo(74),
  },
  {
    id: 2, org_id: 1, type: 'fusion', status: 'resolved', priority: 'medium',
    description: "Fusion alert: acoustic 'chainsaw' at KNH-01 corroborated by NDVI drop in grid A3 (score 0.54).",
    location: { lat: 22.301, lon: 80.598 },
    sensor_id: 1, region_id: 1,
    classifier_label: 'chainsaw', classifier_confidence: 0.78,
    classifier_model_version: 'placeholder-v0',
    metadata: {
      acoustic_alert_id: 1, satellite_change_id: 1,
      acoustic_confidence: 0.78, acoustic_confidence_threshold: 0.65,
      acoustic_suppressed: false, acoustic_weight: 0.45,
      satellite_severity_score: 0.31, satellite_confidence: 0.88,
      distance_meters: 21.4,
      fusion_score: 0.541, fusion_scoring_mode: 'acoustic_satellite',
      fusion_rule_version: 'rule-fusion-v2',
      temporal_decay: 0.91, spatial_decay: 0.88,
      time_decay_halflife_days: 7.0, spatial_sigma_meters: 200.0,
      corroborating_change_count: 1, source_quality_multiplier: 1.05,
      baseline_ndvi: 0.74, recent_ndvi: 0.61, ndvi_delta: -0.13, ingestion_batch_id: 1,
    },
    created_at: daysAgo(76), updated_at: daysAgo(70),
  },
  {
    id: 3, org_id: 1, type: 'audio', status: 'acknowledged', priority: 'high',
    description: "Audio classifier detected 'vehicle' (logging truck) with 85% confidence near KNH-01.",
    location: { lat: 22.299, lon: 80.602 },
    sensor_id: 1, region_id: 1,
    classifier_label: 'vehicle', classifier_confidence: 0.85,
    classifier_model_version: 'placeholder-v0',
    metadata: {},
    created_at: daysAgo(27), updated_at: daysAgo(25),
  },
  {
    id: 4, org_id: 1, type: 'fusion', status: 'investigating', priority: 'critical',
    description: "CRITICAL: Chainsaw + vehicle acoustic cluster corroborated by 2 satellite changes (score 0.87). Active deforestation front confirmed.",
    location: { lat: 22.293, lon: 80.605 },
    sensor_id: 1, region_id: 1,
    classifier_label: 'chainsaw', classifier_confidence: 0.91,
    classifier_model_version: 'placeholder-v0',
    metadata: {
      acoustic_alert_id: 3, satellite_change_id: 4,
      acoustic_confidence: 0.91, acoustic_confidence_threshold: 0.65,
      acoustic_suppressed: false, acoustic_weight: 0.45,
      satellite_severity_score: 0.79, satellite_confidence: 0.95,
      distance_meters: 14.2,
      fusion_score: 0.874, fusion_scoring_mode: 'acoustic_satellite',
      fusion_rule_version: 'rule-fusion-v2',
      temporal_decay: 0.97, spatial_decay: 0.96,
      time_decay_halflife_days: 7.0, spatial_sigma_meters: 200.0,
      corroborating_change_count: 2, source_quality_multiplier: 1.15,
      baseline_ndvi: 0.74, recent_ndvi: 0.29, ndvi_delta: -0.45, ingestion_batch_id: 1,
    },
    created_at: daysAgo(6), updated_at: daysAgo(1),
  },

  // === SIMILIPAL THREAD ===
  {
    id: 5, org_id: 1, type: 'audio', status: 'open', priority: 'high',
    description: "Audio classifier detected 'gunshot' with 88% confidence near SML-01. Possible illegal hunting or land conflict.",
    location: { lat: 21.598, lon: 86.302 },
    sensor_id: 3, region_id: 2,
    classifier_label: 'gunshot', classifier_confidence: 0.88,
    classifier_model_version: 'placeholder-v0',
    metadata: {},
    created_at: daysAgo(40), updated_at: daysAgo(40),
  },
  {
    id: 6, org_id: 1, type: 'fusion', status: 'acknowledged', priority: 'high',
    description: "Fusion alert: gunshot event at SML-01 spatially coincides with expanding canopy clearance (score 0.69).",
    location: { lat: 21.595, lon: 86.295 },
    sensor_id: 3, region_id: 2,
    classifier_label: 'gunshot', classifier_confidence: 0.88,
    classifier_model_version: 'placeholder-v0',
    metadata: {
      acoustic_alert_id: 5, satellite_change_id: 6,
      acoustic_confidence: 0.88, acoustic_confidence_threshold: 0.65,
      acoustic_suppressed: false, acoustic_weight: 0.45,
      satellite_severity_score: 0.52, satellite_confidence: 0.87,
      distance_meters: 38.1,
      fusion_score: 0.692, fusion_scoring_mode: 'acoustic_satellite',
      fusion_rule_version: 'rule-fusion-v2',
      temporal_decay: 0.85, spatial_decay: 0.79,
      time_decay_halflife_days: 7.0, spatial_sigma_meters: 200.0,
      corroborating_change_count: 1, source_quality_multiplier: 1.08,
      baseline_ndvi: 0.71, recent_ndvi: 0.47, ndvi_delta: -0.24, ingestion_batch_id: 2,
    },
    created_at: daysAgo(39), updated_at: daysAgo(35),
  },
  {
    id: 7, org_id: 1, type: 'audio', status: 'open', priority: 'high',
    description: "Audio classifier detected 'chainsaw' with 92% confidence at SML-02. Continuous operation >20 min.",
    location: { lat: 21.424, lon: 86.438 },
    sensor_id: 4, region_id: 2,
    classifier_label: 'chainsaw', classifier_confidence: 0.92,
    classifier_model_version: 'placeholder-v0',
    metadata: {},
    created_at: daysAgo(18), updated_at: daysAgo(18),
  },
  {
    id: 8, org_id: 1, type: 'fusion', status: 'open', priority: 'critical',
    description: "CRITICAL: Continuous chainsaw at SML-02 fused with 84% NDVI severity. Immediate intervention required (score 0.91).",
    location: { lat: 21.422, lon: 86.443 },
    sensor_id: 4, region_id: 2,
    classifier_label: 'chainsaw', classifier_confidence: 0.92,
    classifier_model_version: 'placeholder-v0',
    metadata: {
      acoustic_alert_id: 7, satellite_change_id: 8,
      acoustic_confidence: 0.92, acoustic_confidence_threshold: 0.65,
      acoustic_suppressed: false, acoustic_weight: 0.45,
      satellite_severity_score: 0.84, satellite_confidence: 0.94,
      distance_meters: 9.7,
      fusion_score: 0.913, fusion_scoring_mode: 'acoustic_satellite',
      fusion_rule_version: 'rule-fusion-v2',
      temporal_decay: 0.98, spatial_decay: 0.98,
      time_decay_halflife_days: 7.0, spatial_sigma_meters: 200.0,
      corroborating_change_count: 2, source_quality_multiplier: 1.18,
      baseline_ndvi: 0.68, recent_ndvi: 0.22, ndvi_delta: -0.46, ingestion_batch_id: 2,
    },
    created_at: daysAgo(4), updated_at: daysAgo(4),
  },

  // === NAGARHOLE THREAD ===
  {
    id: 9, org_id: 1, type: 'audio', status: 'resolved', priority: 'low',
    description: "Audio classifier detected 'fire_crackle' with 71% confidence near NGH-01. Likely controlled burn.",
    location: { lat: 11.998, lon: 76.102 },
    sensor_id: 5, region_id: 3,
    classifier_label: 'fire_crackle', classifier_confidence: 0.71,
    classifier_model_version: 'placeholder-v0',
    metadata: {},
    created_at: daysAgo(71), updated_at: daysAgo(68),
  },
  {
    id: 10, org_id: 1, type: 'audio', status: 'open', priority: 'medium',
    description: "Audio classifier detected 'chainsaw' with 80% confidence at NGH-01.",
    location: { lat: 12.001, lon: 76.098 },
    sensor_id: 5, region_id: 3,
    classifier_label: 'chainsaw', classifier_confidence: 0.80,
    classifier_model_version: 'placeholder-v0',
    metadata: {},
    created_at: daysAgo(43), updated_at: daysAgo(43),
  },
  {
    id: 11, org_id: 1, type: 'fusion', status: 'investigating', priority: 'high',
    description: "Fusion alert: chainsaw at NGH-01 matched selective logging NDVI signature (score 0.72). Patrol dispatched.",
    location: { lat: 12.002, lon: 76.095 },
    sensor_id: 5, region_id: 3,
    classifier_label: 'chainsaw', classifier_confidence: 0.80,
    classifier_model_version: 'placeholder-v0',
    metadata: {
      acoustic_alert_id: 10, satellite_change_id: 10,
      acoustic_confidence: 0.80, acoustic_confidence_threshold: 0.65,
      acoustic_suppressed: false, acoustic_weight: 0.45,
      satellite_severity_score: 0.41, satellite_confidence: 0.85,
      distance_meters: 31.5,
      fusion_score: 0.718, fusion_scoring_mode: 'acoustic_satellite',
      fusion_rule_version: 'rule-fusion-v2',
      temporal_decay: 0.88, spatial_decay: 0.83,
      time_decay_halflife_days: 7.0, spatial_sigma_meters: 200.0,
      corroborating_change_count: 1, source_quality_multiplier: 1.07,
      baseline_ndvi: 0.76, recent_ndvi: 0.55, ndvi_delta: -0.21, ingestion_batch_id: 3,
    },
    created_at: daysAgo(42), updated_at: daysAgo(38),
  },
  {
    id: 12, org_id: 1, type: 'audio', status: 'open', priority: 'medium',
    description: "Audio classifier detected 'vehicle' (heavy machinery) with 83% confidence at NGH-01.",
    location: { lat: 12.004, lon: 76.088 },
    sensor_id: 5, region_id: 3,
    classifier_label: 'vehicle', classifier_confidence: 0.83,
    classifier_model_version: 'placeholder-v0',
    metadata: {},
    created_at: daysAgo(20), updated_at: daysAgo(20),
  },
  {
    id: 13, org_id: 1, type: 'fusion', status: 'open', priority: 'high',
    description: "Fusion alert: sustained machinery at NGH-01 corroborates 55% severity canopy loss (score 0.78). Third detection in 21 days.",
    location: { lat: 12.006, lon: 76.084 },
    sensor_id: 5, region_id: 3,
    classifier_label: 'vehicle', classifier_confidence: 0.83,
    classifier_model_version: 'placeholder-v0',
    metadata: {
      acoustic_alert_id: 12, satellite_change_id: 11,
      acoustic_confidence: 0.83, acoustic_confidence_threshold: 0.65,
      acoustic_suppressed: false, acoustic_weight: 0.45,
      satellite_severity_score: 0.55, satellite_confidence: 0.89,
      distance_meters: 18.3,
      fusion_score: 0.783, fusion_scoring_mode: 'acoustic_satellite',
      fusion_rule_version: 'rule-fusion-v2',
      temporal_decay: 0.93, spatial_decay: 0.91,
      time_decay_halflife_days: 7.0, spatial_sigma_meters: 200.0,
      corroborating_change_count: 3, source_quality_multiplier: 1.12,
      baseline_ndvi: 0.76, recent_ndvi: 0.45, ndvi_delta: -0.31, ingestion_batch_id: 3,
    },
    created_at: daysAgo(19), updated_at: daysAgo(14),
  },
  {
    id: 14, org_id: 1, type: 'fusion', status: 'open', priority: 'critical',
    description: "CRITICAL: 72% severity Sentinel-2 detection fused with chainsaw audio at NGH-01 (score 0.86). Deforestation front now 3.8 ha.",
    location: { lat: 12.009, lon: 76.076 },
    sensor_id: 5, region_id: 3,
    classifier_label: 'chainsaw', classifier_confidence: 0.89,
    classifier_model_version: 'placeholder-v0',
    metadata: {
      acoustic_alert_id: 10, satellite_change_id: 12,
      acoustic_confidence: 0.89, acoustic_confidence_threshold: 0.65,
      acoustic_suppressed: false, acoustic_weight: 0.45,
      satellite_severity_score: 0.72, satellite_confidence: 0.92,
      distance_meters: 12.8,
      fusion_score: 0.861, fusion_scoring_mode: 'acoustic_satellite',
      fusion_rule_version: 'rule-fusion-v2',
      temporal_decay: 0.96, spatial_decay: 0.95,
      time_decay_halflife_days: 7.0, spatial_sigma_meters: 200.0,
      corroborating_change_count: 2, source_quality_multiplier: 1.14,
      baseline_ndvi: 0.76, recent_ndvi: 0.34, ndvi_delta: -0.42, ingestion_batch_id: 3,
    },
    created_at: daysAgo(2), updated_at: daysAgo(2),
  },
  // Satellite-only (no acoustic corroboration)
  {
    id: 15, org_id: 1, type: 'satellite', status: 'open', priority: 'medium',
    description: "Satellite-only: NDVI drop 0.24 in Similipal buffer zone (grid B5) — no acoustic sensor coverage. Ground verification needed.",
    location: { lat: 21.580, lon: 86.276 },
    sensor_id: null, region_id: 2,
    classifier_label: null, classifier_confidence: null, classifier_model_version: null,
    metadata: { satellite_change_id: 5, satellite_severity_score: 0.38, ingestion_batch_id: 2 },
    created_at: daysAgo(67), updated_at: daysAgo(67),
  },
  {
    id: 16, org_id: 1, type: 'satellite', status: 'acknowledged', priority: 'low',
    description: "Satellite-only: low-severity fragmentation in Nagarhole northwest (grid C2). Monitoring scheduled.",
    location: { lat: 11.992, lon: 76.108 },
    sensor_id: null, region_id: 3,
    classifier_label: null, classifier_confidence: null, classifier_model_version: null,
    metadata: { satellite_change_id: 9, satellite_severity_score: 0.29, ingestion_batch_id: 3 },
    created_at: daysAgo(71), updated_at: daysAgo(65),
  },
]

export const demoNdviBatches = [
  {
    id: 1, org_id: 1, region_id: 1,
    source_type: 'csv', filename: 'kanha_ndvi_q3.csv',
    status: 'processed', row_count: 48, created_change_count: 4,
    created_at: daysAgo(78),
  },
  {
    id: 2, org_id: 1, region_id: 2,
    source_type: 'sentinel_2', filename: 'similipal_sentinel2_mosaic.csv',
    status: 'processed', row_count: 62, created_change_count: 4,
    created_at: daysAgo(68),
  },
  {
    id: 3, org_id: 1, region_id: 3,
    source_type: 'csv', filename: 'nagarhole_ndvi_patrol_upload.csv',
    status: 'processed', row_count: 55, created_change_count: 4,
    created_at: daysAgo(72),
  },
]

export const demoInvites = []

// ── India forest-loss NDVI overlay ──────────────────────────────────────────
// Representative Sentinel-2-derived NDVI grid spanning India's major forest
// belts: Western Ghats, Central Indian highlands, Eastern Ghats, the Northeast,
// Himalayan foothills, Gir, and the Sundarbans. Each cell carries baseline vs
// recent NDVI; ndvi_delta < 0 is canopy loss. Loss concentrates near each
// landscape's core, scaled by an intensity factor, with healthy forest at the
// peripheries — so the overlay reads as nationwide monitoring with realistic
// regional hotspots.
const INDIA_FOREST_LANDSCAPES = [
  // Western Ghats belt
  { name: 'Western Ghats — Nilgiris', lat: 11.40, lon: 76.70, intensity: 0.95 },
  { name: 'Anamalai — Tamil Nadu', lat: 10.35, lon: 77.00, intensity: 0.55 },
  { name: 'Nagarhole — Karnataka', lat: 12.00, lon: 76.10, intensity: 0.62 },
  { name: 'Kudremukh — Karnataka', lat: 13.50, lon: 75.10, intensity: 0.48 },
  { name: 'Sahyadri — Maharashtra', lat: 17.90, lon: 73.70, intensity: 0.40 },
  // Central Indian highlands
  { name: 'Kanha — Madhya Pradesh', lat: 22.30, lon: 80.60, intensity: 0.42 },
  { name: 'Bandhavgarh — Madhya Pradesh', lat: 23.70, lon: 81.00, intensity: 0.45 },
  { name: 'Satpura — Madhya Pradesh', lat: 22.50, lon: 78.40, intensity: 0.38 },
  { name: 'Tadoba — Maharashtra', lat: 20.25, lon: 79.30, intensity: 0.52 },
  { name: 'Achanakmar — Chhattisgarh', lat: 22.45, lon: 81.70, intensity: 0.35 },
  // Eastern Ghats & eastern belt
  { name: 'Similipal — Odisha', lat: 21.60, lon: 86.30, intensity: 0.70 },
  { name: 'Saranda — Jharkhand', lat: 22.05, lon: 85.35, intensity: 0.66 },
  { name: 'Papikonda — Andhra Pradesh', lat: 17.55, lon: 81.30, intensity: 0.58 },
  // Northeast
  { name: 'Namdapha — Arunachal', lat: 27.50, lon: 96.40, intensity: 0.85 },
  { name: 'Kaziranga — Assam', lat: 26.60, lon: 93.40, intensity: 0.50 },
  { name: 'Manas — Assam', lat: 26.70, lon: 91.00, intensity: 0.44 },
  { name: 'Garo Hills — Meghalaya', lat: 25.40, lon: 90.30, intensity: 0.74 },
  { name: 'Dampa — Mizoram', lat: 23.70, lon: 92.40, intensity: 0.78 },
  // Himalayan foothills
  { name: 'Corbett — Uttarakhand', lat: 29.55, lon: 78.90, intensity: 0.36 },
  { name: 'Dudhwa — Uttar Pradesh', lat: 28.50, lon: 80.70, intensity: 0.33 },
  // West & coastal
  { name: 'Gir — Gujarat', lat: 21.15, lon: 70.80, intensity: 0.30 },
  { name: 'Sundarbans — West Bengal', lat: 21.95, lon: 88.90, intensity: 0.41 },
]

function buildIndiaNdviCells() {
  const cells = []
  const GRID = 7
  const STEP = 0.09 // ~10 km cells — visible at national zoom
  const half = (GRID - 1) / 2
  let id = 1
  for (const site of INDIA_FOREST_LANDSCAPES) {
    for (let r = 0; r < GRID; r += 1) {
      for (let c = 0; c < GRID; c += 1) {
        const dr = r - half
        const dc = c - half
        const dist = Math.sqrt(dr * dr + dc * dc) / (half * Math.SQRT2)
        // Deterministic pseudo-noise so the overlay is stable across renders/tests.
        const seed = Math.sin((r + 1) * 12.9898 + (c + 1) * 78.233 + site.lat * 3.17) * 43758.5453
        const noise = seed - Math.floor(seed)
        const baseline = 0.74 + 0.14 * (1 - dist) + 0.04 * (noise - 0.5)
        const lossCore = Math.max(0, 1 - dist * 1.35) * site.intensity
        const loss = Math.max(0, lossCore * (0.4 + 0.45 * noise))
        const recent = Math.max(0.05, baseline - loss)
        const delta = Number((recent - baseline).toFixed(3))
        cells.push({
          id,
          site: site.name,
          lat: Number((site.lat + dr * STEP).toFixed(4)),
          lon: Number((site.lon + dc * STEP).toFixed(4)),
          baseline_ndvi: Number(baseline.toFixed(3)),
          recent_ndvi: Number(recent.toFixed(3)),
          ndvi_delta: delta,
          severity: Number(Math.min(Math.abs(delta) / 0.5, 1).toFixed(3)),
          cell_size_deg: STEP,
        })
        id += 1
      }
    }
  }
  return cells
}

export const demoIndiaNdviCells = buildIndiaNdviCells()

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
