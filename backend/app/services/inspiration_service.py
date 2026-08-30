"""Business rules for inspirations."""

from collections import OrderedDict

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.inspiration import Inspiration, InspirationStatus
from backend.app.schemas.inspiration import InspirationCreate, InspirationUpdate


def _owned(db: Session, owner_id: int, inspiration_id: int, include_archived: bool = False) -> Inspiration:
    query = db.query(Inspiration).filter(Inspiration.id == inspiration_id, Inspiration.owner_id == owner_id)
    if not include_archived:
        query = query.filter(Inspiration.status != InspirationStatus.ARCHIVED)
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Inspiration not found")
    return item


def list_inspirations(db: Session, owner_id: int, status: str | None, query_text: str | None, skip: int, limit: int):
    query = db.query(Inspiration).filter(Inspiration.owner_id == owner_id, Inspiration.status != InspirationStatus.ARCHIVED)
    if status:
        try:
            query = query.filter(Inspiration.status == InspirationStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid inspiration status") from exc
    if query_text:
        term = f"%{query_text.strip()}%"
        query = query.filter(or_(Inspiration.title.ilike(term), Inspiration.summary.ilike(term), Inspiration.location_name.ilike(term)))
    return query.order_by(Inspiration.updated_at.desc(), Inspiration.id.desc()).offset(skip).limit(limit).all()


def create_inspiration(db: Session, owner_id: int, data: InspirationCreate, *, commit: bool = True):
    item = Inspiration(owner_id=owner_id, visibility="private", **data.model_dump(mode="json"))
    db.add(item)
    if commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return item


def get_inspiration(db: Session, owner_id: int, inspiration_id: int):
    return _owned(db, owner_id, inspiration_id)


def update_inspiration(db: Session, owner_id: int, inspiration_id: int, data: InspirationUpdate):
    item = _owned(db, owner_id, inspiration_id)
    values = data.model_dump(exclude_unset=True, mode="json")
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def archive_inspiration(db: Session, owner_id: int, inspiration_id: int):
    item = _owned(db, owner_id, inspiration_id, include_archived=True)
    item.status = InspirationStatus.ARCHIVED
    db.commit()


def map_points(db: Session, owner_id: int, query_text: str | None = None):
    items = list_inspirations(db, owner_id, None, query_text, 0, 1000)
    items = sorted(items, key=lambda item: (item.created_at, item.id))
    groups = OrderedDict()
    for item in items:
        if item.latitude is None or item.longitude is None:
            continue
        key = f"place:{item.place_id}" if item.place_id else f"coord:{float(item.latitude):.5f},{float(item.longitude):.5f}"
        group = groups.setdefault(key, {"key": key, "name": item.location_name or "地图地点", "latitude": float(item.latitude), "longitude": float(item.longitude), "count": 0, "preview": []})
        group["count"] += 1
        if len(group["preview"]) < 3:
            cover_url = item.cover_url
            if not cover_url and isinstance(item.content, list):
                for block in item.content:
                    if isinstance(block, dict) and block.get("type") == "image":
                        cover_url = block.get("thumb_url") or block.get("url")
                        if cover_url:
                            break
            group["preview"].append({"id": item.id, "title": item.title, "cover_url": cover_url, "updated_at": item.updated_at})
    return list(groups.values())
