from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Project Intelligence Hub"
    app_env: str = "local"
    secret_key: str = "change-this-before-deploying"
    database_path: str = "./pih.db"
    cors_origins: str = "http://localhost:5173"

    demo_admin_email: str = "admin@pih.local"
    demo_admin_password: str = "admin123"

    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_jql: str = "project = DEMO ORDER BY updated DESC"

    neo4j_enabled: bool = False
    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "pih-password"

    llm_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    
    google_application_credentials: str = ""
    drive_folder_id: str = ""
    drive_test_cases_folder_id: str = ""

    google_drive_mcp_enabled: bool = False

    google_drive_mcp_url: str = (
        "https://drivemcp.googleapis.com/mcp/v1"
    )

    google_drive_mcp_client_id: str = ""

    google_drive_mcp_client_secret: str = ""

    google_drive_mcp_scopes: str = "https://www.googleapis.com/auth/drive.readonly"

    google_drive_mcp_token_path: str = "./drive_mcp_token.json"

    google_drive_mcp_redirect_port: int = 8765
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def google_drive_mcp_scope_list(self) -> list[str]:
        return [item.strip() for item in self.google_drive_mcp_scopes.split(",") if item.strip()]


settings = Settings()
