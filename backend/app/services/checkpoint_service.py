from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..models import Checkpoint, Task
import json, os
from ..config import CHECKPOINT_DIR

def save_checkpoint(db: Session, task_id: str, label: str, state: Dict[str, Any],
                    files_modified: List = None, tests: Dict = None,
                    completed: List = None, pending: List = None,
                    handoff: str = None, current_model: str = None,
                    previous_model: str = None) -> Checkpoint:
    cp = Checkpoint(
        task_id=task_id,
        label=label,
        state_json=state or {},
        files_modified=files_modified or [],
        tests_json=tests or {},
        completed_work=completed or [],
        pending_work=pending or [],
        handoff_summary=handoff,
        current_model=current_model,
        previous_model=previous_model,
    )
    db.add(cp)
    db.commit()
    db.refresh(cp)
    # also write JSON file
    try:
        path = CHECKPOINT_DIR / f"{task_id}_{cp.id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "task_id": task_id, "label": label, "state": state,
                "files_modified": files_modified or [], "tests": tests or {},
                "completed": completed or [], "pending": pending or [],
                "handoff": handoff, "current_model": current_model,
                "previous_model": previous_model,
            }, f, indent=2, default=str)
    except Exception:
        pass
    return cp

def list_checkpoints(db: Session, task_id: str):
    return db.query(Checkpoint).filter(Checkpoint.task_id == task_id).order_by(Checkpoint.created_at.desc()).all()

def latest_checkpoint(db: Session, task_id: str):
    return db.query(Checkpoint).filter(Checkpoint.task_id == task_id).order_by(Checkpoint.created_at.desc()).first()

def build_handoff_summary(task, completed: List, pending: List, files: List, errors: str = None, tests: Dict = None) -> str:
    parts = []
    parts.append(f"Task: {task.title}")
    parts.append(f"Objective: {task.objective}")
    if completed:
        parts.append("Completed work:")
        for c in completed:
            parts.append(f"  - {c}")
    if pending:
        parts.append("Pending work:")
        for p in pending:
            parts.append(f"  - {p}")
    if files:
        parts.append("Files modified: " + ", ".join(files))
    if tests:
        parts.append(f"Tests: {tests}")
    if errors:
        parts.append(f"Last error: {errors}")
    parts.append("Continue only the pending work. Do not repeat completed work. Inspect repository before changes.")
    return "\n".join(parts)
