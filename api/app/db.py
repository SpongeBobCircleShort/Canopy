from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
import sqlite3

from app.config import get_settings


def _database_url() -> str:
    return get_settings().database_url


def is_sqlite() -> bool:
    return _database_url().startswith("sqlite")


def _sqlite_path() -> str:
    parsed = urlparse(_database_url())
    if parsed.path in ("", "/:memory:"):
        return ":memory:"
    path = parsed.path
    if parsed.netloc:
        path = f"/{parsed.netloc}{parsed.path}"
    if path.startswith("/") and not _database_url().startswith("sqlite:////"):
        path = path[1:]
    return path or "canopy.db"


def _postgres_url() -> str:
    return _database_url().replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def connection() -> Iterator:
    if is_sqlite():
        db_path = _sqlite_path()
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
        return

    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(_postgres_url(), row_factory=dict_row) as conn:
        yield conn


def initialize_database() -> None:
    if is_sqlite():
        with connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

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

                CREATE TABLE IF NOT EXISTS regions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL REFERENCES organizations(id),
                    name TEXT NOT NULL,
                    description TEXT,
                    boundary_geojson TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

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

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL REFERENCES organizations(id),
                    sensor_id INTEGER REFERENCES sensors(id),
                    satellite_image_id INTEGER,
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

                CREATE INDEX IF NOT EXISTS idx_invites_org ON organization_invites (org_id);
                CREATE INDEX IF NOT EXISTS idx_invites_token ON organization_invites (token);
                CREATE INDEX IF NOT EXISTS idx_regions_org ON regions (org_id);
                CREATE INDEX IF NOT EXISTS idx_sensors_org ON sensors (org_id);
                CREATE INDEX IF NOT EXISTS idx_sensors_lat_lon ON sensors (lat, lon);
                CREATE INDEX IF NOT EXISTS idx_audio_clips_org ON audio_clips (org_id);
                CREATE INDEX IF NOT EXISTS idx_satellite_changes_org ON satellite_change_events (org_id);
                CREATE INDEX IF NOT EXISTS idx_ndvi_batches_org ON ndvi_ingestion_batches (org_id);
                CREATE INDEX IF NOT EXISTS idx_satellite_changes_lat_lon ON satellite_change_events (latitude, longitude);
                CREATE INDEX IF NOT EXISTS idx_alerts_org ON alerts (org_id);
                CREATE INDEX IF NOT EXISTS idx_alerts_lat_lon ON alerts (lat, lon);
                CREATE INDEX IF NOT EXISTS idx_alerts_status_created_at ON alerts (status, created_at DESC);
                """
            )
        return

    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'organizations');"
        )
        exists = cursor.fetchone()[0] if isinstance(cursor.fetchone(), tuple) else cursor.fetchone().get("exists")
        if not exists:
            migration_path = Path(__file__).resolve().parent.parent / "migrations" / "001_initial_schema.sql"
            if migration_path.exists():
                sql_content = migration_path.read_text()
                cursor.execute(sql_content)
                print("PostgreSQL database initialized successfully.")
            else:
                print(f"PostgreSQL migration script not found at: {migration_path}")

