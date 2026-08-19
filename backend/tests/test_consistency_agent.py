from app.agents import ConsistencyAgent
from app.db import db, utc_now


def _approve_relation(project_id, source_id, target_id, relation_type):
    db.execute("""
        INSERT INTO relations(project_id, source_artifact_id, target_artifact_id, relation_type,
                              method, confidence, evidence, status, created_at)
        VALUES (?, ?, ?, ?, 'manual', 1.0, 'test', 'approved', ?)
    """, (project_id, source_id, target_id, relation_type, utc_now()))


def test_jira_without_documentation_or_tests_is_flagged(make_artifact, project_id):
    make_artifact("jira", "TST-1", "Historia sin nada vinculado")

    findings = ConsistencyAgent(project_id).run()
    titles = [f["title"] for f in findings]

    assert "TST-1 sin documentación vinculada" in titles
    assert "TST-1 sin caso de prueba vinculado" in titles


def test_jira_with_approved_document_relation_is_not_flagged_for_docs(make_artifact, project_id):
    jira_id = make_artifact("jira", "TST-2", "Historia con doc")
    doc_id = make_artifact("document", "DOC-1", "Documento funcional")
    _approve_relation(project_id, jira_id, doc_id, "DOCUMENTED_IN")

    findings = ConsistencyAgent(project_id).run()
    titles = [f["title"] for f in findings]

    assert "TST-2 sin documentación vinculada" not in titles
    assert "TST-2 sin caso de prueba vinculado" in titles


def test_endpoint_without_traceability_is_flagged(make_artifact, project_id):
    make_artifact("endpoint", "GET /api/huerfano", "Endpoint sin trazabilidad")

    findings = ConsistencyAgent(project_id).run()

    assert any("sin trazabilidad funcional" in f["title"] for f in findings)


def test_endpoint_with_approved_jira_relation_is_not_flagged(make_artifact, project_id):
    jira_id = make_artifact("jira", "TST-3", "Historia")
    endpoint_id = make_artifact("endpoint", "POST /api/trazable", "Endpoint trazable")
    _approve_relation(project_id, jira_id, endpoint_id, "AFFECTS")

    findings = ConsistencyAgent(project_id).run()

    assert not any("POST /api/trazable" in f["title"] for f in findings)


def test_run_clears_previous_open_findings_before_recomputing(make_artifact, project_id):
    make_artifact("jira", "TST-4", "Historia persistente")
    agent = ConsistencyAgent(project_id)

    first_run_findings = agent.run()
    assert len(first_run_findings) == 2

    stored = db.all(
        "SELECT id FROM findings WHERE project_id=? AND status='open'", (project_id,)
    )
    assert len(stored) == 2

    # Correr de nuevo sin cambios no debe duplicar los findings existentes.
    second_run_findings = agent.run()
    assert len(second_run_findings) == 2
    stored_again = db.all(
        "SELECT id FROM findings WHERE project_id=? AND status='open'", (project_id,)
    )
    assert len(stored_again) == 2
