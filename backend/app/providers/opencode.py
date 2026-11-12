import asyncio, json, os, shutil
from typing import List, Dict, Any
from .base import ProviderAdapter

class OpenCodeAdapter(ProviderAdapter):
    name = "opencode"

    def __init__(self):
        super().__init__({})
        self.binary = shutil.which("opencode") or "opencode"

    async def _run(self, args, cwd=None, timeout=120.0):
        proc = await asyncio.create_subprocess_exec(
            self.binary, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        return proc.returncode, stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")

    async def health_check(self):
        try:
            rc, out, err = await self._run(["--version"], timeout=15.0)
            if rc == 0:
                return {"healthy": True, "status": "healthy", "version": out.strip()}
            return {"healthy": False, "status": "down", "error": err}
        except Exception as e:
            return {"healthy": False, "status": "down", "error": str(e)}

    async def discover_models(self):
        out = []
        try:
            rc, stdout, err = await self._run(["models"], timeout=30.0)
            if rc != 0:
                return out
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                # format: provider/model or provider/model#variant
                # OpenCode models are all under "opencode/" provider namespace in registry? 
                # We'll register with provider_name=opencode and model_id=full id
                is_free = "free" in line.lower()
                ctx = 128000
                out.append({
                    "provider_name": "opencode",
                    "model_id": line,
                    "display_name": line,
                    "category": "coding",
                    "context_window": ctx,
                    "supports_tools": True,
                    "supports_vision": False,
                    "supports_streaming": True,
                    "is_local": False,
                    "estimated_cost_input": 0.0,
                    "estimated_cost_output": 0.0,
                    "health": "healthy",
                    "available": True,
                    "quota_remaining": "free" if is_free else "unknown",
                    "metadata_json": {"free": is_free},
                })
        except Exception:
            pass
        # Also include ollama/* models exposed via opencode
        # (already in ollama provider; skip duplicates but opencode can run them too)
        return out

    async def run_task(self, model: str, prompt: str, cwd: str = None, session_id: str = None, timeout: float = 300.0):
        args = ["run", "--model", model, "--format", "json", "--auto"]
        if session_id:
            args += ["--session", session_id]
        args += [prompt]
        rc, stdout, stderr = await self._run(args, cwd=cwd, timeout=timeout)
        # Parse JSON lines
        texts = []
        session = None
        tokens_in = 0
        tokens_out = 0
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("sessionID"):
                session = obj["sessionID"]
            t = obj.get("type")
            part = obj.get("part", {}) or {}
            if t == "text":
                texts.append(part.get("text", ""))
            if t == "step_finish":
                tok = part.get("tokens", {}) or {}
                tokens_in += tok.get("input", 0)
                tokens_out += tok.get("output", 0)
        return {
            "returncode": rc,
            "stdout": stdout,
            "stderr": stderr,
            "text": "\n".join(texts).strip(),
            "session_id": session,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
