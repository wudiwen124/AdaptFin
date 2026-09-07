"""配置加载：YAML 默认值 + 环境变量覆盖。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

try:  # .env 支持（可选依赖，不影响离线单测）
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[2]


class DataConfig(BaseModel):
    """数据层配置。sources_priority 中的 demo 会由 router 自动追加到末尾兜底。"""

    sources_priority: list[str] = Field(default_factory=lambda: ["demo"])
    quote_ttl_seconds: int = 60
    kline_ttl_seconds: int = 86400
    financial_ttl_seconds: int = 86400
    max_retries: int = 2
    retry_backoff_seconds: float = 0.4


class ModelConfig(BaseModel):
    provider: str = "openai_compatible"
    base_url: str | None = None
    api_key_env: str = "LLM_API_KEY"
    router_model: str = "glm-4-flash"
    deep_model: str = "deepseek-chat"


class StoreConfig(BaseModel):
    db_path: str = "data/advisor.db"
    checkpoint_db_path: str = "data/checkpoints.db"


class RiskConfig(BaseModel):
    max_questions: int = 10
    max_audit_rounds: int = 2


class MemoryConfig(BaseModel):
    embedder: str = "off"  # off | zhipu | siliconflow | local
    embed_model: str = "BAAI/bge-m3"
    embed_api_key_env: str = "EMBED_API_KEY"
    embed_base_url: str | None = None
    top_k: int = 5
    min_similarity: float = 0.62


class Settings(BaseModel):
    env: str = "dev"
    data: DataConfig = Field(default_factory=DataConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    store: StoreConfig = Field(default_factory=StoreConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """轻量环境覆盖：ADVISOR_SOURCES_PRIORITY / ADVISOR_DB_PATH。"""
    if csv_sources := os.environ.get("ADVISOR_SOURCES_PRIORITY"):
        raw.setdefault("data", {})["sources_priority"] = [
            s.strip() for s in csv_sources.split(",") if s.strip()
        ]
    if db_path := os.environ.get("ADVISOR_DB_PATH"):
        raw.setdefault("store", {})["db_path"] = db_path
    if checkpoint_db_path := os.environ.get("ADVISOR_CHECKPOINT_DB_PATH"):
        raw.setdefault("store", {})["checkpoint_db_path"] = checkpoint_db_path
    if router_model := os.environ.get("ADVISOR_ROUTER_MODEL"):
        raw.setdefault("model", {})["router_model"] = router_model
    if deep_model := os.environ.get("ADVISOR_DEEP_MODEL"):
        raw.setdefault("model", {})["deep_model"] = deep_model
    if base_url := os.environ.get("LLM_BASE_URL"):
        raw.setdefault("model", {})["base_url"] = base_url
    if embedder := os.environ.get("ADVISOR_MEMORY_EMBEDDER"):
        raw.setdefault("memory", {})["embedder"] = embedder
    if embed_model := os.environ.get("ADVISOR_EMBED_MODEL"):
        raw.setdefault("memory", {})["embed_model"] = embed_model
    return raw


def load_settings(path: str | Path | None = None) -> Settings:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env", override=False)
    cfg_path = Path(path) if path else Path(os.environ.get("ADVISOR_SETTINGS_PATH", ROOT / "configs" / "settings.yaml"))
    raw = _load_yaml(cfg_path)
    raw = _apply_env_overrides(raw)
    return Settings.model_validate(raw)
