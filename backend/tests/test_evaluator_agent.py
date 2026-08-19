from app.agents import EvaluatorAgent
from app.db import db, utc_now


def _open_recommendation(project_id, title, description):
    return db.execute("""
        INSERT INTO recommendations(project_id, title, description, priority,
                                    evidence_json, status, created_at)
        VALUES (?, ?, ?, 'medium', '[]', 'open', ?)
    """, (project_id, title, description, utc_now()))


def test_evaluate_with_no_previous_recommendations_reports_no_data(project_id):
    result = EvaluatorAgent(project_id).evaluate([], [])

    assert result["evaluated"] == 0
    assert result["effectiveness_rate"] is None


def test_recurring_recommendation_stays_open_and_pending(project_id):
    rec_id = _open_recommendation(
        project_id, "Actualizar documentación funcional", "TST-1 sin documentación vinculada"
    )
    previous = [{"id": rec_id, "title": "Actualizar documentación funcional",
                 "description": "TST-1 sin documentación vinculada"}]
    current = [{"title": "Actualizar documentación funcional",
                "description": "TST-1 sin documentación vinculada", "priority": "medium"}]

    result = EvaluatorAgent(project_id).evaluate(previous, current)

    assert result["still_pending"] == 1
    assert result["effective"] == 0
    assert result["effectiveness_rate"] == 0.0
    row = db.one("SELECT status FROM recommendations WHERE id=?", (rec_id,))
    assert row["status"] == "open"


def test_resolved_recommendation_is_marked_effective(project_id):
    rec_id = _open_recommendation(
        project_id, "Actualizar documentación funcional", "TST-2 sin documentación vinculada"
    )
    previous = [{"id": rec_id, "title": "Actualizar documentación funcional",
                 "description": "TST-2 sin documentación vinculada"}]
    current = []  # ya no se repite -> la condición que la originó se resolvió

    result = EvaluatorAgent(project_id).evaluate(previous, current)

    assert result["effective"] == 1
    assert result["effectiveness_rate"] == 1.0
    row = db.one("SELECT status FROM recommendations WHERE id=?", (rec_id,))
    assert row["status"] == "resolved"


def test_mixed_batch_computes_partial_effectiveness_rate(project_id):
    resolved_id = _open_recommendation(project_id, "Rec A", "desc A")
    pending_id = _open_recommendation(project_id, "Rec B", "desc B")
    previous = [
        {"id": resolved_id, "title": "Rec A", "description": "desc A"},
        {"id": pending_id, "title": "Rec B", "description": "desc B"},
    ]
    current = [{"title": "Rec B", "description": "desc B", "priority": "medium"}]

    result = EvaluatorAgent(project_id).evaluate(previous, current)

    assert result["effectiveness_rate"] == 0.5
