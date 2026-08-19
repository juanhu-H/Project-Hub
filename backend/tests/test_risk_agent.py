from app.agents import RiskAgent
from app.db import db


def test_low_risk_when_no_impact_or_findings(project_id):
    risk = RiskAgent(project_id).run(impacts={}, inconsistencies=[])

    assert risk["level"] == "low"
    assert risk["score"] == 0
    assert risk["model"] == "heuristic-v1"


def test_higher_risk_with_more_impact_and_missing_tests(project_id):
    low = RiskAgent(project_id).run(impacts={}, inconsistencies=[])

    impacts = {"TST-1": [{"artifact_type": "endpoint"}] * 5}
    inconsistencies = [
        {"title": "TST-1 sin caso de prueba vinculado", "evidence": []},
        {"title": "TST-2 sin caso de prueba vinculado", "evidence": []},
        {"title": "TST-3 sin documentación vinculada", "evidence": []},
    ]
    high = RiskAgent(project_id).run(impacts, inconsistencies)

    assert high["score"] > low["score"]


def test_recommend_creates_recommendation_rows_from_findings(project_id):
    inconsistencies = [{
        "title": "TST-1 sin caso de prueba vinculado",
        "evidence": [{"artifact": "TST-1"}],
    }]

    recs = RiskAgent(project_id).recommend(inconsistencies, {"level": "low"})

    assert len(recs) == 1
    assert recs[0]["priority"] == "high"
    assert recs[0]["description"] == "TST-1 sin caso de prueba vinculado"

    saved = db.all("SELECT * FROM recommendations WHERE project_id=?", (project_id,))
    assert len(saved) == 1
    assert saved[0]["status"] == "open"


def test_recommend_adds_alert_when_risk_level_is_high(project_id):
    recs = RiskAgent(project_id).recommend([], {"level": "high"})

    assert any("revisión antes del despliegue" in r["title"].lower() for r in recs)


def test_recommend_skips_alert_when_risk_level_is_not_high(project_id):
    recs = RiskAgent(project_id).recommend([], {"level": "medium"})

    assert not any("revisión antes del despliegue" in r["title"].lower() for r in recs)
