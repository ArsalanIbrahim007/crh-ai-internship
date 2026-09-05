"""Workspace organization, independent of extraction and RAG behavior."""
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.models import Document, DocumentChunk, DocumentDetails, DocumentFolder, User


def visible(document: Document, user: User) -> bool:
    return user.role in {role.strip() for role in document.allowed_roles.split(',')}


def require_folder(db: Session, folder_id: str, user: User) -> DocumentFolder:
    folder = db.get(DocumentFolder, folder_id)
    if folder is None or folder.owner_id != user.id:
        raise HTTPException(404, 'Folder not found')
    return folder


def require_document(db: Session, document_id: str, user: User) -> Document:
    document = db.get(Document, document_id)
    if document is None or not visible(document, user):
        raise HTTPException(404, 'Document not found')
    details = db.get(DocumentDetails, document_id)
    if details and details.folder_id:
        require_folder(db, details.folder_id, user)
    return document


def list_documents(db: Session, user: User) -> list[dict]:
    owned = {folder.id for folder in db.query(DocumentFolder).filter_by(owner_id=user.id)}
    details = {item.document_id: item for item in db.query(DocumentDetails)}
    result = []
    for document in db.query(Document).order_by(Document.created_at.desc()):
        meta = details.get(document.id)
        if not visible(document, user) or (meta and meta.folder_id and meta.folder_id not in owned):
            continue
        result.append({'id': document.id, 'filename': document.filename,
                       'mime_type': document.mime_type, 'folder_id': meta.folder_id if meta else None,
                       'size': meta.size if meta else None, 'created_at': document.created_at.isoformat(),
                       'updated_at': (meta.updated_at if meta else document.created_at).isoformat()})
    return result


def folder_json(folder: DocumentFolder, count: int) -> dict:
    return {'folder_id': folder.id, 'name': folder.name, 'parent_folder_id': folder.parent_folder_id,
            'created_at': folder.created_at.isoformat(), 'updated_at': folder.updated_at.isoformat(),
            'document_count': count}


def create_folder(db: Session, user: User, name: str) -> DocumentFolder:
    if db.query(DocumentFolder).filter_by(owner_id=user.id, name=name).first():
        raise HTTPException(409, 'A folder with that name already exists')
    folder = DocumentFolder(id=f'folder_{uuid4().hex}', name=name, owner_id=user.id)
    db.add(folder)
    db.commit()
    return folder


def delete_document(db: Session, document: Document) -> None:
    # Never allow a stored filename to escape the configured upload directory.
    root = Path(get_settings().upload_root).resolve()
    path = (root / f'{document.id}_{Path(document.filename).name}').resolve()
    if path.parent != root:
        raise HTTPException(400, 'Invalid document path')
    if path.is_file():
        path.unlink()
    db.query(DocumentChunk).filter_by(document_id=document.id).delete()
    db.query(DocumentDetails).filter_by(document_id=document.id).delete()
    db.delete(document)
    db.commit()
