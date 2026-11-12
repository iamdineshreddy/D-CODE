import asyncio
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from ..models import Task, TaskStep
from ..services import provider_registry, prompt_optimizer, model_router, usage_manager, checkpoint_service, git_safety
from ..services.tokenizer import estimate_tokens
from ..config import CHECKPOINT_DIR

async def _execute_one(db: Session, task: Task, model_id: str, provider_name: str, prompt: str, cwd: Optional[str]) -> Dict[str, Any]:
    adapter = provider_registry.get_adapter(provider_name)
    if provider_name == "opencode" and hasattr(adapter, "run_task"):
        res = await adapter.run_task(model_id, prompt, cwd=cwd, timeout=600.0)
        return res
    # For cloud providers, do a single chat (no file edits) - return content
    if adapter is None:
        raise RuntimeError("no adapter")
    messages = [{"role": "user", "content": prompt}]
    r = await adapter.chat(model_id, messages, timeout=300.0)
    return {"returncode": 0, "text": r.get("content", ""), "tokens_in": r.get("prompt_tokens", 0), "tokens_out": r.get("completion_tokens", 0), "session_id": None, "stdout": "", "stderr": ""}

def _available_fallbacks(db: Session, exclude: str, attempted: set = None) -> List[str]:
    from ..models import ModelRecord
    attempted = attempted or set()
    models = db.query(ModelRecord).filter(ModelRecord.available == True).all()
    out = []
    for m in models:
        if m.health == "no_key":
            continue
        if m.model_id == exclude or m.model_id in attempted:
            continue
        out.append(m)
    # sort: opencode first, then local, then others
    def key(m):
        prov = m.provider_name
        if prov == "opencode":
            return (0, m.model_id)
        if m.is_local:
            return (1, m.model_id)
        return (2, m.model_id)
    out.sort(key=key)
    return [m.model_id for m in out]

