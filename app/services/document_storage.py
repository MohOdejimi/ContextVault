import boto3

from botocore.exceptions import ClientError

from app.storage.s3 import get_s3_client
from app.config import S3_BUCKET_NAME

class ObjectNotFound(Exception):
    pass

def get_raw_file_bytes(
        object_key: str,
        client = None
):
    client = client or get_s3_client()
    try:
        response = client.get_object(Bucket=S3_BUCKET_NAME, Key=object_key)
        with response["Body"] as body:
            data = body.read()
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("NoSuchKey", "404", "NotFound"):
            raise ObjectNotFound(f"object not found: {object_key}") from e
        raise

    expected = response["ContentLength"]
    if len(data) != expected:
        raise IOError(f"truncated download for {object_key}: got {len(data)} of {expected} bytes")
    return data