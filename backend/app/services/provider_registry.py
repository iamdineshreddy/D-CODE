import os
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..models import Provider, ModelRecord
from ..providers.ollama import OllamaAdapter
from ..providers.opencode import OpenCodeAdapter
from ..providers.openai_compat import OpenAICompatAdapter, PRESETS
from ..providers.anthropic import AnthropicAdapter
from ..providers.google import GoogleAdapter
from ..config import OLLAMA_BASE_URL

# Adapter cache
_adapters: Dict[str, Any] = {}


def get_adapter(name: str):
    if name in _adapters:
        return _adapters[name]
    # Build on demand
    if name == "ollama":
        a = OllamaAdapter()
    elif name == "opencode":
        a = OpenCodeAdapter()
    elif name == "anthropic":
        a = AnthropicAdapter()
    elif name == "google":
        a = GoogleAdapter()
    elif name in PRESETS:
        p = PRESETS[name]
        a = OpenAICompatAdapter(name, p["base_url"], env_var=p["env"])
    else:
        return None
    _adapters[name] = a
    return a


def list_provider_names():
    names = ["ollama", "opencode", "anthropic", "google"] + list(PRESETS.keys())
    return names


def seed_providers(db: Session):
    for name in list_provider_names():
        existing = db.query(Provider).filter(Provider.name == name).first()
        if existing:
            continue
        kind = "local" if name in ("ollama",) else ("agent" if name == "opencode" else "cloud")
        display = name.title()
        adapter = get_adapter(name)
        env_var = None
        base_url = None
        if name in PRESETS:
            env_var = PRESETS[name]["env"]
            base_url = PRESETS[name]["base_url"]
        if name == "ollama":
            base_url = OLLAMA_BASE_URL
        p = Provider(
            name=name,
            display_name=display,
            kind=kind,
            base_url=base_url,
            auth_type="none" if name in ("ollama", "opencode") else "api_key",
            api_key_env=env_var,
            enabled=True,
        )
        db.add(p)
    db.commit()


async def refresh_provider(db: Session, name: str):
    adapter = get_adapter(name)
    if adapter is None:
        return {"error": "unknown provider"}
    # update provider health
    prov = db.query(Provider).filter(Provider.name == name).first()
    health = await adapter.health_check()
    status = health.get("status", "unknown")
    if prov:
        prov.health = "healthy" if health.get("healthy") else status
        prov.last_checked = __import__("datetime").datetime.utcnow()
        db.commit()
    # discover models
    models = await adapter.discover_models()
    # upsert
    seen = set()
    for m in models:
        seen.add(m["model_id"])
        existing = db.query(ModelRecord).filter(
            ModelRecord.provider_name == name,
            ModelRecord.model_id == m["model_id"],
        ).first()
        if existing:
            for k, v in m.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
        else:
            db.add(ModelRecord(**m))
    if seen:
        db.query(ModelRecord).filter(ModelRecord.provider_name == name).filter(
            ~ModelRecord.model_id.in_(seen)
        ).update({"available": False}, synchronize_session=False)
    db.commit()
    db.commit()
    return {"provider": name, "health": status, "models": len(models)}


async def refresh_all(db: Session):
    results = {}
    for name in list_provider_names():
        try:
            results[name] = await refresh_provider(db, name)
        except Exception as e:
            results[name] = {"error": str(e)}
    return results
