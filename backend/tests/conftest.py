import os
import tempfile

# Los módulos de la app leen la configuración al importarse por primera vez,
# así que la DB de test tiene que quedar fijada ANTES de cualquier `from app...`
# (acá o en cualquier test), para no tocar la base real del proyecto (pih.db).
_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix=".db", prefix="pih_test_")
os.close(_tmp_db_fd)
os.environ["DATABASE_PATH"] = _tmp_db_path
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-in-production")

import pytest  # noqa: E402

from app.db import db, utc_now  # noqa: E402

_DATA_TABLES = (
    "feedback", "recommendations", "findings", "relations",
    "cycle_runs", "artifacts", "audit_log",
)


@pytest.fixture
def project_id():
    """Proyecto de test aislado; se limpia por completo al finalizar el test."""
    pid = db.execute(
        "INSERT INTO projects(code, name, created_at) VALUES (?, ?, ?)",
        (f"TEST-{utc_now()}", "Proyecto de test", utc_now()),
    )
    yield pid
    for table in _DATA_TABLES:
        db.execute(f"DELETE FROM {table} WHERE project_id=?", (pid,))
    db.execute("DELETE FROM projects WHERE id=?", (pid,))


@pytest.fixture
def make_artifact(project_id):
    """Atajo para crear artefactos directamente, sin pasar por una fuente real
    (Jira/Drive/Swagger) en los tests de agentes que no ingestan datos."""
    from app.agents import CaptureAgent

    agent = CaptureAgent(project_id)

    def _make(artifact_type, external_id, title, content="", metadata=None, source="test"):
        return agent.ingest_artifact(
            artifact_type, external_id, title, content, metadata or {}, source
        )

    return _make
