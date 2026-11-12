from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.sql import func
from ..db import Base
import uuid


def _uuid():
    return str(uuid.uuid4())


class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, nullable=False)
    objective = Column(Text, nullable=False)
    project_name = Column(String, nullable=True)
    project_dir = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending|planning|running|paused|failed|completed|cancelled
    current_model = Column(String, nullable=True)
    previous_model = Column(String, nullable=True)
    priority = Column(String, default="normal")
    optimization_mode = Column(String, default="balanced")
    auto_route = Column(Boolean, default=True)
    plan_json = Column(JSON, default=list)
    context_json = Column(JSON, default=dict)
    result_summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)


class TaskStep(Base):
    __tablename__ = "task_steps"
    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, nullable=False, index=True)
    index = Column(Integer, default=0)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending|running|done|failed|skipped
    assigned_model = Column(String, nullable=True)
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, nullable=False, index=True)
    label = Column(String, nullable=False)
    state_json = Column(JSON, default=dict)
    files_modified = Column(JSON, default=list)
    tests_json = Column(JSON, default=dict)
    completed_work = Column(JSON, default=list)
    pending_work = Column(JSON, default=list)
    handoff_summary = Column(Text, nullable=True)
    current_model = Column(String, nullable=True)
    previous_model = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
