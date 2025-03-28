from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.user import User
from . import schemas, services

router = APIRouter()

@router.post("/", response_model=schemas.SectionOut)
def create_section(
    section: schemas.SectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # You can optionally check if current_user owns the project here
    return services.create_section(db, section)

@router.get("/project/{project_id}", response_model=list[schemas.SectionOut])
def get_project_sections(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return services.get_sections_by_project(db, project_id)

@router.get("/{section_id}", response_model=schemas.SectionOut)
def read_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    section = services.get_section(db, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section

@router.put("/{section_id}", response_model=schemas.SectionOut)
def update_section(
    section_id: int,
    section: schemas.SectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    updated = services.update_section(db, section_id, section)
    if not updated:
        raise HTTPException(status_code=404, detail="Section not found")
    return updated

@router.delete("/{section_id}")
def delete_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    deleted = services.delete_section(db, section_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Section not found")
    return {"message": "Section deleted"}
