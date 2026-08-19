from __future__ import annotations
from ..db import db


class EvaluatorAgent:
    """
    Mide la efectividad de las recomendaciones generadas en el ciclo
    anterior: compara cada recomendación que seguía abierta contra las
    recomendaciones que este ciclo volvió a generar. Si una recomendación
    no se repite, la condición que la originó ya no está presente en la
    memoria organizacional y se considera efectiva. No hay inferencia por
    fuera de lo verificable en la base.
    """

    def __init__(self, project_id: int):
        self.project_id = project_id

    def evaluate(
        self,
        previous_recommendations: list[dict],
        current_recommendations: list[dict],
    ) -> dict:
        current_signatures = {
            (rec["title"], rec["description"]) for rec in current_recommendations
        }

        effective: list[dict] = []
        still_pending: list[dict] = []

        for rec in previous_recommendations:
            signature = (rec["title"], rec["description"])
            if signature in current_signatures:
                still_pending.append(rec)
                status = "open"
            else:
                effective.append(rec)
                status = "resolved"
            db.execute(
                "UPDATE recommendations SET status=? WHERE id=?",
                (status, rec["id"]),
            )

        total = len(previous_recommendations)
        result = {
            "evaluated": total,
            "effective": len(effective),
            "still_pending": len(still_pending),
            "effectiveness_rate": round(len(effective) / total, 2) if total else None,
            "effective_titles": [r["title"] for r in effective],
            "still_pending_titles": [r["title"] for r in still_pending],
        }
        db.log("evaluation_completed", result, self.project_id)
        return result
