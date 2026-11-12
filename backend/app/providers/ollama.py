import httpx
from typing import List, Dict, Any
from .base import ProviderAdapter
from ..config import OLLAMA_BASE_URL, OLLAMA_API_URL

MODEL_CAPS = {
    # heuristic capability map
}


def _category(name: str) -> str:
    n = name.lower()
    if "coder" in n or "code" in n:
        return "coding"
    if "vision" in n or "llava" in n:
        return "vision"
    return "general"


def _cost(name: str):
    # local => 0
    return 0.0, 0.0


class OllamaAdapter(ProviderAdapter):
    name = "ollama"

    async def health_check(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{OLLAMA_API_URL}/tags")
                if r.status_code == 200:
                    return {"healthy": True, "status": "healthy"}
                return {"healthy": False, "status": "degraded", "code": r.status_code}
        except Exception as e:
            return {"healthy": False, "status": "down", "error": str(e)}

    async def discover_models(self) -> List[Dict[str, Any]]:
        out = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(f"{OLLAMA_API_URL}/tags")
                r.raise_for_status()
                data = r.json()
            for m in data.get("models", []):
                name = m.get("name")
                details = m.get("details", {}) or {}
                ctx = details.get("context_length") or 4096
                # fetch show for capabilities
                caps = []
                try:
                    async with httpx.AsyncClient(timeout=10.0) as c:
                        sr = await c.post(f"{OLLAMA_API_URL}/show", json={"name": name})
                        if sr.status_code == 200:
                            sd = sr.json()
                            caps = sd.get("capabilities", []) or []
                            if sd.get("model_info", {}).get("context_length"):
                                ctx = sd["model_info"]["context_length"]
                except Exception:
                    pass
                supports_tools = "tools" in caps
                out.append({
                    "provider_name": "ollama",
                    "model_id": name,
                    "display_name": name,
                    "category": _category(name),
                    "context_window": int(ctx) if ctx else 4096,
                    "supports_tools": supports_tools,
                    "supports_vision": "vision" in caps,
                    "supports_streaming": True,
                    "is_local": True,
                    "estimated_cost_input": 0.0,
                    "estimated_cost_output": 0.0,
                    "health": "healthy",
                    "available": True,
                    "quota_remaining": "unlimited (local)",
                    "metadata_json": {"size": m.get("size"), "digest": m.get("digest"), "details": details, "capabilities": caps},
                })
        except Exception as e:
            return []
        return out

    async def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        payload = {"model": model, "messages": messages, "stream": False}
        if "options" in kwargs:
            payload["options"] = kwargs["options"]
        async with httpx.AsyncClient(timeout=kwargs.get("timeout", 300.0)) as c:
            r = await c.post(f"{OLLAMA_API_URL}/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        msg = data.get("message", {}) or {}
        return {
            "content": msg.get("content", ""),
            "model": data.get("model", model),
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "raw": data,
        }

    async def unload(self, model: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                await c.post(f"{OLLAMA_API_URL}/generate", json={"model": model, "keep_alive": 0})
            return True
        except Exception:
            return False
