from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models import UsageRecord, Budget
from datetime import datetime, timedelta
from ..config import DEFAULT_DAILY_BUDGET, DEFAULT_MONTHLY_BUDGET


def record_usage(db: Session, provider_name: str, model_id: str = None, task_id: str = None,
                 input_tokens: int = 0, output_tokens: int = 0, estimated_cost: float = 0.0,
                 status: str = "ok", error_message: str = None):
    rec = UsageRecord(
        provider_name=provider_name,
        model_id=model_id,
        task_id=task_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
        status=status,
        error_message=error_message,
    )
    db.add(rec)
    db.commit()
    return rec


def classify_error(msg: str) -> str:
    m = (msg or "").lower()
    if "rate_limit" in m or "429" in m:
        return "rate_limited"
    if "auth" in m or "401" in m or "403" in m:
        return "auth_error"
    if "credit" in m or "402" in m or "exhaust" in m or "insufficient" in m:
        return "credit_exhausted"
    return "error"


def get_budget(db: Session, scope="global", provider_name=None):
    b = db.query(Budget).filter(Budget.scope == scope, Budget.provider_name == provider_name).first()
    if not b:
        b = Budget(scope=scope, provider_name=provider_name,
                   daily_limit_usd=DEFAULT_DAILY_BUDGET, monthly_limit_usd=DEFAULT_MONTHLY_BUDGET)
        db.add(b)
        db.commit()
        db.refresh(b)
    return b


def budget_status(db: Session) -> Dict[str, Any]:
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    recs = db.query(UsageRecord).all()
    month_cost = sum(r.estimated_cost for r in recs if r.created_at >= month_start)
    day_cost = sum(r.estimated_cost for r in recs if r.created_at >= day_start)
    b = get_budget(db)
    return {
        "daily_spent": round(day_cost, 4),
        "daily_limit": b.daily_limit_usd,
        "monthly_spent": round(month_cost, 4),
        "monthly_limit": b.monthly_limit_usd,
        "daily_remaining": round(max(0, b.daily_limit_usd - day_cost), 4),
        "monthly_remaining": round(max(0, b.monthly_limit_usd - month_cost), 4),
    }


def is_budget_exceeded(db: Session) -> bool:
    bs = budget_status(db)
    return bs["daily_remaining"] <= 0 or bs["monthly_remaining"] <= 0


def usage_summary(db: Session) -> Dict[str, Any]:
    recs = db.query(UsageRecord).all()
    total_in = sum(r.input_tokens for r in recs)
    total_out = sum(r.output_tokens for r in recs)
    total_cost = sum(r.estimated_cost for r in recs)
    by_provider = {}
    by_model = {}
    for r in recs:
        by_provider.setdefault(r.provider_name, {"provider": r.provider_name, "input": 0, "output": 0, "cost": 0.0, "calls": 0})
        by_provider[r.provider_name]["input"] += r.input_tokens
        by_provider[r.provider_name]["output"] += r.output_tokens
        by_provider[r.provider_name]["cost"] += r.estimated_cost
        by_provider[r.provider_name]["calls"] += 1
        key = f"{r.provider_name}/{r.model_id}"
        by_model.setdefault(key, {"model": key, "input": 0, "output": 0, "cost": 0.0, "calls": 0})
        by_model[key]["input"] += r.input_tokens
        by_model[key]["output"] += r.output_tokens
        by_model[key]["cost"] += r.estimated_cost
        by_model[key]["calls"] += 1
    return {
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_cost": round(total_cost, 4),
        "by_provider": list(by_provider.values()),
        "by_model": list(by_model.values()),
    }
