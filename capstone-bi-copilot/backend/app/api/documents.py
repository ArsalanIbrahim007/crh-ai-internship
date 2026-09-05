from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.document_service import document_service
from app.services.rag_service import rag_service
from app.services import document_workspace as workspace
from app.core.security import get_current_user
from app.db.models import DocumentDetails, DocumentFolder, User

router = APIRouter(prefix='/documents', tags=['documents'])


class FolderInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Folder name cannot be empty')
        return value


class MoveInput(BaseModel):
    folder_id: str | None = None


@router.get('')
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return workspace.list_documents(db, user)


async def ingest_upload(file: UploadFile, db: Session, allowed_roles: str | None = None, folder_id: str | None = None):
    content = await file.read()
    if not content:
        raise HTTPException(400, 'The uploaded file is empty')
    try:
        did = document_service.ingest(db, file.filename or 'upload.bin', content,
                                      file.content_type or 'application/octet-stream', allowed_roles)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        db.rollback()
        raise HTTPException(422, 'Could not process this file. Check that it is a valid supported document.') from error
    db.add(DocumentDetails(document_id=did, folder_id=folder_id, size=len(content)))
    db.commit()
    return {'document_id': did, 'filename': file.filename, 'folder_id': folder_id}


@router.post('/upload')
async def upload(file: UploadFile = File(...), allowed_roles: str | None = Form(None), db: Session = Depends(get_db)):
    # Preserve the existing ingestion endpoint and its clients.
    return await ingest_upload(file, db, allowed_roles)


@router.get('/search')
def search(q: str, role: str = 'manager', db: Session = Depends(get_db)):
    return [{'source_id': x.source_id, 'title': x.title, 'snippet': x.text[:240], 'score': x.score}
            for x in rag_service.hybrid_search(db, q, role)]


@router.get('/folders')
def folders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [workspace.folder_json(folder, db.query(DocumentDetails).filter_by(folder_id=folder.id).count())
            for folder in db.query(DocumentFolder).filter_by(owner_id=user.id).order_by(DocumentFolder.name)]


@router.post('/folders', status_code=201)
def create_folder(payload: FolderInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return workspace.folder_json(workspace.create_folder(db, user, payload.name), 0)


@router.patch('/folders/{folder_id}')
def rename_folder(folder_id: str, payload: FolderInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    folder = workspace.require_folder(db, folder_id, user)
    if db.query(DocumentFolder).filter(DocumentFolder.owner_id == user.id, DocumentFolder.name == payload.name,
                                       DocumentFolder.id != folder_id).first():
        raise HTTPException(409, 'A folder with that name already exists')
    folder.name = payload.name
    db.commit()
    return workspace.folder_json(folder, db.query(DocumentDetails).filter_by(folder_id=folder_id).count())


@router.delete('/folders/{folder_id}')
def delete_folder(folder_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    folder = workspace.require_folder(db, folder_id, user)
    if db.query(DocumentDetails).filter_by(folder_id=folder_id).count() or db.query(DocumentFolder).filter_by(parent_folder_id=folder_id).count():
        raise HTTPException(409, 'This folder is not empty. Move or delete its documents before deleting the folder.')
    db.delete(folder)
    db.commit()
    return {'ok': True}


@router.post('/folders/{folder_id}/upload')
async def folder_upload(folder_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace.require_folder(db, folder_id, user)
    return await ingest_upload(file, db, user.role, folder_id)


@router.patch('/{document_id}')
def move_document(document_id: str, payload: MoveInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace.require_document(db, document_id, user)
    if payload.folder_id:
        workspace.require_folder(db, payload.folder_id, user)
    details = db.get(DocumentDetails, document_id)
    if details is None:
        details = DocumentDetails(document_id=document_id)
        db.add(details)
    details.folder_id = payload.folder_id
    db.commit()
    return {'ok': True}


@router.delete('/{document_id}')
def delete_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace.delete_document(db, workspace.require_document(db, document_id, user))
    return {'ok': True}
