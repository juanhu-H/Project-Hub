from __future__ import annotations
import json
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agents import CaptureAgent, ReportAgent, LearningAgent
from .bootstrap import bootstrap
from .config import settings
from .db import db
from .orchestrator import Orchestrator
from .schemas import (
    FeedbackInput, LoginRequest, RelationDecision, SearchRequest,
    TokenResponse, TranscriptInput
)
from .security import create_token, current_user, verify_password

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    bootstrap()


def get_project(user: dict) -> dict:
    project = db.one("""
        SELECT p.id, p.code, p.name, up.role
        FROM projects p
        JOIN user_projects up ON up.project_id=p.id
        WHERE up.user_id=?
        ORDER BY p.id LIMIT 1
    """, (user["id"],))
    if not project:
        raise HTTPException(status_code=403, detail="Usuario sin proyecto asignado")
    return project


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = db.one("SELECT * FROM users WHERE email=?", (payload.email,))
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_token(user["email"], user["role"])
    safe_user = {k: user[k] for k in ("id", "email", "name", "role")}
    db.log("login_success", {"email": user["email"]}, user_email=user["email"])
    return TokenResponse(access_token=token, user=safe_user)


@app.get("/api/dashboard")
def dashboard(user: dict = Depends(current_user)):
    project = get_project(user)
    artifacts = db.all("""
        SELECT artifact_type, COUNT(*) total FROM artifacts
        WHERE project_id=? GROUP BY artifact_type
    """, (project["id"],))
    pending = db.one("""
        SELECT COUNT(*) total FROM relations
        WHERE project_id=? AND status='pending'
    """, (project["id"],))
    findings = db.all("""
        SELECT severity, COUNT(*) total FROM findings
        WHERE project_id=? AND status='open' GROUP BY severity
    """, (project["id"],))
    recommendations = db.all("""
        SELECT * FROM recommendations WHERE project_id=? AND status='open'
        ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id DESC
        LIMIT 8
    """, (project["id"],))
    last_cycle = db.one("""
        SELECT id, status, started_at, finished_at FROM cycle_runs
        WHERE project_id=? ORDER BY id DESC LIMIT 1
    """, (project["id"],))
    return {
        "project": project,
        "metrics": {
            "artifacts": {row["artifact_type"]: row["total"] for row in artifacts},
            "pending_relations": pending["total"] if pending else 0,
            "findings": {row["severity"]: row["total"] for row in findings},
        },
        "recommendations": recommendations,
        "last_cycle": last_cycle,
        "daily_report": ReportAgent(project["id"]).daily_report(),
    }



@app.post("/api/ingest/jira")
async def ingest_jira(user: dict = Depends(current_user)):
    project = get_project(user)
    try:
        ids = await CaptureAgent(project["id"]).ingest_jira()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ingested": len(ids), "artifact_ids": ids}


@app.post("/api/ingest/transcript")
def ingest_transcript(payload: TranscriptInput, user: dict = Depends(current_user)):
    project = get_project(user)
    artifact_id = CaptureAgent(project["id"]).ingest_artifact(
        "transcript",
        f"TRANSCRIPT-{abs(hash(payload.title))}",
        payload.title,
        payload.content,
        {"validation_required": True},
        "manual-transcript",
    )
    return {"artifact_id": artifact_id}


@app.post("/api/process/run")
def run_cycle(user: dict = Depends(current_user)):
    project = get_project(user)
    return Orchestrator(project["id"]).run_cycle()


@app.post("/api/search")
def search(payload: SearchRequest, user: dict = Depends(current_user)):
    project = get_project(user)
    result = ReportAgent(project["id"]).search(payload.query)
    db.log("user_query", {"query": payload.query}, project["id"], user["email"])
    return result


@app.get("/api/relations/pending")
def pending_relations(user: dict = Depends(current_user)):
    project = get_project(user)
    return db.all("""
        SELECT r.id, r.relation_type, r.method, r.confidence, r.evidence, r.status,
               s.external_id source_id, s.title source_title, s.artifact_type source_type,
               t.external_id target_id, t.title target_title, t.artifact_type target_type
        FROM relations r
        JOIN artifacts s ON s.id=r.source_artifact_id
        JOIN artifacts t ON t.id=r.target_artifact_id
        WHERE r.project_id=? AND r.status='pending'
        ORDER BY r.confidence DESC, r.id DESC
    """, (project["id"],))


@app.post("/api/relations/{relation_id}/decision")
def decide_relation(relation_id: int, payload: RelationDecision,
                    user: dict = Depends(current_user)):
    project = get_project(user)
    try:
        return LearningAgent(project["id"]).decide_relation(
            relation_id, payload.decision, payload.comment, user["email"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/feedback")
def feedback(payload: FeedbackInput, user: dict = Depends(current_user)):
    project = get_project(user)
    return LearningAgent(project["id"]).feedback(
        payload.target_type, payload.target_id,
        payload.outcome, payload.comment, user["email"]
    )


@app.get("/api/reports/daily")
def daily_report(user: dict = Depends(current_user)):
    project = get_project(user)
    return ReportAgent(project["id"]).daily_report()


@app.get("/api/session-log")
def session_log(user: dict = Depends(current_user)):
    project = get_project(user)
    rows = db.all("""
        SELECT id, user_email, event_type, details_json, created_at
        FROM audit_log
        WHERE project_id=? OR project_id IS NULL
        ORDER BY id DESC LIMIT 100
    """, (project["id"],))
    for row in rows:
        row["details"] = json.loads(row.pop("details_json"))
    return rows
