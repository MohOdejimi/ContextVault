import boto3
import logging

from fastapi import FastAPI, logger
from contextlib import asynccontextmanager
from botocore.exceptions import ClientError

from app.auth.routes import router as auth_router
from app.routes.documents import router as documents_router
from app.config import S3_BUCKET_NAME, S3_REGION_NAME

@asynccontextmanager
async def lifespan(app: FastAPI):
    s3_client = boto3.client("s3", region_name=S3_REGION_NAME)
    bucket_name = S3_BUCKET_NAME
    bucket_config = {}
    try:
        s3_client.create_bucket(Bucket = bucket_name, **bucket_config)
        print(f"Bucket '{bucket_name}' created successfully.")
    except ClientError as e:
        logging.error(e)
    app.state.s3_client = s3_client
    yield

app = FastAPI(title="Entreprise RAG System", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(documents_router)