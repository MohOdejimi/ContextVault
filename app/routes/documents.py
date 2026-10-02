import logging
import os
import uuid 

from typing import Annotated
from pathlib import Path
from fastapi import APIRouter, Depends,  HTTPException, status,  File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.documents import Document
from app.auth.routes import get_current_user
from app.database import get_db
from app.auth.models import User

router = APIRouter(tags=["File Upload"])
logger = logging.Logger(__name__)

supported_extensions = {".pdf", ".docx", ".txt", ".md"}
mime_validation_map = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    )
}
max_upload_bytes = int(os.getenv('MAX_UPLOAD_SIZE', '5')) * 1024 * 1024
chunk_size = 1024 * 1024

parent_dir = Path(__file__).resolve().parent 
uploads_dir = parent_dir / "upload"
uploads_dir.mkdir(exist_ok=True)

@router.post('/document', status_code = status.HTTP_201_CREATED)
async def upload_document(
    db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)], file: UploadFile = File(...)):

    filename = file.filename
    
    content_type = file.content_type
    _, file_extension = os.path.splitext(filename)
    file_extension = file_extension.lower()
    unique_identifier = str(uuid.uuid4())

    
    if file_extension not in supported_extensions:
        raise HTTPException (
            detail=f"Invalid file type '{file_extension}'. Allowed '{', '.join(supported_extensions)}'",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    if mime_validation_map[file_extension] != content_type:
        raise HTTPException(
            detail="Failed MIME validation check",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        )

    stored_filename = unique_identifier + file_extension 
    dest = Path(uploads_dir / stored_filename)

    file_size = 0

    uploaded = False
    try: 
        with open(dest, 'wb') as out:
            while chunk := await file.read(chunk_size):
                file_size += len(chunk)
                if file_size > max_upload_bytes:
                    raise HTTPException(
                        detail=f"File exceeds {max_upload_bytes // (1024  * 1024)} MB limit",
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE
                    )
                out.write(chunk)
        if file_size == 0:
            raise HTTPException(
                detail="Empty file",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        uploaded = True
    except PermissionError as error:
        raise HTTPException(
            detail="File storage failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except OSError as error:
        raise HTTPException(
            detail = "File storage failed",
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as error:
        raise HTTPException(
            detail=f"Server Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) from error
    except HTTPException:
        raise 
    finally:
        if not uploaded and dest.exists():
            dest.unlink()

    try:
        doc_details =  Document(
            original_filename = filename,
            user_id = current_user.id,
            stored_filename = stored_filename,
            content_type = content_type,
            size_in_bytes =  file_size, 
        )
        db.add(doc_details)
        db.commit()
        db.refresh(doc_details)
    except Exception as error:
        db.rollback()
        logger.exception("Unexpected error during file upload")
        raise HTTPException(
            detail="Server Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return {
        "filename": filename,
        "content_type": content_type
    }