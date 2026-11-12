from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.sql import func
from ..db import Base
import uuid


def _uuid():
    return str(uuid.uuid4())


class ProjectMemory(Base):
    __tablename__ = "project_memory"
    id = Column(String, primary_key=True, default=_uuid)
    project_name = Column(String, unique=True, nullable=False)
    project_dir = Column(String, nullable=True)
    objective = Column(Text, nullable=True)
    requirements = Column(JSON, default=list)
    architecture = Column(JSON, default=dict)
    files_modified = Column(JSON, default=list)
    completed_tasks = Column(JSON, default=list)
    pending_tasks = Column(JSON, default=list)
    known_bugs = Column(JSON, default=list)
    test_results = Column(JSON, default=dict)
    decisions = Column(JSON, default=list)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
