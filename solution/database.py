import sqlite3
from pathlib import Path


def get_connection(db_path="data/interaction_ledger.db"):
    """Create the database folder and return a SQLite connection."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def create_tables(connection):
    """Create the tables used by the data pipeline."""

    connection.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            phone_hash TEXT NOT NULL,
            phone_encrypted TEXT NOT NULL,
            customer_name_encrypted TEXT NOT NULL,
            external_ref TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            lead_data TEXT NOT NULL,
            duplicate_count INTEGER DEFAULT 0,
            UNIQUE(workflow_id, phone_hash)
        );

        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            call_id TEXT,
            workflow_id TEXT,
            phone_hash TEXT,
            occurred_at TEXT,
            payload TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rejected_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            row_number INTEGER NOT NULL,
            reason TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS field_warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            row_number INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            reason TEXT NOT NULL
        );
    """)

    connection.commit()