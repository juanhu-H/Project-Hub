from __future__ import annotations

import json
from typing import Any

import httpx
import yaml

from ..config import settings
from ..db import db
from ..graph import neo4j_graph


class CaptureAgent:
    """
    Agente de captura de Project Intelligence Hub.

    Fuentes soportadas:

    1. Jira REST API
       - Sincronización estructurada de tickets.
       - Épicas, historias, bugs, hotfix y subtareas.

    2. Atlassian Rovo MCP
       - Consultas complementarias sobre Jira/Confluence.
       - Utiliza OAuth mediante mcp-remote.

    3. Swagger / OpenAPI
       - Extracción estructurada de endpoints.
    """

    ATLASSIAN_MCP_URL = "https://mcp.atlassian.com/v1/mcp/authv2"

    def __init__(self, project_id: int):
        self.project_id = project_id

    # ==========================================================
    # ARTEFACTOS
    # ==========================================================

    def ingest_artifact(
        self,
        artifact_type: str,
        external_id: str,
        title: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        source: str = "manual",
    ) -> int:

        artifact_id = db.upsert_artifact(
            self.project_id,
            artifact_type,
            external_id,
            title,
            content,
            metadata or {},
            source,
        )

        artifact = db.one(
            "SELECT * FROM artifacts WHERE id=?",
            (artifact_id,),
        )

        if artifact:
            try:
                neo4j_graph.sync_artifact(artifact)

            except Exception as exc:
                print(
                    "[PIH] Neo4j no disponible:",
                    str(exc),
                )

        db.log(
            "artifact_ingested",
            {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "external_id": external_id,
                "source": source,
            },
            self.project_id,
        )

        return artifact_id

    # ==========================================================
    # SWAGGER / OPENAPI
    # ==========================================================

    def ingest_swagger(
        self,
        raw: str,
        source_name: str = "swagger",
    ) -> list[int]:

        spec = yaml.safe_load(raw)

        if not spec:
            raise ValueError(
                "El archivo Swagger/OpenAPI está vacío."
            )

        ids: list[int] = []

        paths = spec.get("paths") or {}

        for path, operations in paths.items():

            if not isinstance(
                operations,
                dict,
            ):
                continue

            for method, operation in operations.items():

                if method.lower() not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "options",
                    "head",
                }:
                    continue

                if not isinstance(
                    operation,
                    dict,
                ):
                    continue

                operation_id = (
                    operation.get("operationId")
                    or f"{method.upper()} {path}"
                )

                content = json.dumps(
                    operation,
                    ensure_ascii=False,
                )

                artifact_id = self.ingest_artifact(
                    artifact_type="endpoint",
                    external_id=(
                        f"{method.upper()} {path}"
                    ),
                    title=(
                        operation.get("summary")
                        or operation_id
                    ),
                    content=(
                        f"{method.upper()} {path}\n"
                        f"{content}"
                    ),
                    metadata={
                        "path": path,
                        "method": method.upper(),
                        "operation_id": operation_id,
                        "tags": operation.get(
                            "tags",
                            [],
                        ),
                    },
                    source=source_name,
                )

                ids.append(
                    artifact_id
                )

        db.log(
            "swagger_sync_completed",
            {
                "endpoints_saved": len(ids),
            },
            self.project_id,
        )

        return ids

    # ==========================================================
    # JIRA REST API
    # ==========================================================

    async def ingest_jira(
        self,
    ) -> list[int]:
        """
        Sincroniza los issues configurados en JIRA_JQL.

        Utiliza:
        GET /rest/api/3/search/jql

        La consulta JQL se envía explícitamente como parámetro.
        """

        self._validate_jira_settings()

        base_url = settings.jira_base_url.rstrip("/")

        url = (
            f"{base_url}"
            "/rest/api/3/search/jql"
        )

        auth = (
            settings.jira_email,
            settings.jira_api_token,
        )

        headers = {
            "Accept": "application/json",
        }

        print("")
        print("=========================================")
        print("[PIH] INICIO SINCRONIZACIÓN JIRA")
        print("=========================================")

        print(
            "[PIH] Base URL:",
            base_url,
        )

        print(
            "[PIH] Email:",
            settings.jira_email,
        )

        print(
            "[PIH] JQL:",
            settings.jira_jql,
        )

        all_issues: list[dict[str, Any]] = []

        next_page_token: str | None = None

        page_number = 1

        async with httpx.AsyncClient(
            timeout=45.0,
        ) as client:

            # =============================================
            # VALIDAR IDENTIDAD AUTENTICADA
            # =============================================

            myself_url = (
                f"{base_url}/rest/api/3/myself"
            )

            myself_response = await client.get(
                myself_url,
                auth=auth,
                headers={
                    "Accept": "application/json"
                },
            )

            print("")
            print("========== JIRA AUTH DEBUG ==========")
            print(
                "[PIH] /myself STATUS:",
                myself_response.status_code
            )

            print(
                "[PIH] /myself RESPONSE:"
            )

            print(
                myself_response.text
            )
            

            print("=====================================")
            print("")


            while True:

                params = {
                    "jql": settings.jira_jql,

                    "maxResults": 100,

                    "fields": ",".join(
                        [
                            "summary",
                            "description",
                            "status",
                            "issuetype",
                            "priority",
                            "assignee",
                            "updated",
                            "created",
                            "labels",
                            "comment",
                            "parent",
                            "subtasks",
                            "fixVersions",
                            "components",
                        ]
                    ),
                }

                if next_page_token:
                    params[
                        "nextPageToken"
                    ] = next_page_token

                print("")
                print(
                    f"[PIH] Consultando página {page_number}"
                )

                response = await client.get(
                    url,
                    params=params,
                    auth=auth,
                    headers=headers,
                )

                print(
                    "[PIH] URL:",
                    response.request.url,
                )

                print(
                    "[PIH] HTTP STATUS:",
                    response.status_code,
                )

                print("")
                print(
                    "[PIH] RESPUESTA RAW DE JIRA:"
                )

                print(
                    response.text
                )

                print("")
                print(
                    "-----------------------------------------"
                )

                if response.status_code >= 400:

                    raise ValueError(
                        "Error consultando Jira. "
                        f"HTTP {response.status_code}: "
                        f"{response.text}"
                    )

                try:

                    data = response.json()
                    print( 
                        "responseee json", data
                    )
                except Exception as exc:

                    raise ValueError(
                        "Jira respondió con un contenido "
                        "que no es JSON válido."
                    ) from exc

                issues = data.get(
                    "issues",
                    [],
                )

                print(
                    "[PIH] Issues encontrados en esta página:",
                    len(issues),
                )

                all_issues.extend(
                    issues
                )

                next_page_token = data.get(
                    "nextPageToken"
                )

                if not next_page_token:
                    break

                page_number += 1

        print("")
        print(
            "[PIH] TOTAL ISSUES RECIBIDOS:",
            len(all_issues),
        )

        ids: list[int] = []

        for issue in all_issues:

            try:

                artifact_id = (
                    self._process_jira_issue(
                        issue
                    )
                )

                if artifact_id:

                    ids.append(
                        artifact_id
                    )

            except Exception as exc:

                issue_key = issue.get(
                    "key",
                    "SIN-KEY",
                )

                print(
                    "[PIH] Error procesando",
                    issue_key,
                    ":",
                    str(exc),
                )

        print("")
        print(
            "[PIH] TOTAL ISSUES GUARDADOS:",
            len(ids),
        )

        print(
            "========================================="
        )

        print(
            "[PIH] FIN SINCRONIZACIÓN JIRA"
        )

        print(
            "========================================="
        )

        print("")

        db.log(
            "jira_sync_completed",
            {
                "jql": settings.jira_jql,
                "issues_received": len(
                    all_issues
                ),
                "issues_saved": len(ids),
            },
            self.project_id,
        )

        return ids

    # ==========================================================
    # PROCESAMIENTO DE ISSUE JIRA
    # ==========================================================

    def _process_jira_issue(
        self,
        issue: dict[str, Any],
    ) -> int | None:

        fields = issue.get(
            "fields",
            {},
        )

        issue_key = issue.get(
            "key"
        )

        if not issue_key:

            print(
                "[PIH] Issue sin KEY. Ignorado."
            )

            return None

        summary = (
            fields.get("summary")
            or issue_key
        )

        # ------------------------------------------------------
        # TIPO
        # ------------------------------------------------------

        issue_type_data = (
            fields.get("issuetype")
            or {}
        )

        issue_type = (
            issue_type_data.get(
                "name"
            )
            or "Desconocido"
        )

        # ------------------------------------------------------
        # ESTADO
        # ------------------------------------------------------

        status_data = (
            fields.get("status")
            or {}
        )

        status = (
            status_data.get(
                "name"
            )
        )

        # ------------------------------------------------------
        # PRIORIDAD
        # ------------------------------------------------------

        priority_data = (
            fields.get("priority")
            or {}
        )

        priority = (
            priority_data.get(
                "name"
            )
        )

        # ------------------------------------------------------
        # ASIGNADO
        # ------------------------------------------------------

        assignee_data = (
            fields.get("assignee")
            or {}
        )

        assignee = (
            assignee_data.get(
                "displayName"
            )
        )

        # ------------------------------------------------------
        # PADRE / ÉPICA
        # ------------------------------------------------------

        parent_data = (
            fields.get("parent")
            or {}
        )

        parent_key = (
            parent_data.get(
                "key"
            )
        )

        # ------------------------------------------------------
        # SUBTAREAS
        # ------------------------------------------------------

        subtasks = []

        for subtask in (
            fields.get(
                "subtasks",
                [],
            )
            or []
        ):

            subtask_key = (
                subtask.get(
                    "key"
                )
            )

            if subtask_key:

                subtasks.append(
                    subtask_key
                )

        # ------------------------------------------------------
        # COMPONENTES
        # ------------------------------------------------------

        components = []

        for component in (
            fields.get(
                "components",
                [],
            )
            or []
        ):

            component_name = (
                component.get(
                    "name"
                )
            )

            if component_name:

                components.append(
                    component_name
                )

        # ------------------------------------------------------
        # FIX VERSIONS
        # ------------------------------------------------------

        fix_versions = []

        for version in (
            fields.get(
                "fixVersions",
                [],
            )
            or []
        ):

            version_name = (
                version.get(
                    "name"
                )
            )

            if version_name:

                fix_versions.append(
                    version_name
                )

        # ------------------------------------------------------
        # LABELS
        # ------------------------------------------------------

        labels = (
            fields.get(
                "labels",
                [],
            )
            or []
        )

        # ------------------------------------------------------
        # DESCRIPCIÓN
        # ------------------------------------------------------

        description = (
            fields.get(
                "description"
            )
        )

        # ------------------------------------------------------
        # COMENTARIOS
        # ------------------------------------------------------

        comments = (
            fields.get(
                "comment"
            )
        )

        # ------------------------------------------------------
        # CONTENIDO NORMALIZADO
        # ------------------------------------------------------

        content = json.dumps(
            {
                "key": issue_key,

                "summary": summary,

                "description": description,

                "status": status,

                "issue_type": issue_type,

                "priority": priority,

                "assignee": assignee,

                "parent": parent_key,

                "subtasks": subtasks,

                "labels": labels,

                "components": components,

                "fix_versions": fix_versions,

                "comments": comments,
            },
            ensure_ascii=False,
        )

        # ------------------------------------------------------
        # METADATA
        # ------------------------------------------------------

        metadata = {
            "jira_id": issue.get(
                "id"
            ),

            "issue_type": issue_type,

            "status": status,

            "priority": priority,

            "assignee": assignee,

            "parent": parent_key,

            "subtasks": subtasks,

            "labels": labels,

            "components": components,

            "fix_versions": fix_versions,

            "created": fields.get(
                "created"
            ),

            "updated": fields.get(
                "updated"
            ),
        }

        print(
            "[PIH] Guardando:",
            issue_key,
            "-",
            issue_type,
            "-",
            summary,
        )

        artifact_id = self.ingest_artifact(
            artifact_type="jira",
            external_id=issue_key,
            title=summary,
            content=content,
            metadata=metadata,
            source="jira-rest",
        )

        return artifact_id

    # ==========================================================
    # VALIDACIÓN DE CONFIGURACIÓN JIRA
    # ==========================================================

    def _validate_jira_settings(
        self,
    ) -> None:

        missing = []

        if not settings.jira_base_url:

            missing.append(
                "JIRA_BASE_URL"
            )

        if not settings.jira_email:

            missing.append(
                "JIRA_EMAIL"
            )

        if not settings.jira_api_token:

            missing.append(
                "JIRA_API_TOKEN"
            )

        if not settings.jira_jql:

            missing.append(
                "JIRA_JQL"
            )

        if missing:

            raise ValueError(
                "Faltan variables de Jira "
                "en el archivo .env: "
                + ", ".join(
                    missing
                )
            )

    # ==========================================================
    # ATLASSIAN ROVO MCP
    # ==========================================================

    async def list_atlassian_mcp_tools(
        self,
    ) -> list[dict[str, Any]]:
        """
        Conecta con Atlassian Rovo MCP y devuelve
        las herramientas disponibles para el usuario autenticado.
        """

        try:

            from mcp import (
                ClientSession,
                StdioServerParameters,
            )

            from mcp.client.stdio import (
                stdio_client,
            )

        except ImportError as exc:

            raise RuntimeError(
                "El SDK MCP no está instalado. "
                'Ejecutar: pip install "mcp[cli]"'
            ) from exc

        server_params = (
            StdioServerParameters(
                command="npx",
                args=[
                    "-y",
                    "mcp-remote@latest",
                    self.ATLASSIAN_MCP_URL,
                ],
            )
        )

        print(
            "[PIH MCP] Conectando con Atlassian Rovo MCP..."
        )

        async with stdio_client(
            server_params
        ) as (
            read,
            write,
        ):

            async with ClientSession(
                read,
                write,
            ) as session:

                await session.initialize()

                tools_response = (
                    await session.list_tools()
                )

                tools = []

                for tool in (
                    tools_response.tools
                ):

                    tools.append(
                        {
                            "name": tool.name,
                            "description": (
                                tool.description
                            ),
                        }
                    )

                print(
                    "[PIH MCP] Herramientas disponibles:",
                    len(tools),
                )

                db.log(
                    "atlassian_mcp_connected",
                    {
                        "tool_count": len(
                            tools
                        ),
                    },
                    self.project_id,
                )

                return tools

    # ==========================================================
    # EJECUCIÓN DE HERRAMIENTA MCP
    # ==========================================================

    async def call_atlassian_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Ejecuta una herramienta publicada por
        Atlassian Rovo MCP.

        Los nombres de herramientas no se hardcodean.
        Primero debe consultarse list_atlassian_mcp_tools().
        """

        try:

            from mcp import (
                ClientSession,
                StdioServerParameters,
            )

            from mcp.client.stdio import (
                stdio_client,
            )

        except ImportError as exc:

            raise RuntimeError(
                "El SDK MCP no está instalado. "
                'Ejecutar: pip install "mcp[cli]"'
            ) from exc

        server_params = (
            StdioServerParameters(
                command="npx",
                args=[
                    "-y",
                    "mcp-remote@latest",
                    self.ATLASSIAN_MCP_URL,
                ],
            )
        )

        async with stdio_client(
            server_params
        ) as (
            read,
            write,
        ):

            async with ClientSession(
                read,
                write,
            ) as session:

                await session.initialize()

                tools_response = (
                    await session.list_tools()
                )

                available_tools = [
                    tool.name
                    for tool
                    in tools_response.tools
                ]

                if (
                    tool_name
                    not in available_tools
                ):

                    raise ValueError(
                        "Herramienta MCP inexistente: "
                        f"{tool_name}. "
                        "Disponibles: "
                        + ", ".join(
                            available_tools
                        )
                    )

                result = (
                    await session.call_tool(
                        tool_name,
                        arguments=arguments,
                    )
                )

                text_output = []

                for item in (
                    result.content
                    or []
                ):

                    text = getattr(
                        item,
                        "text",
                        None,
                    )

                    if text:

                        text_output.append(
                            text
                        )

                structured = getattr(
                    result,
                    "structuredContent",
                    None,
                )

                if structured is None:

                    structured = getattr(
                        result,
                        "structured_content",
                        None,
                    )

                response = {
                    "tool": tool_name,
                    "text": text_output,
                    "structured": structured,
                }

                db.log(
                    "atlassian_mcp_tool_called",
                    {
                        "tool": tool_name,
                        "arguments": arguments,
                    },
                    self.project_id,
                )

                return response