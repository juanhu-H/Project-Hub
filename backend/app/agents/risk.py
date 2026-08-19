from __future__ import annotations
import json
from ..db import db, utc_now


class RiskAgent:
    """
    Predice retrasos y cuellos de botella: analiza el impacto y las
    inconsistencias detectadas, evalúa el riesgo asociado y propone
    acciones de mitigación (recomendaciones).
    """

    def __init__(self, project_id: int):
        self.project_id = project_id

    def run(self, impacts: dict, inconsistencies: list[dict]) -> dict:
        risk = self._assess(impacts, inconsistencies)
        db.log("risk_assessed", risk, self.project_id)
        return risk

    def _assess(self, impacts: dict, inconsistencies: list[dict]) -> dict:
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

    def recommend(self, inconsistencies: list[dict], risk: dict) -> list[dict]:
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
