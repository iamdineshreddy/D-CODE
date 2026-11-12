from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models import ModelRecord
from .tokenizer import classify_task, TASK_MODEL_PREFERENCE

# Rough latency tiers
LATENCY = {"ollama": 0.6, "opencode": 0.5}

def _score(m: ModelRecord, task_type: str, prefer_local: bool = True, execution: bool = False) -> float:
    score = 0.0
    caps = TASK_MODEL_PREFERENCE.get(task_type, ["general"])
    if m.category in caps:
        score += 30
    if m.category == "coding" and "coding" in task_type:
        score += 10
    # capability
    if m.supports_tools:
        score += 10
    # context window (bigger better, scaled)
    score += min(m.context_window / 100000.0, 10) * 2
    # local preference for simple
    if m.is_local:
        score += 15 if prefer_local else 5
    else:
        score += 5 if prefer_local else 15
    # prefer lightweight models for simple tasks
    if prefer_local:
        size = (m.metadata_json or {}).get("size") or 0
        if isinstance(size, (int,float)):
            if size and size < 6_000_000_000:
                score += 12
            elif size and size > 15_000_000_000:
                score -= 8
    # cost (lower better)
    cost = (m.estimated_cost_input + m.estimated_cost_output) / 2.0
    score += max(0, 20 - cost * 2)
    # health
    if m.health == "healthy":
        score += 15
    elif m.health in ("no_key",):
        score -= 50
    # availability
    if not m.available:
        score -= 1000
    # quota
    if m.quota_remaining and "exhaust" in str(m.quota_remaining).lower():
        score -= 1000
    # execution preference: prefer tool-capable opencode/cloud models
    if execution:
        if m.provider_name == "opencode":
            score += 40
        if m.is_local:
            score -= 15
    return score

def route(db: Session, task: str, task_type: str = None, manual_model: str = None, execution: bool = False) -> Dict[str, Any]:
    tt = task_type or classify_task(task)
    if manual_model:
        # find model
        m = db.query(ModelRecord).filter(ModelRecord.model_id == manual_model).first()
        if not m:
            # maybe provider/model string
            m = db.query(ModelRecord).filter(ModelRecord.model_id == manual_model.split("/")[-1]).first()
        if m:
            return {
                "selected_model": m.model_id,
                "provider": m.provider_name,
                "reason": "Manual selection",
                "task_type": tt,
                "candidates": [],
            }
    prefer_local = tt in ("simple_coding", "documentation", "testing")
    models = db.query(ModelRecord).filter(ModelRecord.available == True).all()
    cand_list = []
    for m in models:
        if m.health == "no_key":
            continue
        if not m.available:
            continue
        if execution and m.provider_name != "opencode":
            continue
        if execution and m.model_id.startswith("ollama/"):
            continue
        cand_list.append((m, _score(m, tt, prefer_local, execution)))
    cand_list.sort(key=lambda x: x[1], reverse=True)
    candidates = [{"model_id": m.model_id, "provider": m.provider_name, "score": round(s, 1), "cost": m.estimated_cost_input} for m, s in cand_list[:8]]
    if not cand_list:
        return {"selected_model": None, "provider": None, "reason": "No available models", "task_type": tt, "candidates": []}
    best, best_score = cand_list[0]
    return {
        "selected_model": best.model_id,
        "provider": best.provider_name,
        "reason": f"Best score {round(best_score,1)} for {tt}",
        "task_type": tt,
        "candidates": candidates,
    }
