import httpx, os
from typing import List, Dict, Any
from .base import ProviderAdapter

CATALOG = [
    {"model_id": "claude-3-5-sonnet-20241022", "context_window": 200000, "supports_tools": True, "supports_vision": True, "cost_in": 3.0, "cost_out": 15.0, "category": "coding"},
    {"model_id": "claude-3-5-haiku-20241022", "context_window": 200000, "supports_tools": True, "supports_vision": True, "cost_in": 0.8, "cost_out": 4.0, "category": "general"},
    {"model_id": "claude-3-opus-20240229", "context_window": 200000, "supports_tools": True, "supports_vision": True, "cost_in": 15.0, "cost_out": 75.0, "category": "reasoning"},
]

class AnthropicAdapter(ProviderAdapter):
    name = "anthropic"
    def __init__(self, api_key=None):
        super().__init__({})
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1"

    async def health_check(self):
        if not self.api_key:
            return {"healthy": False, "status": "no_key"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(f"{self.base_url}/models", headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
                if r.status_code == 200:
                    return {"healthy": True, "status": "healthy"}
                if r.status_code == 401:
                    return {"healthy": False, "status": "auth_error", "code": 401}
                if r.status_code == 429:
                    return {"healthy": False, "status": "rate_limited", "code": 429}
                return {"healthy": False, "status": "degraded", "code": r.status_code}
        except Exception as e:
            return {"healthy": False, "status": "down", "error": str(e)}

    async def discover_models(self):
        out = []
        for c in CATALOG:
            out.append({
                "provider_name": "anthropic",
                "model_id": c["model_id"],
                "display_name": c["model_id"],
                "category": c["category"],
                "context_window": c["context_window"],
                "supports_tools": c["supports_tools"],
                "supports_vision": c["supports_vision"],
                "supports_streaming": True,
                "is_local": False,
                "estimated_cost_input": c["cost_in"],
                "estimated_cost_output": c["cost_out"],
                "health": "healthy" if self.api_key else "no_key",
                "available": bool(self.api_key),
                "quota_remaining": "unknown",
                "metadata_json": {},
            })
        # try live
        if self.api_key:
            try:
                async with httpx.AsyncClient(timeout=15.0) as c:
                    r = await c.get(f"{self.base_url}/models", headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
                    if r.status_code == 200:
                        data = r.json()
                        live = []
                        for m in data.get("data", []):
                            live.append({
                                "provider_name": "anthropic",
                                "model_id": m.get("id"),
                                "display_name": m.get("display_name", m.get("id")),
                                "category": "general",
                                "context_window": m.get("context_window", 200000) or 200000,
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
                        if live:
                            return live
            except Exception:
                pass
        return out

    async def chat(self, model, messages, **kwargs):
        if not self.api_key:
            raise RuntimeError("auth_error")
        # Convert messages to anthropic format
        system = None
        msgs = []
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content")
            else:
                msgs.append({"role": m.get("role"), "content": m.get("content")})
        payload = {"model": model, "max_tokens": kwargs.get("max_tokens", 4096), "messages": msgs}
        if system:
            payload["system"] = system
        async with httpx.AsyncClient(timeout=kwargs.get("timeout", 120.0)) as c:
            r = await c.post(f"{self.base_url}/messages",
                             headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                             json=payload)
            if r.status_code == 429:
                raise RuntimeError("rate_limited")
            if r.status_code == 401:
                raise RuntimeError("auth_error")
            if r.status_code == 402:
                raise RuntimeError("credit_exhausted")
            r.raise_for_status()
            data = r.json()
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
        usage = data.get("usage", {}) or {}
        return {
            "content": content,
            "model": data.get("model", model),
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "raw": data,
        }
