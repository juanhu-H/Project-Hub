from __future__ import annotations
import json
from ..db import db, utc_now


class AnalysisAgent:
    """Consolida consistencia, impacto y riesgo para el MVP."""

    def __init__(self, project_id: int):
        self.project_id = project_id

    def run(self) -> dict:
        self._clear_open_findings()
        inconsistencies = self._consistency()
        impacts = self._impact()
        risk = self._risk(impacts, inconsistencies)
        recommendations = self._recommend(inconsistencies, risk)

        result = {
            "inconsistencies": inconsistencies,
            "impacts": impacts,
            "risk": risk,
            "recommendations": recommendations,
        }
        db.log("analysis_completed", result, self.project_id)
        return result

    def _clear_open_findings(self):
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

    def _consistency(self) -> list[dict]:
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

    def _impact(self) -> dict:
        issues = db.all(
            "SELECT id, external_id, title FROM artifacts WHERE project_id=? AND artifact_type='jira'",
            (self.project_id,)
        )
        result = {}
        for issue in issues:
            related = db.all("""
                SELECT a.external_id, a.title, a.artifact_type, r.relation_type,
                       r.confidence, r.evidence, r.status
                FROM relations r
                JOIN artifacts a ON a.id = CASE
                    WHEN r.source_artifact_id=? THEN r.target_artifact_id
                    ELSE r.source_artifact_id END
                WHERE r.project_id=?
                  AND (r.source_artifact_id=? OR r.target_artifact_id=?)
                  AND r.status='approved'
            """, (issue["id"], self.project_id, issue["id"], issue["id"]))
            result[issue["external_id"]] = related
        return result

    def _risk(self, impacts: dict, inconsistencies: list[dict]) -> dict:
        impacted_count = sum(len(v) for v in impacts.values())
        critical_dependencies = sum(
            1 for rels in impacts.values()
            for r in rels if r["artifact_type"] == "endpoint"
        )
        missing_tests = sum(1 for f in inconsistencies if "caso de prueba" in f["title"].lower())
        missing_docs = sum(1 for f in inconsistencies if "documentación" in f["title"].lower())

        # Heurística transparente, no es predicción estadística.
        impact_score = min(100, impacted_count * 12)
        dependency_score = min(100, critical_dependencies * 25)
        tests_score = min(100, missing_tests * 35)
        docs_score = min(100, missing_docs * 25)
        incidents_score = 20 if db.one(
            "SELECT id FROM artifacts WHERE project_id=? AND artifact_type='jira' AND lower(title) LIKE '%bug%' LIMIT 1",
            (self.project_id,)
        ) else 0

        score = round(
            impact_score * 0.25 +
            dependency_score * 0.25 +
            tests_score * 0.20 +
            docs_score * 0.15 +
            incidents_score * 0.15
        )
        level = "low" if score < 40 else "medium" if score < 70 else "high"
        return {
            "score": score,
            "level": level,
            "model": "heuristic-v1",
            "factors": {
                "impact": {"value": impact_score, "weight": 0.25},
                "critical_dependencies": {"value": dependency_score, "weight": 0.25},
                "missing_tests": {"value": tests_score, "weight": 0.20},
                "missing_documentation": {"value": docs_score, "weight": 0.15},
                "incident_history": {"value": incidents_score, "weight": 0.15},
            },
            "disclaimer": "Evaluación heurística explicable; no constituye una predicción estadística."
        }

    def _recommend(self, inconsistencies: list[dict], risk: dict) -> list[dict]:
        recommendations = []
        for finding in inconsistencies[:6]:
            if "caso de prueba" in finding["title"].lower():
                title = "Crear o vincular caso de prueba"
                description = finding["title"]
                priority = "high"
            elif "documentación" in finding["title"].lower():
                title = "Actualizar documentación funcional"
                description = finding["title"]
                priority = "medium"
            else:
                title = "Revisar trazabilidad del artefacto"
                description = finding["title"]
                priority = "low"

            rec = {"title": title, "description": description, "priority": priority}
            db.execute("""
                INSERT INTO recommendations(project_id, title, description, priority,
                                            evidence_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'open', ?)
            """, (
                self.project_id, title, description, priority,
                json.dumps(finding["evidence"], ensure_ascii=False), utc_now()
            ))
            recommendations.append(rec)

        if risk["level"] == "high":
            rec = {
                "title": "Requerir revisión antes del despliegue",
                "description": "El puntaje heurístico de riesgo es alto. Ejecutar regresión y validar documentación.",
                "priority": "high",
            }
            db.execute("""
                INSERT INTO recommendations(project_id, title, description, priority,
                                            evidence_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'open', ?)
            """, (
                self.project_id, rec["title"], rec["description"], rec["priority"],
                json.dumps([risk], ensure_ascii=False), utc_now()
            ))
            recommendations.append(rec)
        return recommendations
