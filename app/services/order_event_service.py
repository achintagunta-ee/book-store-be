# app/services/order_event_service.py

from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlmodel import Session
from app.models.order_event import OrderEvent




def log_order_event(
    session: Session,
    order_id: int,
    event_type: str,
    label: str,
    created_by: str = "system",
    meta: Optional[dict] = None,
):
    """
    Append-only event log for order timeline
    """

    event = OrderEvent(
        id=str(uuid4()),
        order_id=order_id,
        event_type=event_type,
        label=label,
        meta=meta,
        created_by=created_by,
        created_at=datetime.utcnow(),
    )

    session.add(event)