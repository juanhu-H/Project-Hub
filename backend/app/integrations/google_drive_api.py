from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from ..config import settings


class GoogleDriveAPIClient:
    """Cliente de lectura para los documentos compartidos con la cuenta de servicio."""

    def _headers(self) -> dict[str, str]:
        if not settings.google_application_credentials:
            raise RuntimeError("Falta GOOGLE_APPLICATION_CREDENTIALS.")
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_application_credentials,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        credentials.refresh(Request())
        return {"Authorization": f"Bearer {credentials.token}"}

    def fetch_documents(self, folder_id: str, page_size: int = 50) -> list[dict[str, str]]:
        if not folder_id:
            raise ValueError("Falta DRIVE_FOLDER_ID en la configuración.")

        headers = self._headers()
        listing = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=headers,
            params={
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "files(id,name,mimeType,modifiedTime)",
                "pageSize": page_size,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
            timeout=30,
        )
        listing.raise_for_status()

        documents = []
        for file in listing.json().get("files", []):
            mime_type = file.get("mimeType", "")
            if mime_type == "application/vnd.google-apps.folder":
                continue
            download = requests.get(
                f"https://www.googleapis.com/drive/v3/files/{file['id']}",
                headers=headers,
                params={"alt": "media", "supportsAllDrives": "true"},
                timeout=30,
            )
            if not download.ok:
                continue
            content = self._as_text(download.content, mime_type)
            if content.strip():
                file_name = Path(file.get("name") or file["id"]).stem
                documents.append({
                    "id": file["id"],
                    "title": self._title_from_content(content, file_name),
                    "file_name": file_name,
                    "mime_type": mime_type,
                    "modified_time": file.get("modifiedTime", ""),
                    "content": content,
                })
        return documents

    @staticmethod
    def _as_text(raw: bytes, mime_type: str) -> str:
        docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if mime_type == docx:
            with ZipFile(BytesIO(raw)) as file:
                root = ElementTree.fromstring(file.read("word/document.xml"))
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            paragraphs = []
            for paragraph in root.iter(f"{ns}p"):
                text = "".join(node.text or "" for node in paragraph.iter(f"{ns}t"))
                if text.strip():
                    paragraphs.append(text)
            return "\n".join(paragraphs)
        if mime_type.startswith("text/"):
            return raw.decode("utf-8", errors="replace")
        return ""

    @staticmethod
    def _title_from_content(content: str, fallback: str) -> str:
        """El primer párrafo del documento es su título funcional."""
        return next((line.strip() for line in content.splitlines() if line.strip()), fallback)
