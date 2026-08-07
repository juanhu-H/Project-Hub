from .config import settings
from .db import db, utc_now
from .security import hash_password


def bootstrap():
    user = db.one("SELECT id FROM users WHERE email=?", (settings.demo_admin_email,))
    if not user:
        user_id = db.execute("""
            INSERT INTO users(email, password_hash, name, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            settings.demo_admin_email,
            hash_password(settings.demo_admin_password),
            "Administrador PIH",
            "admin",
            utc_now(),
        ))
    else:
        user_id = user["id"]

    project = db.one("SELECT id FROM projects WHERE code='PIH-DEMO'")
    if not project:
        project_id = db.execute("""
            INSERT INTO projects(code, name, created_at) VALUES (?, ?, ?)
        """, ("PIH-DEMO", "Portal Prestadores — Demo", utc_now()))
    else:
        project_id = project["id"]

    db.execute("""
        INSERT OR IGNORE INTO user_projects(user_id, project_id, role)
        VALUES (?, ?, ?)
    """, (user_id, project_id, "admin"))
