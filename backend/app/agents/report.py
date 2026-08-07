from __future__ import annotations
import json
from datetime import datetime, timezone
from ..db import db
from ..utils import extract_issue_keys, tokens


class ReportAgent:
    def __init__(self, project_id: int):
        self.project_id = project_id

    def search(self, query: str) -> dict:
        query_tokens = tokens(query)
        issue_keys = extract_issue_keys(query)

        artifacts = db.all(
            "SELECT * FROM artifacts WHERE project_id=?", (self.project_id,)
        )
        ranked = []
        for artifact in artifacts:
            text_tokens = tokens(
                f"{artifact['external_id']} {artifact['title']} {artifact['content']}"
            )
            overlap = len(query_tokens & text_tokens)
            if artifact["external_id"] in issue_keys:
                overlap += 20
            if overlap:
                ranked.append((overlap, artifact))
        ranked.sort(key=lambda item: item[0], reverse=True)
        selected = [item[1] for item in ranked[:5]]

        evidence = []
        related = []
        for artifact in selected:
            evidence.append({
                "type": artifact["artifact_type"],
                "id": artifact["external_id"],
                "title": artifact["title"],
                "source": artifact["source"],
            })
            rels = db.all("""
                SELECT a.external_id, a.title, a.artifact_type, r.relation_type,
                       r.confidence, r.evidence
                FROM relations r
                JOIN artifacts a ON a.id = CASE
                    WHEN r.source_artifact_id=? THEN r.target_artifact_id
                    ELSE r.source_artifact_id END
                WHERE r.project_id=?
                  AND (r.source_artifact_id=? OR r.target_artifact_id=?)
                  AND r.status='approved'
            """, (artifact["id"], self.project_id, artifact["id"], artifact["id"]))
            related.extend(rels)

        # respuesta determinística y trazable
        if selected:
            lines = [f"Se encontraron {len(selected)} artefactos relevantes."]
            if related:
                lines.append(f"Existen {len(related)} relaciones aprobadas asociadas.")
                by_type = {}
                for rel in related:
                    by_type.setdefault(rel["artifact_type"], []).append(rel["external_id"])
                for artifact_type, ids in by_type.items():
                    lines.append(f"{artifact_type}: {', '.join(sorted(set(ids)))}")
            else:
                lines.append("No hay relaciones aprobadas; revise las relaciones candidatas.")
            answer = "\n".join(lines)
        else:
            answer = (
                "No existe evidencia suficiente en la memoria organizacional para responder. "
                "Cargue nuevas fuentes o reformule la consulta."
            )

        risk_row = db.one("""
            SELECT details_json FROM audit_log
            WHERE project_id=? AND event_type='analysis_completed'
            ORDER BY id DESC LIMIT 1
        """, (self.project_id,))
        risk = None
        if risk_row:
            risk = json.loads(risk_row["details_json"]).get("risk")

        result = {
            "query": query,
            "answer": answer,
            "evidence": evidence,
            "relations": related[:20],
            "risk": risk,
            "confidence": "high" if issue_keys and related else "medium" if evidence else "low",
        }
        db.log("search_performed", result, self.project_id)
        return result

    def daily_report(self) -> dict:
        artifacts = db.all("""
            SELECT artifact_type, COUNT(*) AS total
            FROM artifacts WHERE project_id=?
            GROUP BY artifact_type
        """, (self.project_id,))
        findings = db.all("""
            SELECT severity, COUNT(*) AS total
            FROM findings WHERE project_id=? AND status='open'
            GROUP BY severity
        """, (self.project_id,))
        recommendations = db.all("""
            SELECT priority, COUNT(*) AS total
            FROM recommendations WHERE project_id=? AND status='open'
            GROUP BY priority
        """, (self.project_id,))
        pending = db.one("""
            SELECT COUNT(*) AS total FROM relations
            WHERE project_id=? AND status='pending'
        """, (self.project_id,))
        last_cycle = db.one("""
            SELECT * FROM cycle_runs WHERE project_id=?
            ORDER BY id DESC LIMIT 1
        """, (self.project_id,))

        return {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "title": "Resumen diario del proyecto",
            "artifacts": {row["artifact_type"]: row["total"] for row in artifacts},
            "findings": {row["severity"]: row["total"] for row in findings},
            "recommendations": {
                row["priority"]: row["total"] for row in recommendations
            },
            "pending_relations": pending["total"] if pending else 0,
            "last_cycle": last_cycle,
        }
