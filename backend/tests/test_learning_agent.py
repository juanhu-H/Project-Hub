import pytest

from app.agents import LearningAgent
from app.db import db, utc_now


def test_learn_from_evaluation_marks_successful_above_half(project_id):
    result = LearningAgent(project_id).learn_from_evaluation(1, {"effectiveness_rate": 0.8})
    assert result["outcome"] == "successful"


def test_learn_from_evaluation_marks_failed_below_half(project_id):
    result = LearningAgent(project_id).learn_from_evaluation(2, {"effectiveness_rate": 0.2})
    assert result["outcome"] == "failed"


def test_learn_from_evaluation_marks_no_data_when_nothing_to_evaluate(project_id):
    result = LearningAgent(project_id).learn_from_evaluation(3, {"effectiveness_rate": None})
    assert result["outcome"] == "no_data"


def test_learn_from_evaluation_persists_feedback_row(project_id):
    result = LearningAgent(project_id).learn_from_evaluation(4, {"effectiveness_rate": 1.0})

    row = db.one("SELECT * FROM feedback WHERE id=?", (result["feedback_id"],))
    assert row["target_type"] == "cycle_evaluation"
    assert row["target_id"] == "4"
    assert row["outcome"] == "successful"


def test_decide_relation_updates_status_and_logs_feedback(make_artifact, project_id):
    source_id = make_artifact("jira", "TST-20", "Historia A")
    target_id = make_artifact("document", "DOC-20", "Documento B")
    rel_id = db.execute("""
        INSERT INTO relations(project_id, source_artifact_id, target_artifact_id, relation_type,
                              method, confidence, evidence, status, created_at)
        VALUES (?, ?, ?, 'RELATED_TO', 'semantic_candidate', 0.7, 'ev', 'pending', ?)
    """, (project_id, source_id, target_id, utc_now()))

    result = LearningAgent(project_id).decide_relation(
        rel_id, "approved", "confirmado en test", "test@pih.local"
    )

    assert result == {"relation_id": rel_id, "status": "approved"}
    row = db.one("SELECT status FROM relations WHERE id=?", (rel_id,))
    assert row["status"] == "approved"

    feedback_rows = db.all(
        "SELECT * FROM feedback WHERE project_id=? AND target_type='relation'", (project_id,)
    )
    assert len(feedback_rows) == 1
    assert feedback_rows[0]["outcome"] == "approved"


def test_decide_relation_raises_for_unknown_relation(project_id):
    with pytest.raises(ValueError):
        LearningAgent(project_id).decide_relation(999999, "approved", "", "test@pih.local")
