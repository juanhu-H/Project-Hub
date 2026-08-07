from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .config import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self):
        with self.connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_projects (
                user_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                PRIMARY KEY(user_id, project_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                artifact_type TEXT NOT NULL,
                external_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, artifact_type, external_id)
            );

            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                source_artifact_id INTEGER NOT NULL,
                target_artifact_id INTEGER NOT NULL,
                relation_type TEXT NOT NULL,
                method TEXT NOT NULL,
                confidence REAL NOT NULL,
                evidence TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(source_artifact_id, target_artifact_id, relation_type)
            );

            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                finding_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cycle_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                user_email TEXT,
                event_type TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

    def one(self, query: str, params: tuple = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def all(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def execute(self, query: str, params: tuple = ()) -> int:
        with self.connect() as conn:
            cur = conn.execute(query, params)
            return int(cur.lastrowid or 0)

    def upsert_artifact(self, project_id: int, artifact_type: str, external_id: str,
                        title: str, content: str, metadata: dict, source: str) -> int:
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO artifacts(project_id, artifact_type, external_id, title, content,
                                      metadata_json, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, artifact_type, external_id)
                DO UPDATE SET title=excluded.title, content=excluded.content,
                              metadata_json=excluded.metadata_json, source=excluded.source,
                              updated_at=excluded.updated_at
            """, (project_id, artifact_type, external_id, title, content,
                  json.dumps(metadata, ensure_ascii=False), source, utc_now()))
            row = conn.execute("""
                SELECT id FROM artifacts
                WHERE project_id=? AND artifact_type=? AND external_id=?
            """, (project_id, artifact_type, external_id)).fetchone()
            return int(row["id"])

    def log(self, event_type: str, details: dict, project_id: int | None = None,
            user_email: str | None = None):
        self.execute("""
            INSERT INTO audit_log(project_id, user_email, event_type, details_json, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (project_id, user_email, event_type,
              json.dumps(details, ensure_ascii=False), utc_now()))


db = Database(settings.database_path)
