from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.sql import func
from ..db import Base
import uuid


def _uuid():
    return str(uuid.uuid4())


class Provider(Base):
    __tablename__ = "providers"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, unique=True, nullable=False)  # ollama, openai, anthropic, ...
    display_name = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # local | cloud | agent
    base_url = Column(String, nullable=True)
    auth_type = Column(String, default="none")  # none | api_key | oauth | cli
    api_key_env = Column(String, nullable=True)  # env var name holding key
    enabled = Column(Boolean, default=True)
    health = Column(String, default="unknown")  # healthy | degraded | down | unknown
    last_checked = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ModelRecord(Base):
    __tablename__ = "models"
    id = Column(String, primary_key=True, default=_uuid)
    provider_name = Column(String, nullable=False, index=True)
    model_id = Column(String, nullable=False)  # e.g. qwen2.5-coder:7b
    display_name = Column(String, nullable=True)
    category = Column(String, default="general")  # coding | reasoning | vision | embedding | general
    context_window = Column(Integer, default=4096)
    supports_tools = Column(Boolean, default=False)
    supports_vision = Column(Boolean, default=False)
    supports_streaming = Column(Boolean, default=True)
    is_local = Column(Boolean, default=False)
    estimated_cost_input = Column(Float, default=0.0)  # USD per 1M tokens
    estimated_cost_output = Column(Float, default=0.0)
    health = Column(String, default="unknown")
    available = Column(Boolean, default=True)
    quota_remaining = Column(String, nullable=True)  # unknown / number
    metadata_json = Column(JSON, default=dict)
    last_seen = Column(DateTime, server_default=func.now())
    __table_args__ = ({"sqlite_autoincrement": True},)
