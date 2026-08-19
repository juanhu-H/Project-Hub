from __future__ import annotations
import json
from .db import db, utc_now
from .agents import (
    KnowledgeAgent, ConsistencyAgent, ImpactAgent, RiskAgent,
    EvaluatorAgent, LearningAgent, ReportAgent,
)


class Orchestrator:
    """
    Ejecuta el ciclo agéntico completo de Project Intelligence Hub:
    Conocimiento -> Consistencia -> Impacto -> Riesgos -> Recomendaciones
    -> Evaluación de resultados -> Aprendizaje -> Resumen diario.
    """

    def __init__(self, project_id: int):
        self.project_id = project_id

    def run_cycle(self) -> dict:
        cycle_id = db.execute("""
            INSERT INTO cycle_runs(project_id, status, summary_json, started_at)
            VALUES (?, 'running', '{}', ?)
        """, (self.project_id, utc_now()))
        db.log("cycle_started", {"cycle_id": cycle_id}, self.project_id)

        try:
            # Se toma una foto de las recomendaciones que seguían abiertas del
            # ciclo anterior ANTES de que el Agente de Consistencia las limpie
            # para recalcular; el Evaluador las necesita para medir efectividad.
            previous_recommendations = db.all("""
                SELECT * FROM recommendations WHERE project_id=? AND status='open'
            """, (self.project_id,))

            knowledge = KnowledgeAgent(self.project_id).build()

            inconsistencies = ConsistencyAgent(self.project_id).run()
            impacts = ImpactAgent(self.project_id).run()

            risk_agent = RiskAgent(self.project_id)
            risk = risk_agent.run(impacts, inconsistencies)
            recommendations = risk_agent.recommend(inconsistencies, risk)

            evaluation = EvaluatorAgent(self.project_id).evaluate(
                previous_recommendations, recommendations
            )
            learning = LearningAgent(self.project_id).learn_from_evaluation(
                cycle_id, evaluation
            )

            report = ReportAgent(self.project_id).daily_report()

            summary = {
                "cycle_id": cycle_id,
                "knowledge": knowledge,
                "consistency": {"findings": len(inconsistencies)},
                "impact": {"issues_analyzed": len(impacts)},
                "risk": risk,
                "recommendations": recommendations,
                "evaluation": evaluation,
                "learning": learning,
                "daily_report": report,
            }
            db.execute("""
                UPDATE cycle_runs
                SET status='completed', summary_json=?, finished_at=?
                WHERE id=?
            """, (json.dumps(summary, ensure_ascii=False), utc_now(), cycle_id))
            db.log("cycle_completed", summary, self.project_id)
            return summary
        except Exception as exc:
            db.execute("""
                UPDATE cycle_runs
                SET status='failed', summary_json=?, finished_at=?
                WHERE id=?
            """, (json.dumps({"error": str(exc)}), utc_now(), cycle_id))
            db.log("cycle_failed", {"cycle_id": cycle_id, "error": str(exc)}, self.project_id)
            raise
