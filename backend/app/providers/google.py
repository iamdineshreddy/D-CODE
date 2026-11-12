import httpx, os
from typing import List, Dict, Any
from .base import ProviderAdapter

CATALOG = [
    {"model_id": "gemini-2.0-flash", "context_window": 1000000, "supports_tools": True, "supports_vision": True, "cost_in": 0.1, "cost_out": 0.4, "category": "general"},
    {"model_id": "gemini-1.5-pro", "context_window": 2000000, "supports_tools": True, "supports_vision": True, "cost_in": 1.25, "cost_out": 5.0, "category": "general"},
    {"model_id": "gemini-1.5-flash", "context_window": 1000000, "supports_tools": True, "supports_vision": True, "cost_in": 0.075, "cost_out": 0.3, "category": "general"},
]

class GoogleAdapter(ProviderAdapter):
    name = "google"
    def __init__(self, api_key=None):
        super().__init__({})
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def health_check(self):
        if not self.api_key:
            return {"healthy": False, "status": "no_key"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(f"{self.base_url}/models?key={self.api_key}")
                if r.status_code == 200:
                    return {"healthy": True, "status": "healthy"}
                if r.status_code == 401 or r.status_code == 403:
                    return {"healthy": False, "status": "auth_error", "code": r.status_code}
                if r.status_code == 429:
                    return {"healthy": False, "status": "rate_limited", "code": 429}
                return {"healthy": False, "status": "degraded", "code": r.status_code}
        except Exception as e:
            return {"healthy": False, "status": "down", "error": str(e)}

    async def discover_models(self):
        out = []
        if self.api_key:
            try:
                async with httpx.AsyncClient(timeout=15.0) as c:
                    r = await c.get(f"{self.base_url}/models?key={self.api_key}")
                    if r.status_code == 200:
                        data = r.json()
                        for m in data.get("models", []):
                            name = m.get("name", "").replace("models/", "")
                            ctx = m.get("inputTokenLimit", 8192) or 8192
                            out.append({
                                "provider_name": "google",
                                "model_id": name,
                                "display_name": m.get("displayName", name),
                                "category": "general",
                                "context_window": ctx,
                                "supports_tools": "generateContent" in (m.get("supportedGenerationMethods") or []),
                                "supports_vision": True,
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
        for c in CATALOG:
            out.append({
                "provider_name": "google",
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
        return out

    async def chat(self, model, messages, **kwargs):
        if not self.api_key:
            raise RuntimeError("auth_error")
        # Build contents
        contents = []
        system_text = None
        for m in messages:
            if m.get("role") == "system":
                system_text = m.get("content")
            else:
                role = "user" if m.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
        payload = {"contents": contents}
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        gen_cfg = {}
        if kwargs.get("max_tokens"):
            gen_cfg["maxOutputTokens"] = kwargs["max_tokens"]
        if gen_cfg:
            payload["generationConfig"] = gen_cfg
        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        async with httpx.AsyncClient(timeout=kwargs.get("timeout", 120.0)) as c:
            r = await c.post(url, json=payload)
            if r.status_code == 429:
                raise RuntimeError("rate_limited")
            if r.status_code in (401, 403):
                raise RuntimeError("auth_error")
            if r.status_code == 402:
                raise RuntimeError("credit_exhausted")
            r.raise_for_status()
            data = r.json()
        text = ""
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                text += part.get("text", "")
        usage = data.get("usageMetadata", {}) or {}
        return {
            "content": text,
            "model": model,
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "raw": data,
        }
