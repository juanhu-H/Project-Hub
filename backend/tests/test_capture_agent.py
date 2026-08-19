import pytest

from app.agents.capture import CaptureAgent
from app.db import db


def test_adf_to_text_extracts_nested_text():
    adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Como", "marks": [{"type": "strong"}]},
                {"type": "text", "text": " visitante"},
            ]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Quiero registrarme"},
            ]},
        ],
    }
    text = CaptureAgent._adf_to_text(adf)
    assert "Como" in text
    assert "visitante" in text
    assert "Quiero registrarme" in text
    # No debe filtrarse ruido estructural de ADF (claves de formato).
    assert "paragraph" not in text
    assert "marks" not in text


def test_adf_to_text_handles_none_and_empty():
    assert CaptureAgent._adf_to_text(None) == ""
    assert CaptureAgent._adf_to_text({}) == ""
    assert CaptureAgent._adf_to_text([]) == ""


def test_jira_comments_text_joins_comment_bodies():
    comments = {
        "comments": [
            {"body": {"content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Primer comentario"}]}
            ]}},
            {"body": {"content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Segundo comentario"}]}
            ]}},
        ]
    }
    text = CaptureAgent._jira_comments_text(comments)
    assert "Primer comentario" in text
    assert "Segundo comentario" in text


def test_jira_comments_text_handles_missing_comments():
    assert CaptureAgent._jira_comments_text(None) == ""
    assert CaptureAgent._jira_comments_text({}) == ""
    assert CaptureAgent._jira_comments_text({"comments": []}) == ""


def test_ingest_swagger_creates_endpoint_artifact_per_operation(project_id):
    agent = CaptureAgent(project_id)
    spec = """
openapi: 3.0.3
info:
  title: Test API
  version: 1.0.0
paths:
  /api/ping:
    get:
      operationId: ping
      summary: Ping de prueba
      description: Implementa PIH-1
      responses:
        "200":
          description: OK
  /api/pong:
    post:
      operationId: pong
      summary: Pong de prueba
      responses:
        "201":
          description: Creado
"""
    ids = agent.ingest_swagger(spec, "test-source")
    assert len(ids) == 2

    rows = db.all(
        "SELECT * FROM artifacts WHERE id IN (?, ?) ORDER BY external_id",
        tuple(ids),
    )
    assert rows[0]["artifact_type"] == "endpoint"
    assert rows[0]["external_id"] == "GET /api/ping"
    assert rows[0]["source"] == "test-source"
    assert rows[1]["external_id"] == "POST /api/pong"


def test_ingest_swagger_rejects_empty_spec(project_id):
    agent = CaptureAgent(project_id)
    with pytest.raises(ValueError):
        agent.ingest_swagger("", "test-source")


def test_ingest_swagger_ignores_non_http_method_keys(project_id):
    agent = CaptureAgent(project_id)
    spec = """
openapi: 3.0.3
info: {title: Test, version: "1.0"}
paths:
  /api/only-params:
    parameters:
      - name: id
        in: query
    get:
      summary: Único endpoint válido
      responses:
        "200":
          description: OK
"""
    ids = agent.ingest_swagger(spec, "test-source")
    assert len(ids) == 1