async def run_task(db: Session, task_id: str) -> Dict[str, Any]:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return {"error": "task not found"}
    task.status = "running"
    db.commit()

    cwd = task.project_dir
    # git checkpoint before
    git_info = {}
    if cwd and git_safety.is_git_repo(cwd):
        git_info = git_safety.create_checkpoint_commit(cwd, f"before task {task.id}")

    # optimize prompt
    opt = await prompt_optimizer.optimize_prompt(task.objective, mode=task.optimization_mode)
    optimized_prompt = opt["optimized"]

    # route model
    if task.auto_route:
        rr = model_router.route(db, task.objective, manual_model=None, execution=True)
    else:
        rr = model_router.route(db, task.objective, manual_model=task.current_model)
    if task.current_model and not task.auto_route:
        pass
    selected = rr.get("selected_model")
    provider_name = rr.get("provider")
    # allow manual
    if task.current_model and not task.auto_route:
        # find provider
        from ..models import ModelRecord
        m = db.query(ModelRecord).filter(ModelRecord.model_id == task.current_model).first()
        if m:
            selected = m.model_id
            provider_name = m.provider_name
    if not selected:
        task.status = "failed"
        task.error = "No available model"
        db.commit()
        return {"error": "no model"}

    task.current_model = selected
    db.commit()

    # initial checkpoint
    checkpoint_service.save_checkpoint(db, task.id, "start", {"prompt": optimized_prompt}, current_model=selected)

    completed_work: List[str] = []
    pending_work: List[str] = ["Execute implementation"]
    files_modified: List[str] = []
    last_error = None
    attempts = 0
    max_attempts = 6
    current_model = selected
    current_provider = provider_name
    attempted_models = set()

    # Build execution prompt for OpenCode
    def build_prompt(model, handoff=None):
        base = (
            "You are an autonomous coding agent. Work in the current repository.\n"
            f"Objective (optimized):\n{optimized_prompt}\n\n"
            "Instructions:\n"
            "- Inspect repository structure first.\n"
            "- Implement required changes.\n"
            "- Run tests if present.\n"
            "- Do not repeat completed work.\n"
            "- Summarize changes and test results at the end.\n"
        )
        if handoff:
            base += "\nHandoff from previous model:\n" + handoff + "\n"
        return base

    while attempts < max_attempts:
        attempts += 1
        attempted_models.add(current_model)
        handoff = None
        if attempts > 1 and last_error:
            # build handoff from last checkpoint
            cp = checkpoint_service.latest_checkpoint(db, task.id)
            handoff = cp.handoff_summary if cp else None
            if not handoff:
                handoff = checkpoint_service.build_handoff_summary(task, completed_work, pending_work, files_modified, last_error)
        prompt = build_prompt(current_model, handoff if attempts > 1 else None)

        # save checkpoint before attempt
        checkpoint_service.save_checkpoint(db, task.id, f"attempt_{attempts}_start",
            {"attempt": attempts, "model": current_model, "prompt": prompt},
            completed=completed_work, pending=pending_work, files_modified=files_modified,
            current_model=current_model, previous_model=task.previous_model,
            handoff=handoff)

        try:
            res = await _execute_one(db, task, current_model, current_provider, prompt, cwd)
        except Exception as e:
            res = {"returncode": 1, "text": "", "stderr": str(e), "tokens_in": 0, "tokens_out": 0}

        rc = res.get("returncode", 0)
        text = res.get("text", "") or ""
        stderr = res.get("stderr", "") or ""
        ti = res.get("tokens_in", 0) or 0
        to = res.get("tokens_out", 0) or 0
        # record usage
        try:
            cost = 0.0
            from ..models import ModelRecord
            mrec = db.query(ModelRecord).filter(ModelRecord.model_id == current_model).first()
            if mrec:
                cost = (ti/1e6)*mrec.estimated_cost_input + (to/1e6)*mrec.estimated_cost_output
            usage_manager.record_usage(db, current_provider, current_model, task.id, ti, to, cost, "ok" if rc == 0 else "error", stderr[:500] if rc != 0 else None)
        except Exception:
            pass

        # update files modified
        if cwd:
            files_modified = git_safety.changed_files(cwd) or files_modified

        # determine success
        failed = False
        err_msg = None
        if rc != 0:
            failed = True
            err_msg = stderr or text or "non-zero exit"
        # If repo provided but no files changed, treat as failure for coding tasks
        if (not failed) and cwd and not files_modified:
            failed = True
            err_msg = "no file changes produced"
        # detect rate limit / auth / credit in output
        low = (stderr + text).lower()
        if any(k in low for k in ["rate_limited", "rate limit", "429"]):
            failed = True; err_msg = "rate_limited"
        if any(k in low for k in ["auth_error", "401", "403", "unauthorized"]):
            failed = True; err_msg = "auth_error"
        if any(k in low for k in ["credit", "402", "exhaust", "insufficient"]):
            failed = True; err_msg = "credit_exhausted"

        if not failed:
            # mark completed
            completed_work.append(f"Attempt {attempts} succeeded with {current_model}")
            pending_work = []
            last_error = None
            checkpoint_service.save_checkpoint(db, task.id, f"attempt_{attempts}_done",
                {"result": text[:4000], "model": current_model},
                files_modified=files_modified, completed=completed_work, pending=pending_work,
                tests={}, current_model=current_model, previous_model=task.previous_model,
                handoff=None)
            task.status = "completed"
            task.result_summary = text[:4000]
            task.current_model = current_model
            db.commit()
            # update project memory
            if task.project_name:
                from ..models import ProjectMemory
                pm = db.query(ProjectMemory).filter(ProjectMemory.project_name == task.project_name).first()
                if pm:
                    pm.completed_tasks = (pm.completed_tasks or []) + [task.title]
                    pm.files_modified = files_modified
                    pm.test_results = {"last": "passed"}
                    db.commit()
            return {"status": "completed", "model": current_model, "result": text[:4000], "files": files_modified}

        # failed: classify
        status = usage_manager.classify_error(err_msg or "")
        # mark model maybe
        last_error = err_msg or stderr or "unknown failure"
        # update checkpoint with handoff
        ho = checkpoint_service.build_handoff_summary(task, completed_work, pending_work, files_modified, last_error)
        checkpoint_service.save_checkpoint(db, task.id, f"attempt_{attempts}_failed",
            {"error": last_error, "model": current_model, "stderr": stderr[:2000]},
            files_modified=files_modified, completed=completed_work, pending=pending_work,
            handoff=ho, current_model=current_model, previous_model=task.previous_model)

        # record failure usage status
        try:
            usage_manager.record_usage(db, current_provider, current_model, task.id, 0, 0, 0.0, status, last_error[:500])
        except Exception:
            pass

        # mark model unavailable for credit/auth exhaustion
        if status in ("credit_exhausted", "auth_error"):
            from ..models import ModelRecord
            mrec = db.query(ModelRecord).filter(ModelRecord.model_id == current_model).first()
            if mrec:
                mrec.available = False
                mrec.health = status
                db.commit()

        # find fallback
        fallbacks = _available_fallbacks(db, current_model, attempted_models)
        if not fallbacks:
            task.status = "paused"
            task.error = last_error
            db.commit()
            return {"status": "paused", "error": last_error, "message": "No fallback model available"}

        # pick next via router among fallbacks: simple choose first healthy
        next_model = None
        next_provider = None
        for fm in fallbacks:
            from ..models import ModelRecord
            mrec = db.query(ModelRecord).filter(ModelRecord.model_id == fm).first()
            if mrec and mrec.health not in ("auth_error", "credit_exhausted", "no_key"):
                next_model = fm
                next_provider = mrec.provider_name
                break
        if not next_model:
            next_model = fallbacks[0]
            from ..models import ModelRecord
            mrec = db.query(ModelRecord).filter(ModelRecord.model_id == next_model).first()
            next_provider = mrec.provider_name if mrec else current_provider

        task.previous_model = current_model
        task.current_model = next_model
        current_model = next_model
        current_provider = next_provider
        db.commit()

    task.status = "failed"
    task.error = last_error
    db.commit()
    return {"status": "failed", "error": last_error}
