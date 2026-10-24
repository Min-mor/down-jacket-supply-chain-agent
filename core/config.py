"""全局配置（pydantic-settings）。

所有可调参数都从环境变量 / .env 读取，代码里不硬编码。生产环境通过
环境变量覆盖，示例见根目录 .env.example。
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
    )

    app_name: str = "down-jacket-agent"
    env: str = "dev"  # dev / test / prod

    # ---- LLM（DeepSeek / OpenAI 兼容）----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # ---- 持久化 ----
    # SQLite 零配置；生产可切 Postgres，例如：
    # postgresql+psycopg://user:pass@host:5432/agent
    database_url: str = "sqlite:///./data/agent.db"

    # ---- API ----
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["*"]
    rate_limit_per_minute: int = 60
    # 若设置非空，则请求需带 X-API-Token 头（轻量网关鉴权，完整用户体系另行接入）
    api_token: str = ""

    # ---- 记忆 ----
    max_history_turns: int = 20

    # ---- 日志 ----
    log_level: str = "INFO"
    log_json: bool = True


settings = Settings()
