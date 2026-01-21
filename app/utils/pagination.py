from sqlalchemy import func
from sqlmodel import select
from typing import Any


def paginate(
    *,
    session,
    query,
    page: int = 1,
    limit: int = 10,
):
    if page < 1:
        page = 1

    if limit < 1:
        limit = 10

    offset = (page - 1) * limit

    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()

    results = session.exec(
        query.offset(offset).limit(limit)
    ).all()

    return {
        "total_items": total,
        "total_pages": (total + limit - 1) // limit,
        "current_page": page,
        "limit": limit,
        "results": results,
    }
