import os, asyncio
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .db import init_db, get_db, SessionLocal
from . import models
from .schemas.common import *
from .services import provider_registry, usage_manager, model_router, prompt_optimizer, checkpoint_service, task_executor
from .config import *

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    init_db()
    db = SessionLocal()
    try:
        provider_registry.seed_providers(db)
        usage_manager.get_budget(db)
    finally:
        db.close()
    async def _refresh():
        db = SessionLocal()
        try:
            await provider_registry.refresh_all(db)
        finally:
            db.close()
    try:
        await _refresh()
    except Exception:
        pass
    yield

app = FastAPI(title="D-ORCHESTRATOR", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "D-ORCHESTRATOR"}

# Providers
@app.get("/api/providers")
def list_providers(db: Session = Depends(get_db)):
    provs = db.query(models.Provider).all()
    return [ProviderOut.model_validate(p) for p in provs]

@app.post("/api/providers/{name}/refresh")
async def refresh_provider(name: str, db: Session = Depends(get_db)):
    r = await provider_registry.refresh_provider(db, name)
    return r

@app.post("/api/providers/refresh-all")
async def refresh_all(db: Session = Depends(get_db)):
    return await provider_registry.refresh_all(db)

@app.get("/api/providers/{name}/health")
async def provider_health(name: str):
    adapter = provider_registry.get_adapter(name)
    if adapter is None:
        raise HTTPException(404, "unknown provider")
    return await adapter.health_check()

# Models
@app.get("/api/models")
def list_models(db: Session = Depends(get_db)):
    ms = db.query(models.ModelRecord).all()
    return [ModelOut.model_validate(m) for m in ms]

@app.post("/api/models/rediscover")
async def rediscover(db: Session = Depends(get_db)):
    return await provider_registry.refresh_all(db)

# Prompt optimizer
@app.post("/api/optimize")
async def optimize(req: OptimizeRequest, db: Session = Depends(get_db)):
    res = await prompt_optimizer.optimize_prompt(req.prompt, req.mode, req.model, req.task_type)
    return OptimizeResult(**res)

# Router
@app.post("/api/route")
def route(req: RouteRequest, db: Session = Depends(get_db)):
    r = model_router.route(db, req.task, req.task_type, req.manual_model)
    return RouteResult(**{k: r[k] for k in ["selected_model","provider","reason","task_type","candidates"]})

