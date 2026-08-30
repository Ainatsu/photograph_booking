"""Private inspiration repository endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.inspiration import InspirationCreate, InspirationMapResponse, InspirationResponse, InspirationUpdate, InspirationUploadResponse
from backend.app.services.inspiration_service import archive_inspiration, create_inspiration, get_inspiration, list_inspirations, map_points, update_inspiration
from backend.app.services.inspiration_generation_service import get_generation_status, retry_failed_batches
from backend.app.utils.file_upload import create_thumbnail_for_url, save_upload_file

router = APIRouter(prefix="/inspirations", tags=["inspirations"])


@router.get("/", response_model=list[InspirationResponse])
def browse(status: str | None = None, query: str | None = None, skip: int = 0, limit: int = 20, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return list_inspirations(db, current_user.id, status, query, max(skip, 0), min(max(limit, 1), 100))


@router.post("/", response_model=InspirationResponse, status_code=201)
def create(data: InspirationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return create_inspiration(db, current_user.id, data)


@router.get("/map", response_model=InspirationMapResponse)
def inspiration_map(query: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return {"points": map_points(db, current_user.id, query)}


@router.post("/upload-images", response_model=InspirationUploadResponse)
async def upload_image(file: UploadFile = File(...), current_user: User = Depends(get_current_active_user)):
    url = await save_upload_file(file, sub_dir=f"inspiration_refs/{current_user.id}")
    return {"url": url, "thumb_url": create_thumbnail_for_url(url)}


@router.post("/{inspiration_id}/generation/retry", response_model=InspirationResponse)
def retry_generation(inspiration_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    item = get_inspiration(db, current_user.id, inspiration_id)
    status = retry_failed_batches(db, owner_id=current_user.id, inspiration_id=inspiration_id)
    return {**item.__dict__, "generation": status}


@router.get("/{inspiration_id}", response_model=InspirationResponse)
def detail(inspiration_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    item = get_inspiration(db, current_user.id, inspiration_id)
    return {**item.__dict__, "generation": get_generation_status(db, owner_id=current_user.id, inspiration_id=inspiration_id)}


@router.put("/{inspiration_id}", response_model=InspirationResponse)
def update(inspiration_id: int, data: InspirationUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return update_inspiration(db, current_user.id, inspiration_id, data)


@router.delete("/{inspiration_id}", status_code=204)
def archive(inspiration_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    archive_inspiration(db, current_user.id, inspiration_id)
    return Response(status_code=204)
