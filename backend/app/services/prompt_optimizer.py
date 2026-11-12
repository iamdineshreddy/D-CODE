import httpx
from typing import Dict, Any, List
from .tokenizer import estimate_tokens, classify_task
from ..config import OLLAMA_API_URL, DEFAULT_LOCAL_OPTIMIZER

MODE_INSTRUCTIONS = {
    "balanced": "Reduce redundant wording and filler while preserving all technical requirements and constraints. Keep structure.",
    "aggressive": "Maximize safe token reduction: remove redundancy, merge duplicate instructions, compress examples, but NEVER drop requirements, constraints, or acceptance criteria.",
    "high_quality": "Preserve detailed context and instructions; only remove obvious filler and repetitions. Prioritize clarity and completeness over token savings.",
}


def _heuristic_optimize(text: str, mode: str) -> str:
    # Basic cleanup: collapse multiple blank lines, trim trailing spaces
    lines = [ln.rstrip() for ln in text.splitlines()]
    out = []
    blank = 0
    for ln in lines:
        if ln.strip() == "":
            blank += 1
            if blank <= 1:
                out.append(ln)
        else:
            blank = 0
            out.append(ln)
    res = "\n".join(out).strip()
    return res


async def optimize_prompt(prompt: str, mode: str = "balanced", model: str = None, task_type: str = None) -> Dict[str, Any]:
    original_tokens = estimate_tokens(prompt)
    notes: List[str] = []
    # Lightweight heuristic: if very short, skip LLM
    if len(prompt) < 200:
        optimized = _heuristic_optimize(prompt, mode)
        return {
            "original": prompt,
            "optimized": optimized,
            "mode": mode,
            "original_tokens_est": original_tokens,
            "optimized_tokens_est": estimate_tokens(optimized),
            "savings_pct": round((1 - estimate_tokens(optimized)/max(1, original_tokens))*100, 1),
            "notes": ["Prompt short; heuristic cleanup only."],
        }

    opt_model = model or DEFAULT_LOCAL_OPTIMIZER
    tt = task_type or classify_task(prompt)
    system = (
        "You are a prompt optimization engine. Rewrite the user's request into a concise, structured implementation specification.\n"
        f"Mode: {mode}. {MODE_INSTRUCTIONS.get(mode, '')}\n"
        "Rules:\n"
        "- Preserve ALL requirements, constraints, acceptance criteria, technical context.\n"
        "- Remove filler, redundant instructions, repeated context.\n"
        "- Output only the optimized prompt/specification, no commentary, no extra constraints not implied.\n"
        "- Be concise: aim for fewer tokens than the input.\n"
        "- Use compact bullet lists; avoid verbose explanations.\n"
    )
    user = f"Task type: {tt}\n\nOriginal request:\n{prompt}\n\nOptimized specification:"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    optimized = None
    try:
        async with httpx.AsyncClient(timeout=120.0) as c:
            r = await c.post(f"{OLLAMA_API_URL}/chat", json={"model": opt_model, "messages": messages, "stream": False})
            r.raise_for_status()
            data = r.json()
            optimized = (data.get("message", {}) or {}).get("content", "").strip()
    except Exception as e:
        notes.append(f"LLM optimization unavailable ({e}); using heuristic.")
        optimized = None

    if not optimized:
        optimized = _heuristic_optimize(prompt, mode)
    else:
        # safety: ensure not too aggressive
        if mode != "aggressive" and estimate_tokens(optimized) < 0.3 * original_tokens and original_tokens > 100:
            notes.append("Optimization too aggressive; reverted to balanced heuristic.")
            optimized = _heuristic_optimize(prompt, "balanced")
        # if no reduction, fall back to heuristic
        if estimate_tokens(optimized) >= original_tokens and mode in ("balanced","aggressive"):
            ho = _heuristic_optimize(prompt, mode)
            if estimate_tokens(ho) < estimate_tokens(optimized):
                optimized = ho
                notes.append("LLM did not reduce tokens; used heuristic compaction.")
    optimized = _heuristic_optimize(optimized, mode)
    opt_tokens = estimate_tokens(optimized)
    savings = round((1 - opt_tokens / max(1, original_tokens)) * 100, 1)
    if savings < 0:
        savings = 0.0
    return {
        "original": prompt,
        "optimized": optimized,
        "mode": mode,
        "original_tokens_est": original_tokens,
        "optimized_tokens_est": opt_tokens,
        "savings_pct": savings,
        "notes": notes,
    }
