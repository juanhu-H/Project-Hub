from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx2
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ..config import settings


class GoogleDriveMCPClient:

    def __init__(self):
        self.server_url = settings.google_drive_mcp_url

    def _http_client(self) -> httpx2.AsyncClient:
        credentials_path = settings.google_application_credentials
        if not credentials_path:
            raise RuntimeError(
                "Falta GOOGLE_APPLICATION_CREDENTIALS para autenticar Google Drive MCP."
            )

        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        credentials.refresh(Request())
        return httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {credentials.token}"}
        )

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[tuple[Any, Any]]:
        async with self._http_client() as http_client:
            async with streamable_http_client(
                self.server_url,
                http_client=http_client,
            ) as streams:
                yield streams

    async def list_tools(
        self,
    ) -> list[dict[str, Any]]:

        print("")
        print("========================================")
        print("[PIH MCP] CONECTANDO A GOOGLE DRIVE MCP")
        print("========================================")
        print(
            "[PIH MCP] Server URL:",
            self.server_url,
        )

        async with self._connection() as (
            read_stream,
            write_stream,
        ):

            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:

                print(
                    "[PIH MCP] Inicializando sesión..."
                )

                await session.initialize()

                print(
                    "[PIH MCP] Solicitando tools/list..."
                )

                response = (
                    await session.list_tools()
                )

                tools = []

                for tool in response.tools:

                    tools.append(
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": getattr(
                                tool,
                                "input_schema",
                                None,
                            ),
                        }
                    ) 

                print(
                    "[PIH MCP] Tools encontradas:",
                    len(tools),
                )

                return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        async with self._connection() as (
            read_stream,
            write_stream,
        ):

            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:

                await session.initialize()

                available_response = (
                    await session.list_tools()
                )

                available_tools = [
                    tool.name
                    for tool
                    in available_response.tools
                ]

                if tool_name not in available_tools:

                    raise ValueError(
                        "La herramienta MCP "
                        f"'{tool_name}' no existe. "
                        "Disponibles: "
                        + ", ".join(
                            available_tools
                        )
                    )

                result = await session.call_tool(
                    tool_name,
                    arguments=arguments,
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

                    return {
                        "tool": tool_name,
                        "text": text_output,
                        "structured": structured,
                        "is_error": bool(getattr(result, "isError", False)),
                    }
