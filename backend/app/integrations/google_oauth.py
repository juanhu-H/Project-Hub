from __future__ import annotations

import asyncio
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from ..config import settings

_credentials: Credentials | None = None
_lock = asyncio.Lock()


def _client_config() -> dict:
    redirect_uri = (
        f"http://localhost:{settings.google_drive_mcp_redirect_port}/"
    )
    return {
        "web": {
            "client_id": settings.google_drive_mcp_client_id,
            "client_secret": settings.google_drive_mcp_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }


def _load_credentials() -> Credentials | None:
    token_path = Path(settings.google_drive_mcp_token_path)
    if not token_path.exists():
        return None
    return Credentials.from_authorized_user_file(
        str(token_path), settings.google_drive_mcp_scope_list
    )


def _save_credentials(creds: Credentials) -> None:
    token_path = Path(settings.google_drive_mcp_token_path)
    token_path.write_text(creds.to_json(), encoding="utf-8")


def _run_installed_app_flow() -> Credentials:
    if not settings.google_drive_mcp_client_id or not settings.google_drive_mcp_client_secret:
        raise RuntimeError(
            "Faltan GOOGLE_DRIVE_MCP_CLIENT_ID / GOOGLE_DRIVE_MCP_CLIENT_SECRET en el .env."
        )

    print("")
    print("========================================")
    print("[PIH MCP] AUTORIZACIÓN GOOGLE DRIVE REQUERIDA")
    print("========================================")
    print("[PIH MCP] Se abrirá el navegador para autorizar el acceso a Drive...")

    flow = InstalledAppFlow.from_client_config(
        _client_config(), scopes=settings.google_drive_mcp_scope_list
    )
    creds = flow.run_local_server(
        port=settings.google_drive_mcp_redirect_port,
        prompt="consent",
    )

    print(
        "[PIH MCP] Autorización completada. Token guardado en",
        settings.google_drive_mcp_token_path,
    )

    return creds


async def get_access_token() -> str:
    """Devuelve un access token válido, refrescando o disparando el consentimiento
    OAuth2 (una vez, vía navegador) cuando hace falta."""

    global _credentials

    async with _lock:
        creds = _credentials or _load_credentials()

        if creds and creds.expired and creds.refresh_token:
            await asyncio.to_thread(creds.refresh, Request())
            _save_credentials(creds)

        if not creds or not creds.valid:
            creds = await asyncio.to_thread(_run_installed_app_flow)
            _save_credentials(creds)

        _credentials = creds
        return creds.token
