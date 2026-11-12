from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.sql import func
from ..db import Base
import uuid


def _uuid():
    return str(uuid.uuid4())


class ApprovalRequest(Base):
    __tablename__ = "approvals"
    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending|approved|rejected
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)
