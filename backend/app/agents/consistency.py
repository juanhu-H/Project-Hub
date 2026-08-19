from __future__ import annotations
import json
from ..db import db, utc_now


class ConsistencyAgent:
    """
    Detecta contradicciones, requisitos incompletos y documentación
    desactualizada. Consulta la memoria construida por el Agente de
    Conocimiento para verificar que la información sea coherente.
    """

    def __init__(self, project_id: int):
        self.project_id = project_id

    def run(self) -> list[dict]:
        self._clear_open()
        findings = []
        findings.extend(self._check_jira_traceability())
        findings.extend(self._check_endpoint_traceability())
        db.log("consistency_completed", {"findings": len(findings)}, self.project_id)
        return findings

    def _clear_open(self):
        db.execute(
            "DELETE FROM findings WHERE project_id=? AND status='open'",
            (self.project_id,)
        )
        db.execute(
            "DELETE FROM recommendations WHERE project_id=? AND status='open'",
            (self.project_id,)
        )

    def _add_finding(self, finding_type: str, severity: str, title: str,
                     description: str, evidence: list[dict]) -> int:
        return db.execute("""
            INSERT INTO findings(project_id, finding_type, severity, title,
                                 description, evidence_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?)
        """, (
            self.project_id, finding_type, severity, title, description,
            json.dumps(evidence, ensure_ascii=False), utc_now()
        ))

    def _check_jira_traceability(self) -> list[dict]:
        findings = []
        issues = db.all(
            "SELECT * FROM artifacts WHERE project_id=? AND artifact_type='jira'",
            (self.project_id,)
        )
        for issue in issues:
            rels = db.all("""
                SELECT r.*, a.artifact_type, a.external_id, a.title
                FROM relations r
                JOIN artifacts a ON a.id=r.target_artifact_id
                WHERE r.project_id=? AND r.source_artifact_id=? AND r.status='approved'
                UNION ALL
                SELECT r.*, a.artifact_type, a.external_id, a.title
                FROM relations r
                JOIN artifacts a ON a.id=r.source_artifact_id
                WHERE r.project_id=? AND r.target_artifact_id=? AND r.status='approved'
            """, (self.project_id, issue["id"], self.project_id, issue["id"]))
            types = {r["artifact_type"] for r in rels}
            if "document" not in types:
                item = {
                    "severity": "medium",
                    "title": f"{issue['external_id']} sin documentación vinculada",
                    "description": "No se encontró una relación aprobada con documentación funcional.",
                    "evidence": [{"artifact": issue["external_id"]}],
                }
                self._add_finding("consistency", **item)
                findings.append(item)
            if "test" not in types:
                item = {
                    "severity": "high",
                    "title": f"{issue['external_id']} sin caso de prueba vinculado",
                    "description": "El cambio podría llegar a implementación sin cobertura trazable.",
                    "evidence": [{"artifact": issue["external_id"]}],
                }
                self._add_finding("consistency", **item)
                findings.append(item)
        return findings

    def _check_endpoint_traceability(self) -> list[dict]:
        findings = []
        endpoints = db.all(
            "SELECT * FROM artifacts WHERE project_id=? AND artifact_type='endpoint'",
            (self.project_id,)
        )
        for endpoint in endpoints:
            linked = db.one("""
                SELECT COUNT(*) AS total
                FROM relations r
                JOIN artifacts a ON (
                    (a.id=r.source_artifact_id AND r.target_artifact_id=?)
                    OR (a.id=r.target_artifact_id AND r.source_artifact_id=?)
                )
                WHERE r.project_id=? AND r.status='approved'
                  AND a.artifact_type IN ('jira', 'document')
            """, (endpoint["id"], endpoint["id"], self.project_id))
            if not linked or linked["total"] == 0:
                item = {
                    "severity": "low",
                    "title": f"Endpoint {endpoint['external_id']} sin trazabilidad funcional",
                    "description": "Existe en OpenAPI, pero no posee historia o documento aprobado relacionado.",
                    "evidence": [{"artifact": endpoint["external_id"]}],
                }
                self._add_finding("consistency", **item)
                findings.append(item)
        return findings
