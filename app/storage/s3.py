import boto3

from collections.abc import Generator 

from app.config import S3_REGION_NAME

def get_s3_client() -> Generator[boto3.client, None, None]:
    s3_client = boto3.client("s3", region_name=S3_REGION_NAME)
    yield s3_client
    s3_client.close()
