from __future__ import annotations
import json
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

    def learn_from_evaluation(self, cycle_id: int, evaluation: dict) -> dict:
        """
        Incorpora el resultado del Agente Evaluador a la memoria organizacional
        como una lección del ciclo. No modifica ningún modelo: solo registra
        evidencia (qué recomendaciones funcionaron y cuáles siguen pendientes)
        para que futuros ciclos y consultas puedan aprovecharla.
        """
        rate = evaluation.get("effectiveness_rate")
        if rate is None:
            outcome = "no_data"
        elif rate >= 0.5:
            outcome = "successful"
        else:
            outcome = "failed"

        feedback_id = db.execute("""
            INSERT INTO feedback(project_id, target_type, target_id, outcome,
                                 comment, created_at)
            VALUES (?, 'cycle_evaluation', ?, ?, ?, ?)
        """, (
            self.project_id, str(cycle_id), outcome,
            json.dumps(evaluation, ensure_ascii=False), utc_now(),
        ))
        db.log("learning_recorded", {
            "feedback_id": feedback_id,
            "cycle_id": cycle_id,
            "evaluation": evaluation,
        }, self.project_id)
        return {"feedback_id": feedback_id, "outcome": outcome}

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
