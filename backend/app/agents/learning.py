from __future__ import annotations
from ..db import db, utc_now


class LearningAgent:
    """
    El aprendizaje no modifica el modelo.
    Registra feedback y convierte evidencia validada en memoria persistente.
    """

    def __init__(self, project_id: int):
        self.project_id = project_id

    def decide_relation(self, relation_id: int, decision: str,
                        comment: str, user_email: str) -> dict:
        relation = db.one(
            "SELECT * FROM relations WHERE id=? AND project_id=?",
            (relation_id, self.project_id)
        )
        if not relation:
            raise ValueError("Relación inexistente")
        db.execute(
            "UPDATE relations SET status=? WHERE id=?",
            (decision, relation_id)
        )
        db.execute("""
            INSERT INTO feedback(project_id, target_type, target_id, outcome,
                                 comment, created_at)
            VALUES (?, 'relation', ?, ?, ?, ?)
        """, (self.project_id, str(relation_id), decision, comment, utc_now()))
        db.log("relation_reviewed", {
            "relation_id": relation_id,
            "decision": decision,
            "comment": comment,
        }, self.project_id, user_email)
        return {"relation_id": relation_id, "status": decision}

    def feedback(self, target_type: str, target_id: str, outcome: str,
                 comment: str, user_email: str) -> dict:
        feedback_id = db.execute("""
            INSERT INTO feedback(project_id, target_type, target_id, outcome,
                                 comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            self.project_id, target_type, target_id,
            outcome, comment, utc_now()
        ))
        db.log("feedback_recorded", {
            "feedback_id": feedback_id,
            "target_type": target_type,
            "target_id": target_id,
            "outcome": outcome,
        }, self.project_id, user_email)
        return {"feedback_id": feedback_id}
