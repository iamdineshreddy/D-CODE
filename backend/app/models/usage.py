from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.sql import func
from ..db import Base
import uuid


def _uuid():
    return str(uuid.uuid4())


class UsageRecord(Base):
    __tablename__ = "usage_records"
    id = Column(String, primary_key=True, default=_uuid)
    provider_name = Column(String, nullable=False, index=True)
    model_id = Column(String, nullable=True)
    task_id = Column(String, nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    status = Column(String, default="ok")  # ok | rate_limited | auth_error | exhausted | error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Budget(Base):
    __tablename__ = "budgets"
    id = Column(String, primary_key=True, default=_uuid)
    scope = Column(String, default="global")  # global | provider
    provider_name = Column(String, nullable=True)
    daily_limit_usd = Column(Float, default=5.0)
    monthly_limit_usd = Column(Float, default=20.0)
    alert_threshold = Column(Float, default=0.8)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
