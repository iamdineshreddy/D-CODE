import httpx, os
from typing import List, Dict, Any, Optional
from .base import ProviderAdapter

# Known OpenAI-compatible provider presets
PRESETS = {
    "openai": {"base_url": "https://api.openai.com/v1", "env": "OPENAI_API_KEY"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "env": "OPENROUTER_API_KEY"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "env": "DEEPSEEK_API_KEY"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "env": "GROQ_API_KEY"},
    "together": {"base_url": "https://api.together.xyz/v1", "env": "TOGETHER_API_KEY"},
    "fireworks": {"base_url": "https://api.fireworks.ai/inference/v1", "env": "FIREWORKS_API_KEY"},
    "xai": {"base_url": "https://api.x.ai/v1", "env": "XAI_API_KEY"},
}

# Static model catalogs (costs per 1M tokens). Not exhaustive.
CATALOGS = {
    "openai": [
        {"model_id": "gpt-4o-mini", "context_window": 128000, "supports_tools": True, "supports_vision": True, "cost_in": 0.15, "cost_out": 0.60, "category": "general"},
        {"model_id": "gpt-4o", "context_window": 128000, "supports_tools": True, "supports_vision": True, "cost_in": 2.5, "cost_out": 10.0, "category": "general"},
        {"model_id": "gpt-4.1", "context_window": 1000000, "supports_tools": True, "supports_vision": True, "cost_in": 2.0, "cost_out": 8.0, "category": "general"},
        {"model_id": "o3-mini", "context_window": 200000, "supports_tools": True, "supports_vision": False, "cost_in": 1.1, "cost_out": 4.4, "category": "reasoning"},
    ],
    "deepseek": [
        {"model_id": "deepseek-chat", "context_window": 64000, "supports_tools": True, "supports_vision": False, "cost_in": 0.27, "cost_out": 1.1, "category": "coding"},
        {"model_id": "deepseek-reasoner", "context_window": 64000, "supports_tools": False, "supports_vision": False, "cost_in": 0.55, "cost_out": 2.19, "category": "reasoning"},
    ],
    "groq": [
        {"model_id": "llama-3.3-70b-versatile", "context_window": 128000, "supports_tools": True, "supports_vision": False, "cost_in": 0.59, "cost_out": 0.79, "category": "general"},
        {"model_id": "llama-3.1-8b-instant", "context_window": 128000, "supports_tools": True, "supports_vision": False, "cost_in": 0.05, "cost_out": 0.08, "category": "general"},
    ],
    "openrouter": [
        {"model_id": "openai/gpt-4o-mini", "context_window": 128000, "supports_tools": True, "supports_vision": True, "cost_in": 0.15, "cost_out": 0.6, "category": "general"},
        {"model_id": "anthropic/claude-3.5-sonnet", "context_window": 200000, "supports_tools": True, "supports_vision": True, "cost_in": 3.0, "cost_out": 15.0, "category": "coding"},
        {"model_id": "google/gemini-2.0-flash-001", "context_window": 1000000, "supports_tools": True, "supports_vision": True, "cost_in": 0.1, "cost_out": 0.4, "category": "general"},
    ],
}


class OpenAICompatAdapter(ProviderAdapter):
    def __init__(self, name: str, base_url: str, api_key: Optional[str] = None, env_var: Optional[str] = None):
        super().__init__({"name": name, "base_url": base_url})
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.env_var = env_var
        self.api_key = api_key or (os.getenv(env_var) if env_var else None)

    async def health_check(self) -> Dict[str, Any]:
        if not self.api_key:
            return {"healthy": False, "status": "no_key", "error": "API key not configured"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"})
                if r.status_code == 200:
                    return {"healthy": True, "status": "healthy"}
                if r.status_code == 401:
                    return {"healthy": False, "status": "auth_error", "code": r.status_code}
                if r.status_code == 429:
                    return {"healthy": False, "status": "rate_limited", "code": r.status_code}
                return {"healthy": False, "status": "degraded", "code": r.status_code}
        except Exception as e:
            return {"healthy": False, "status": "down", "error": str(e)}

    async def discover_models(self) -> List[Dict[str, Any]]:
        out = []
        # Try live /models endpoint
        if self.api_key:
            try:
                async with httpx.AsyncClient(timeout=15.0) as c:
                    r = await c.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"})
                    if r.status_code == 200:
                        data = r.json()
                        for m in data.get("data", []):
                            mid = m.get("id")
                            out.append({
                                "provider_name": self.name,
                                "model_id": mid,
                                "display_name": mid,
                                "category": "general",
                                "context_window": m.get("context_window", 8192) or 8192,
                                "supports_tools": True,
                                "supports_vision": False,
                                "supports_streaming": True,
                                "is_local": False,
                                "estimated_cost_input": 0.0,
                                "estimated_cost_output": 0.0,
                                "health": "healthy",
                                "available": True,
                                "quota_remaining": "unknown",
                                "metadata_json": m,
                            })
                        if out:
                            return out
            except Exception:
                pass
        # Fallback to static catalog
        for c in CATALOGS.get(self.name, []):
            out.append({
                "provider_name": self.name,
                "model_id": c["model_id"],
                "display_name": c["model_id"],
                "category": c.get("category", "general"),
                "context_window": c.get("context_window", 8192),
                "supports_tools": c.get("supports_tools", False),
                "supports_vision": c.get("supports_vision", False),
                "supports_streaming": True,
                "is_local": False,
                "estimated_cost_input": c.get("cost_in", 0.0),
                "estimated_cost_output": c.get("cost_out", 0.0),
                "health": "healthy" if self.api_key else "no_key",
                "available": bool(self.api_key),
                "quota_remaining": "unknown",
                "metadata_json": {},
            })
        return out

    async def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("API key not configured")
        payload = {"model": model, "messages": messages, "stream": False}
        if kwargs.get("max_tokens"):
            payload["max_tokens"] = kwargs["max_tokens"]
        async with httpx.AsyncClient(timeout=kwargs.get("timeout", 120.0)) as c:
            r = await c.post(f"{self.base_url}/chat/completions",
                             headers={"Authorization": f"Bearer {self.api_key}"},
                             json=payload)
            if r.status_code == 429:
                raise RuntimeError("rate_limited")
            if r.status_code == 401:
                raise RuntimeError("auth_error")
            if r.status_code == 402:
                raise RuntimeError("credit_exhausted")
            r.raise_for_status()
            data = r.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {}) or {}
        usage = data.get("usage", {}) or {}
        return {
            "content": msg.get("content", ""),
            "model": data.get("model", model),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "raw": data,
        }
