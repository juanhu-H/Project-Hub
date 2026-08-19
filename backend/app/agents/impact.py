from __future__ import annotations
from ..db import db


class ImpactAgent:
    """
    Identifica módulos, APIs, pruebas, documentación e historias afectadas
    ante un cambio, consultando las relaciones aprobadas en la memoria
    organizacional construida por el Agente de Conocimiento.
    """

    def __init__(self, project_id: int):
        self.project_id = project_id

    def run(self) -> dict:
        """Impacto precalculado para todas las historias de Jira del proyecto
        (usado por el ciclo agéntico)."""
        issues = db.all(
            "SELECT id, external_id, title FROM artifacts WHERE project_id=? AND artifact_type='jira'",
            (self.project_id,)
        )
        return {
            issue["external_id"]: self._related_artifacts(issue["id"])
            for issue in issues
        }

    def analyze_change(self, external_id: str) -> dict:
        """Impacto bajo demanda para un artefacto puntual (ej. 'el usuario
        solicita modificar este endpoint')."""
        artifact = db.one(
            "SELECT id, external_id, title, artifact_type FROM artifacts "
            "WHERE project_id=? AND external_id=?",
            (self.project_id, external_id)
        )
        if not artifact:
            raise ValueError(
                f"No existe el artefacto '{external_id}' en la memoria organizacional."
            )
        related = self._related_artifacts(artifact["id"])
        return {
            "artifact": {
                "external_id": artifact["external_id"],
                "title": artifact["title"],
                "artifact_type": artifact["artifact_type"],
            },
            "impacted": related,
            "impacted_count": len(related),
        }

    def _related_artifacts(self, artifact_id: int) -> list[dict]:
        return db.all("""
            SELECT a.external_id, a.title, a.artifact_type, r.relation_type,
                   r.confidence, r.evidence, r.status
            FROM relations r
            JOIN artifacts a ON a.id = CASE
                WHEN r.source_artifact_id=? THEN r.target_artifact_id
                ELSE r.source_artifact_id END
            WHERE r.project_id=?
              AND (r.source_artifact_id=? OR r.target_artifact_id=?)
              AND r.status='approved'
        """, (artifact_id, self.project_id, artifact_id, artifact_id))
