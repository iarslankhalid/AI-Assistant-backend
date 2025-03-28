from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.user import User
from . import schemas, services

router = APIRouter()

@router.post("/", response_model=schemas.LabelOut)
def create_label(
    label: schemas.LabelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return services.create_label(db, label, current_user.id)

@router.get("/", response_model=list[schemas.LabelOut])
def get_my_labels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return services.get_labels(db, current_user.id)

@router.get("/{label_id}", response_model=schemas.LabelOut)
def get_label(
    label_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    label = services.get_label(db, label_id, current_user.id)
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")
    return label

@router.put("/{label_id}", response_model=schemas.LabelOut)
def update_label(
    label_id: int,
    label: schemas.LabelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    updated = services.update_label(db, label_id, label, current_user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Label not found")
    return updated

@router.delete("/{label_id}")
def delete_label(
    label_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    deleted = services.delete_label(db, label_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Label not found")
    return {"message": "Label deleted"}
