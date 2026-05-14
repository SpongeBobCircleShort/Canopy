CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS organizations (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id),
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_invites (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES organizations(id),
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    invited_by_user_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS regions (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    description TEXT,
    boundary GEOMETRY(POLYGON, 4326),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sensors (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES organizations(id),
    region_id BIGINT REFERENCES regions(id),
    name TEXT NOT NULL,
    device_type TEXT NOT NULL,
    location GEOMETRY(POINT, 4326) NOT NULL,
    installed_at TIMESTAMPTZ,
    last_heard_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audio_clips (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES organizations(id),
    sensor_id BIGINT REFERENCES sensors(id),
    captured_at TIMESTAMPTZ NOT NULL,
    file_url TEXT NOT NULL,
    duration_seconds NUMERIC,
    sample_rate INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audio_labels (
    id BIGSERIAL PRIMARY KEY,
    clip_id BIGINT NOT NULL REFERENCES audio_clips(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id),
    label TEXT NOT NULL,
    confidence NUMERIC,
    labeled_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS satellite_images (
    id BIGSERIAL PRIMARY KEY,
    region_id BIGINT REFERENCES regions(id),
    capture_date DATE NOT NULL,
    ndvi_raster_url TEXT,
    thumbnail_url TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS satellite_change_events (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES organizations(id),
    region_id BIGINT REFERENCES regions(id),
    source TEXT NOT NULL DEFAULT 'manual',
    change_type TEXT NOT NULL DEFAULT 'unknown',
    severity_score NUMERIC NOT NULL,
    confidence NUMERIC NOT NULL,
    baseline_start TIMESTAMPTZ,
    baseline_end TIMESTAMPTZ,
    observation_start TIMESTAMPTZ,
    observation_end TIMESTAMPTZ,
    description TEXT,
    latitude NUMERIC,
    longitude NUMERIC,
    geometry GEOMETRY(GEOMETRY, 4326),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE IF NOT EXISTS ndvi_ingestion_batches (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES organizations(id),
    region_id BIGINT REFERENCES regions(id),
    uploaded_by_user_id BIGINT NOT NULL REFERENCES users(id),
    source_type TEXT NOT NULL DEFAULT 'csv',
    filename TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    row_count INTEGER NOT NULL DEFAULT 0,
    created_change_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES organizations(id),
    sensor_id BIGINT REFERENCES sensors(id),
    satellite_image_id BIGINT REFERENCES satellite_images(id),
    region_id BIGINT REFERENCES regions(id),
    type TEXT NOT NULL,
    location GEOMETRY(POINT, 4326) NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    status_note TEXT,
    classifier_label TEXT,
    classifier_confidence NUMERIC,
    classifier_model_version TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    reported_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_invites_org ON organization_invites (org_id);
CREATE INDEX IF NOT EXISTS idx_invites_token ON organization_invites (token);
CREATE INDEX IF NOT EXISTS idx_regions_org ON regions (org_id);
CREATE INDEX IF NOT EXISTS idx_regions_boundary ON regions USING GIST (boundary);
CREATE INDEX IF NOT EXISTS idx_sensors_org ON sensors (org_id);
CREATE INDEX IF NOT EXISTS idx_sensors_location ON sensors USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_audio_clips_org ON audio_clips (org_id);
CREATE INDEX IF NOT EXISTS idx_satellite_changes_org ON satellite_change_events (org_id);
CREATE INDEX IF NOT EXISTS idx_ndvi_batches_org ON ndvi_ingestion_batches (org_id);
CREATE INDEX IF NOT EXISTS idx_satellite_changes_geometry ON satellite_change_events USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_alerts_org ON alerts (org_id);
CREATE INDEX IF NOT EXISTS idx_alerts_location ON alerts USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_alerts_status_created_at ON alerts (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts (type);
CREATE INDEX IF NOT EXISTS idx_audio_clips_sensor_captured_at ON audio_clips (sensor_id, captured_at DESC);
