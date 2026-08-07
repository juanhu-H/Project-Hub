from __future__ import annotations
import json
from .db import db, utc_now
from .agents import KnowledgeAgent, AnalysisAgent, ReportAgent


class Orchestrator:
    def __init__(self, project_id: int):
        self.project_id = project_id

    def run_cycle(self) -> dict:
        cycle_id = db.execute("""
            INSERT INTO cycle_runs(project_id, status, summary_json, started_at)
            VALUES (?, 'running', '{}', ?)
        """, (self.project_id, utc_now()))
        db.log("cycle_started", {"cycle_id": cycle_id}, self.project_id)

        try:
            knowledge = KnowledgeAgent(self.project_id).build()
            analysis = AnalysisAgent(self.project_id).run()
            report = ReportAgent(self.project_id).daily_report()
            summary = {
                "cycle_id": cycle_id,
                "knowledge": knowledge,
                "analysis": analysis,
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
