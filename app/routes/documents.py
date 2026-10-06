import logging
import os
import uuid 
import boto3

from typing import Annotated
from io import BytesIO
from pathlib import Path
from fastapi import APIRouter, Depends,  HTTPException, status,  File, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from botocore.exceptions import ClientError

from app.models.documents import Document
from app.auth.routes import get_current_user
from app.database import get_db
from app.auth.models import User
from app.schema import Document_Response
from app.storage.s3 import get_s3_client
from app.config import S3_BUCKET_NAME, S3_REGION_NAME

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


@router.post('/document', response_model = Document_Response, status_code = status.HTTP_201_CREATED)
async def upload_document(
    db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)], s3_client: Annotated[boto3.client, Depends(get_s3_client)],file: UploadFile = File(...)):

    filename = file.filename
    
    content_type = file.content_type
    _, file_extension = os.path.splitext(filename)
    file_extension = file_extension.lower()
    unique_identifier = str(uuid.uuid4())
    bucket_name = S3_BUCKET_NAME

    
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

    file_size = 0
    buffer = BytesIO()
    key = stored_filename

    uploaded = False
    try: 
        while chunk := await file.read(chunk_size):
            file_size += len(chunk)
            if file_size > max_upload_bytes:
                raise HTTPException(
                    detail=f"File exceeds {max_upload_bytes // (1024  * 1024)} MB limit",
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE
                )
            buffer.write(chunk)
        if file_size == 0:
            raise HTTPException(
                detail="Empty file",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        buffer.seek(0)
        s3_client.upload_fileobj(
            buffer, 
            bucket_name, 
            key,
            ExtraArgs={"ContentType": content_type})
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
    except HTTPException:
        raise 
    except Exception as error:
        raise HTTPException(
            detail=f"Server Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) from error

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
        try:
            s3_client.head_object(Bucket=bucket_name, Key=key)
        except ClientError as error:
            code = error.response['Error']['Code']
            if code == '404':
                raise HTTPException(
                    detail="Client Error",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            else:
                logger.error(f"Error checking file '{key}' in S3 bucket '{bucket_name}': {error}")
                raise HTTPException(
                    detail="Server Error",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            try:
                s3_client.delete_object(Bucket=bucket_name, Key=key)
                logger.info(f"Deleted file '{key}' from S3 bucket '{bucket_name}'")
            except ClientError as error:
                logger.error(f"Failed to delete file '{key}' from S3 bucket '{bucket_name}': {error}")
                raise HTTPException(
                    detail="Server Error",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        raise HTTPException(
            detail="Server Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return doc_details

@router.get('/documents/{doc_id}', response_model = Document_Response, status_code = status.HTTP_200_OK)
def get_document(
    doc_id: int,
    db: Annotated[Session, Depends(get_db)], 
    current_user: Annotated[User, Depends(get_current_user)], 
    ):
    document = db.scalar(select(Document).where((Document.id == doc_id) & (current_user.id == Document.user_id)))
    if not document:
        raise HTTPException(
            detail="Unrecognised Document ID",
            status_code = status.HTTP_404_NOT_FOUND
        )

    return document

@router.get('/documents', response_model = list[Document_Response], status_code = status.HTTP_200_OK)
def get_user_documents(db: Annotated[Session, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]):
    stmt = select(Document).where(Document.user_id == current_user.id)
    documents = db.execute(stmt).scalars().all()

    return documents

def generate_presigned_url(s3_client, client_method, method_parameters, expires_in):
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod=client_method,
            Params=method_parameters,
            ExpiresIn = expires_in
        )
    except ClientError as error:
        raise

    return url

@router.get('/documents/download/{doc_id}', status_code = status.HTTP_200_OK)
def download_document(
    doc_id: int,
    db: Annotated[Session, Depends(get_db)], 
    current_user: Annotated[User, Depends(get_current_user)], 
    s3_client: Annotated[boto3.client, Depends(get_s3_client)]
    ):
    document = db.scalar(select(Document).where((Document.id == doc_id) & (Document.user_id == current_user.id)))
    if not document:
        raise HTTPException(
            detail="Document not found on server",
            status_code = status.HTTP_404_NOT_FOUND
        )
    
    try:
        s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=document.stored_filename)
    except ClientError as error:
        code = error.response['Error']['Code']
        if code == '404':
            raise HTTPException(
                detail=f"File '{document.stored_filename}' not found",
                status_code=status.HTTP_404_NOT_FOUND
            )

    url = generate_presigned_url(
        s3_client,
        "get_object",
        {"Bucket": S3_BUCKET_NAME, "Key": document.stored_filename},
        120
    )

    return {"url": url}

@router.delete("/documents/{doc_id}", status_code=status.HTTP_200_OK)
def delete_user_document(
    doc_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    s3_client: Annotated[boto3.client, Depends(get_s3_client)]
):

    document = db.scalar(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == current_user.id,
        )
    )

    if not document:
        raise HTTPException(
            detail="Document not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    document_key = document.stored_filename

    try:
        db.delete(document)
        db.commit()
    except Exception as error:
        db.rollback()
        logger.exception("Database error while deleting document")

        raise HTTPException(
            detail="Failed to delete document",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from error

    try:
        s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=document_key)
    except ClientError as e:
        code = e.response['Error']['Code']

        if code == 404:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail=f"File Document is not found"
            )
    else:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=document_key)


    return {
        "detail": "Document deleted successfully"
    }