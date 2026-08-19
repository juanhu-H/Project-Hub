from app.db import db
from app.orchestrator import Orchestrator


def test_run_cycle_executes_all_agents_in_order(make_artifact, project_id):
    make_artifact("jira", "TST-30", "Historia de ciclo completo")

    summary = Orchestrator(project_id).run_cycle()

    for key in (
        "cycle_id", "knowledge", "consistency", "impact",
        "risk", "recommendations", "evaluation", "learning", "daily_report",
    ):
        assert key in summary

    cycle = db.one(
        "SELECT status FROM cycle_runs WHERE id=?", (summary["cycle_id"],)
    )
    assert cycle["status"] == "completed"


def test_second_cycle_evaluates_first_cycles_recommendations(make_artifact, project_id):
    make_artifact("jira", "TST-31", "Historia persistente sin doc ni test")

    first = Orchestrator(project_id).run_cycle()
    first_rec_count = len(first["recommendations"])
    assert first_rec_count > 0
    # Primer ciclo: no hay histórico previo para evaluar.
    assert first["evaluation"]["evaluated"] == 0

    second = Orchestrator(project_id).run_cycle()
    # Como nada se corrigió entre ciclos, las mismas recomendaciones se
    # regeneran -> el Evaluador debe verlas todas como "still_pending".
    assert second["evaluation"]["evaluated"] == first_rec_count
    assert second["evaluation"]["still_pending"] == first_rec_count
    assert second["evaluation"]["effective"] == 0


def test_cycle_marks_recommendation_effective_once_underlying_issue_is_fixed(
    make_artifact, project_id
):
    from app.db import utc_now

    jira_id = make_artifact("jira", "TST-32", "Historia que se corrige entre ciclos")
    first = Orchestrator(project_id).run_cycle()
    assert first["evaluation"]["evaluated"] == 0

    doc_id = make_artifact("document", "DOC-32", "Documentación agregada")
    db.execute("""
        INSERT INTO relations(project_id, source_artifact_id, target_artifact_id, relation_type,
                              method, confidence, evidence, status, created_at)
        VALUES (?, ?, ?, 'DOCUMENTED_IN', 'manual', 1.0, 'test', 'approved', ?)
    """, (project_id, jira_id, doc_id, utc_now()))

    second = Orchestrator(project_id).run_cycle()

    assert second["evaluation"]["effective"] >= 1
    assert second["evaluation"]["effectiveness_rate"] > 0
