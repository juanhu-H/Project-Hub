from __future__ import annotations
import json
import re
from itertools import combinations
from ..db import db, utc_now
from ..graph import neo4j_graph
from ..utils import extract_issue_keys, extract_paths, jaccard, normalize


class KnowledgeAgent:
    """
    Construye relaciones con enfoque híbrido:
    1) coincidencias explícitas;
    2) reglas determinísticas por tipo;
    3) similitud semántica simple como relación candidata.
    """

    def __init__(self, project_id: int):
        self.project_id = project_id

    def _create_relation(self, source: dict, target: dict, relation_type: str,
                         method: str, confidence: float, evidence: str,
                         status: str) -> bool:
        if source["id"] == target["id"]:
            return False
        try:
            relation_id = db.execute("""
                INSERT INTO relations(
                    project_id, source_artifact_id, target_artifact_id,
                    relation_type, method, confidence, evidence, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_artifact_id, target_artifact_id, relation_type)
                DO UPDATE SET method=excluded.method, confidence=excluded.confidence,
                              evidence=excluded.evidence, status=excluded.status
            """, (
                self.project_id, source["id"], target["id"], relation_type,
                method, confidence, evidence, status, utc_now()
            ))
            relation = {
                "relation_type": relation_type,
                "method": method,
                "confidence": confidence,
                "evidence": evidence,
                "status": status,
            }
            neo4j_graph.sync_relation(source, target, relation)
            return True
        except Exception:
            return False

    def build(self) -> dict:
        artifacts = db.all("SELECT * FROM artifacts WHERE project_id=?", (self.project_id,))
        created = 0
        explicit = 0
        candidates = 0

        for source, target in combinations(artifacts, 2):
            s_text = f"{source['external_id']} {source['title']} {source['content']}"
            t_text = f"{target['external_id']} {target['title']} {target['content']}"

            # Jira key cited in another artifact.
            s_keys = extract_issue_keys(s_text)
            t_keys = extract_issue_keys(t_text)
            if source["artifact_type"] == "jira" and source["external_id"] in t_keys:
                if self._create_relation(
                    source, target, self._relation_type(source, target),
                    "explicit_reference", 0.98,
                    f"{target['external_id']} referencia explícitamente {source['external_id']}",
                    "approved"
                ):
                    created += 1; explicit += 1
                continue
            if target["artifact_type"] == "jira" and target["external_id"] in s_keys:
                if self._create_relation(
                    target, source, self._relation_type(target, source),
                    "explicit_reference", 0.98,
                    f"{source['external_id']} referencia explícitamente {target['external_id']}",
                    "approved"
                ):
                    created += 1; explicit += 1
                continue

            # Endpoint path cited in another artifact.
            endpoint = source if source["artifact_type"] == "endpoint" else (
                target if target["artifact_type"] == "endpoint" else None
            )
            other = target if endpoint is source else source
            if endpoint:
                metadata = json.loads(endpoint["metadata_json"])
                path = metadata.get("path", "")
                if path and path in other["content"]:
                    if self._create_relation(
                        other, endpoint, self._relation_type(other, endpoint),
                        "endpoint_path_match", 0.97,
                        f"Se encontró la ruta {path} dentro de {other['external_id']}",
                        "approved"
                    ):
                        created += 1; explicit += 1
                    continue

            # Relación semántica candidata: nunca se confirma sola.
            allowed_pair = {source["artifact_type"], target["artifact_type"]} & {
                "jira", "endpoint", "document", "test", "transcript"
            }
            score = jaccard(s_text, t_text)
            if allowed_pair and score >= 0.16:
                common = sorted(set(normalize(s_text).split()) & set(normalize(t_text).split()))
                evidence = "Términos coincidentes: " + ", ".join(common[:8])
                if self._create_relation(
                    source, target, self._relation_type(source, target),
                    "semantic_candidate", min(0.89, round(0.55 + score, 2)),
                    evidence, "pending"
                ):
                    created += 1; candidates += 1

        db.log("knowledge_graph_built", {
            "artifacts": len(artifacts),
            "relations_created_or_updated": created,
            "explicit_relations": explicit,
            "candidate_relations": candidates,
        }, self.project_id)

        return {
            "artifacts": len(artifacts),
            "relations": len(db.all(
                "SELECT id FROM relations WHERE project_id=?", (self.project_id,)
            )),
            "explicit": explicit,
            "candidates": candidates,
        }

    @staticmethod
    def _relation_type(source: dict, target: dict) -> str:
        pair = (source["artifact_type"], target["artifact_type"])
        mapping = {
            ("jira", "endpoint"): "AFFECTS",
            ("jira", "document"): "DOCUMENTED_IN",
            ("jira", "test"): "TESTED_BY",
            ("jira", "transcript"): "DISCUSSED_IN",
            ("transcript", "jira"): "MENTIONS",
            ("document", "endpoint"): "DESCRIBES",
            ("test", "endpoint"): "VALIDATES",
        }
        return mapping.get(pair) or mapping.get((pair[1], pair[0])) or "RELATED_TO"
