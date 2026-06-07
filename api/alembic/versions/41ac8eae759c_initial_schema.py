"""initial_schema

Revision ID: 41ac8eae759c
Revises: 
Create Date: 2026-06-06 00:36:26.358400

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41ac8eae759c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite Schema
        op.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER REFERENCES organizations(id),
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS organization_invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                email TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                token TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                invited_by_user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL,
                accepted_at TEXT
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS regions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                name TEXT NOT NULL,
                description TEXT,
                boundary_geojson TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                region_id INTEGER REFERENCES regions(id),
                name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                installed_at TEXT,
                last_heard_at TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS audio_clips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                sensor_id INTEGER REFERENCES sensors(id),
                captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                file_url TEXT NOT NULL,
                duration_seconds REAL,
                sample_rate INTEGER,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS audio_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clip_id INTEGER NOT NULL REFERENCES audio_clips(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id),
                label TEXT NOT NULL,
                confidence REAL,
                labeled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS satellite_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region_id INTEGER REFERENCES regions(id),
                capture_date TEXT NOT NULL,
                ndvi_raster_url TEXT,
                thumbnail_url TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS satellite_change_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                region_id INTEGER REFERENCES regions(id),
                source TEXT NOT NULL DEFAULT 'manual',
                change_type TEXT NOT NULL DEFAULT 'unknown',
                severity_score REAL NOT NULL,
                confidence REAL NOT NULL,
                baseline_start TEXT,
                baseline_end TEXT,
                observation_start TEXT,
                observation_end TEXT,
                description TEXT,
                latitude REAL,
                longitude REAL,
                geometry_geojson TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS ndvi_ingestion_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                region_id INTEGER REFERENCES regions(id),
                uploaded_by_user_id INTEGER NOT NULL REFERENCES users(id),
                source_type TEXT NOT NULL DEFAULT 'csv',
                filename TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                row_count INTEGER NOT NULL DEFAULT 0,
                created_change_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                sensor_id INTEGER REFERENCES sensors(id),
                satellite_image_id INTEGER REFERENCES satellite_images(id),
                region_id INTEGER REFERENCES regions(id),
                type TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'open',
                status_note TEXT,
                classifier_label TEXT,
                classifier_confidence REAL,
                classifier_model_version TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                reported_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Indexes for SQLite
        op.execute("CREATE INDEX IF NOT EXISTS idx_invites_org ON organization_invites (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_invites_token ON organization_invites (token);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_regions_org ON regions (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_sensors_org ON sensors (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_sensors_lat_lon ON sensors (lat, lon);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_audio_clips_org ON audio_clips (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_satellite_changes_org ON satellite_change_events (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_ndvi_batches_org ON ndvi_ingestion_batches (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_satellite_changes_lat_lon ON satellite_change_events (latitude, longitude);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_org ON alerts (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_lat_lon ON alerts (lat, lon);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status_created_at ON alerts (status, created_at DESC);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts (type);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_audio_clips_sensor_captured_at ON audio_clips (sensor_id, captured_at DESC);")

    else:
        # PostgreSQL / PostGIS Schema
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        op.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        op.execute("""
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
        """)
        op.execute("""
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
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS regions (
                id BIGSERIAL PRIMARY KEY,
                org_id BIGINT NOT NULL REFERENCES organizations(id),
                name TEXT NOT NULL,
                description TEXT,
                boundary GEOMETRY(POLYGON, 4326),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        op.execute("""
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
        """)
        op.execute("""
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
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS audio_labels (
                id BIGSERIAL PRIMARY KEY,
                clip_id BIGINT NOT NULL REFERENCES audio_clips(id) ON DELETE CASCADE,
                user_id BIGINT REFERENCES users(id),
                label TEXT NOT NULL,
                confidence NUMERIC,
                labeled_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS satellite_images (
                id BIGSERIAL PRIMARY KEY,
                region_id BIGINT REFERENCES regions(id),
                capture_date DATE NOT NULL,
                ndvi_raster_url TEXT,
                thumbnail_url TEXT,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        op.execute("""
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
        """)
        op.execute("""
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
        """)
        op.execute("""
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
        """)
        # Indexes for Postgres
        op.execute("CREATE INDEX IF NOT EXISTS idx_invites_org ON organization_invites (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_invites_token ON organization_invites (token);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_regions_org ON regions (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_regions_boundary ON regions USING GIST (boundary);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_sensors_org ON sensors (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_sensors_location ON sensors USING GIST (location);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_audio_clips_org ON audio_clips (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_satellite_changes_org ON satellite_change_events (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_ndvi_batches_org ON ndvi_ingestion_batches (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_satellite_changes_geometry ON satellite_change_events USING GIST (geometry);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_org ON alerts (org_id);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_location ON alerts USING GIST (location);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status_created_at ON alerts (status, created_at DESC);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts (type);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_audio_clips_sensor_captured_at ON audio_clips (sensor_id, captured_at DESC);")


def downgrade() -> None:
    bind = op.get_bind()
    tables = [
        "alerts",
        "ndvi_ingestion_batches",
        "satellite_change_events",
        "satellite_images",
        "audio_labels",
        "audio_clips",
        "sensors",
        "regions",
        "organization_invites",
        "users",
        "organizations"
    ]
    for table in tables:
        if bind.dialect.name == "sqlite":
            op.execute(f"DROP TABLE IF EXISTS {table};")
        else:
            op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
    if bind.dialect.name != "sqlite":
        op.execute("DROP EXTENSION IF EXISTS postgis CASCADE;")

