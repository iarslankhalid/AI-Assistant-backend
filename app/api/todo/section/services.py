from sqlalchemy.orm import Session
from app.db.models.todo.section import Section
from . import schemas

def create_section(db: Session, section: schemas.SectionCreate):
    db_section = Section(**section.dict())
    db.add(db_section)
    db.commit()
    db.refresh(db_section)
    return db_section

def get_sections_by_project(db: Session, project_id: int):
    return db.query(Section).filter(Section.project_id == project_id).all()

def get_section(db: Session, section_id: int):
    return db.query(Section).filter(Section.id == section_id).first()

def update_section(db: Session, section_id: int, section: schemas.SectionUpdate):
    db_section = get_section(db, section_id)
    if db_section:
        for key, value in section.dict(exclude_unset=True).items():
            setattr(db_section, key, value)
        db.commit()
        db.refresh(db_section)
    return db_section

def delete_section(db: Session, section_id: int):
    db_section = get_section(db, section_id)
    if db_section:
        db.delete(db_section)
        db.commit()
    return db_section
