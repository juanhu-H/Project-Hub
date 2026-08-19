import pytest

from app.agents import ImpactAgent
from app.db import db, utc_now


def _approve_relation(project_id, source_id, target_id, relation_type):
    db.execute("""
        INSERT INTO relations(project_id, source_artifact_id, target_artifact_id, relation_type,
                              method, confidence, evidence, status, created_at)
        VALUES (?, ?, ?, ?, 'manual', 1.0, 'test', 'approved', ?)
    """, (project_id, source_id, target_id, relation_type, utc_now()))


def test_analyze_change_raises_for_unknown_artifact(project_id):
    with pytest.raises(ValueError):
        ImpactAgent(project_id).analyze_change("NOPE-1")


def test_analyze_change_returns_related_approved_artifacts(make_artifact, project_id):
    jira_id = make_artifact("jira", "TST-10", "Historia impactada")
    endpoint_id = make_artifact("endpoint", "POST /api/y", "Endpoint relacionado")
    _approve_relation(project_id, jira_id, endpoint_id, "AFFECTS")

    result = ImpactAgent(project_id).analyze_change("TST-10")

    assert result["artifact"]["external_id"] == "TST-10"
    assert result["impacted_count"] == 1
    assert result["impacted"][0]["external_id"] == "POST /api/y"


def test_analyze_change_ignores_pending_relations(make_artifact, project_id):
    jira_id = make_artifact("jira", "TST-12", "Historia con candidata pendiente")
    doc_id = make_artifact("document", "DOC-12", "Doc candidato")
    db.execute("""
        INSERT INTO relations(project_id, source_artifact_id, target_artifact_id, relation_type,
                              method, confidence, evidence, status, created_at)
        VALUES (?, ?, ?, 'RELATED_TO', 'semantic_candidate', 0.7, 'ev', 'pending', ?)
    """, (project_id, jira_id, doc_id, utc_now()))

    result = ImpactAgent(project_id).analyze_change("TST-12")

    assert result["impacted_count"] == 0


def test_run_aggregates_impact_for_every_jira_issue(make_artifact, project_id):
    make_artifact("jira", "TST-11", "Historia sin relaciones")

    result = ImpactAgent(project_id).run()

    assert "TST-11" in result
    assert result["TST-11"] == []