# Tasks
@app.post("/api/tasks")
def create_task(req: TaskCreate, db: Session = Depends(get_db)):
    t = models.Task(
        title=req.title,
        objective=req.objective,
        project_name=req.project_name,
        project_dir=req.project_dir,
        optimization_mode=req.optimization_mode,
        auto_route=req.auto_route,
        current_model=req.manual_model,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    # project memory
    if req.project_name:
        pm = db.query(models.ProjectMemory).filter(models.ProjectMemory.project_name == req.project_name).first()
        if not pm:
            pm = models.ProjectMemory(project_name=req.project_name, project_dir=req.project_dir, objective=req.objective)
            db.add(pm)
            db.commit()
    return TaskOut.model_validate(t)

@app.get("/api/tasks")
def list_tasks(db: Session = Depends(get_db)):
    ts = db.query(models.Task).order_by(models.Task.created_at.desc()).all()
    return [TaskOut.model_validate(t) for t in ts]

@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    t = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not t:
        raise HTTPException(404, "task not found")
    return TaskOut.model_validate(t)

@app.post("/api/tasks/{task_id}/run")
async def run_task_endpoint(task_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    t = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not t:
        raise HTTPException(404, "task not found")
    # run in background
    async def _run():
        db2 = SessionLocal()
        try:
            await task_executor.run_task(db2, task_id)
        finally:
            db2.close()
    background_tasks.add_task(_run)
    return {"status": "started", "task_id": task_id}

@app.post("/api/tasks/{task_id}/run-sync")
async def run_task_sync(task_id: str, db: Session = Depends(get_db)):
    db2 = SessionLocal()
    try:
        return await task_executor.run_task(db2, task_id)
    finally:
        db2.close()

@app.post("/api/tasks/{task_id}/pause")
def pause_task(task_id: str, db: Session = Depends(get_db)):
    t = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not t:
        raise HTTPException(404)
    t.status = "paused"
    db.commit()
    return {"status": "paused"}

@app.get("/api/tasks/{task_id}/checkpoints")
def list_checkpoints(task_id: str, db: Session = Depends(get_db)):
    cps = checkpoint_service.list_checkpoints(db, task_id)
    return [CheckpointOut.model_validate(c) for c in cps]

@app.post("/api/tasks/{task_id}/recover")
async def recover_task(task_id: str, db: Session = Depends(get_db)):
    # resume using latest checkpoint
    t = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not t:
        raise HTTPException(404)
    t.status = "pending"
    db.commit()
    db2 = SessionLocal()
    try:
        return await task_executor.run_task(db2, task_id)
    finally:
        db2.close()

# Usage
@app.get("/api/usage/summary")
def usage_summary(db: Session = Depends(get_db)):
    return usage_manager.usage_summary(db)

@app.get("/api/usage/budget")
def budget_status(db: Session = Depends(get_db)):
    return usage_manager.budget_status(db)

@app.get("/api/usage/records")
def usage_records(limit: int = 100, db: Session = Depends(get_db)):
    recs = db.query(models.UsageRecord).order_by(models.UsageRecord.created_at.desc()).limit(limit).all()
    return recs

# Approvals
@app.get("/api/approvals")
def list_approvals(db: Session = Depends(get_db)):
    aps = db.query(models.ApprovalRequest).order_by(models.ApprovalRequest.created_at.desc()).all()
    return [ApprovalOut.model_validate(a) for a in aps]

@app.post("/api/approvals/{aid}/resolve")
def resolve_approval(aid: str, status: str, db: Session = Depends(get_db)):
    a = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == aid).first()
    if not a:
        raise HTTPException(404)
    a.status = status
    from datetime import datetime
    a.resolved_at = datetime.utcnow()
    db.commit()
    return {"status": status}

# Project memory
@app.get("/api/memory")
def list_memory(db: Session = Depends(get_db)):
    return db.query(models.ProjectMemory).all()

@app.get("/api/memory/{name}")
def get_memory(name: str, db: Session = Depends(get_db)):
    pm = db.query(models.ProjectMemory).filter(models.ProjectMemory.project_name == name).first()
    if not pm:
        raise HTTPException(404)
    return pm

# Settings: budget update
@app.put("/api/settings/budget")
def update_budget(daily: float = None, monthly: float = None, db: Session = Depends(get_db)):
    b = usage_manager.get_budget(db)
    if daily is not None:
        b.daily_limit_usd = daily
    if monthly is not None:
        b.monthly_limit_usd = monthly
    db.commit()
    return usage_manager.budget_status(db)

# Overview stats
@app.get("/api/overview")
def overview(db: Session = Depends(get_db)):
    tasks = db.query(models.Task).all()
    models_list = db.query(models.ModelRecord).all()
    provs = db.query(models.Provider).all()
    bs = usage_manager.budget_status(db)
    us = usage_manager.usage_summary(db)
    return {
        "tasks": {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.status == "pending"),
            "running": sum(1 for t in tasks if t.status == "running"),
            "completed": sum(1 for t in tasks if t.status == "completed"),
            "failed": sum(1 for t in tasks if t.status == "failed"),
            "paused": sum(1 for t in tasks if t.status == "paused"),
        },
        "models": {
            "total": len(models_list),
            "available": sum(1 for m in models_list if m.available),
            "local": sum(1 for m in models_list if m.is_local),
        },
        "providers": {
            "total": len(provs),
            "healthy": sum(1 for p in provs if p.health == "healthy"),
        },
        "budget": bs,
        "usage": us,
    }

# Serve frontend static if built
from fastapi.staticfiles import StaticFiles
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
