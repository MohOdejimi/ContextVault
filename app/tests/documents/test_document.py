import os
import boto3

from pathlib import Path

from fastapi import status, HTTPException
from fastapi.testclient import TestClient
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

uploads_dir = Path(__file__).resolve().parents[2] / "upload"

test_pdf_file = Path(uploads_dir) / "test.pdf"
test_doc_file = Path(uploads_dir) / "test.docx"
test_txt_file = Path(uploads_dir) / "test.txt"
test_md_file = Path(uploads_dir) / "test.md"
test_yml_file = Path(uploads_dir) / "test.yaml"
empty_file = Path(uploads_dir) / "empty.txt"
large_file = Path(uploads_dir) / "large.pdf"

bucket = os.getenv("S3_BUCKET_NAME")

def user_registration_helper(client: TestClient, email: str = "TEST@SAMPLE.COM"):
    password = "Securepass2"

    response = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == status.HTTP_201_CREATED
    return email, password

def user_login_helper(client: TestClient, email: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()["access_token"]

def object_exists_helper(s3_client, bucket_name, key):
    try:
        s3_client.head_object(Bucket=bucket_name, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == 404:
            return False
        raise 

def get_doc_key_helper(mock_s3_client, bucket):
    objects = mock_s3_client.list_objects_v2(Bucket=bucket)

    assert "Contents" in objects, "nothing was uploaded"
    assert len(objects["Contents"]) == 1

    doc_key = objects["Contents"][0]["Key"]

    return doc_key

def get_user_id(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, "rb") as f:
        response = client.post('/document',
            headers = {
                "Authorization": f"Bearer {token}"
            },
            files = {
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED
    id = response.json()["id"]

    return id 

def test_safe_pdf_upload(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, "rb") as f:
        response = client.post('/document', 
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED

def test_safe_md_download(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_md_file, "rb") as f:
        response = client.post('/document', 
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (test_md_file.name, f, "text/markdown")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED

def test_safe_txt_upload(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_txt_file, "rb") as f:
        response = client.post(
            "/document",
            headers={"Authorization": f"Bearer {token}"},
            files = {
                "file": (test_txt_file.name, f, "text/plain")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED  

def test_safe_docx_upload(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_doc_file, "rb") as f:
        response = client.post("/document",
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (test_doc_file.name, f,  (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ))
            }
        )

    assert response.status_code == status.HTTP_201_CREATED

def test_unsupported_extension(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_yml_file, "rb") as f:
        response = client.post('/document',
            headers={"Authorization": f"Bearer {token}"},
            files = {
                "file": (test_yml_file.name, f, "application/yaml")
            }
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_mime_mismatch(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, "rb") as f:
        response = client.post('/document', 
            headers = {"Authorization": f"Bearer {token}"},
            files = {
                "file": (test_pdf_file.name, f, "text/plain")
            }
        )

    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

def test_empty_file(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(empty_file, "rb") as f:
        response = client.post('/document',
            headers = {"Authorization": f"Bearer {token}"},
            files = {
                "file": (empty_file.name, f, "text/plain")
            }
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_file_larger_than_limit(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(large_file, "rb") as f:
        response = client.post('/document', 
            headers = {"Authorization": f"Bearer {token}"},
            files = {
                "file": (large_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE

def test_upload_without_authentication(client: TestClient):
    with open(test_pdf_file, "rb") as f:
        response = client.post('/document',
            files = {
                "file": (test_pdf_file.name, f, "applicaion/pdf")
            }
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_uploaded_object_exist_in_moto_s3(client: TestClient, mock_s3_client: boto3.client):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, "rb") as f:
        response = client.post('/document',
            headers = {
                "Authorization": f"Bearer {token}"
            },
            files = {
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED

    doc_key = get_doc_key_helper(mock_s3_client, bucket)
    assert object_exists_helper(mock_s3_client, bucket, doc_key) is True

def test_object_bytes_match_uploaded_bytes(client: TestClient, mock_s3_client: boto3.client):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_txt_file, "rb") as f:
        response = client.post('/document',
            headers = {
                "Authorization": f"Bearer {token}"
            },
            files = {
                "file": (test_txt_file.name, f, "text/plain")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED

    doc_key = get_doc_key_helper(mock_s3_client, bucket)

    object_details = mock_s3_client.get_object(Bucket=bucket, Key=doc_key)
    file_bytes = object_details["Body"].read()

    assert file_bytes == test_txt_file.read_bytes()

def test_S3_upload_failure(client: TestClient, mock_s3_client: boto3.client):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    mock_s3_client.delete_bucket(Bucket=bucket)

    with open(test_txt_file, "rb") as f:
        response = client.post('/document',
            headers = {
                "Authorization": f"Bearer {token}"
            },
            files = {
                "file": (test_txt_file.name, f, "text/plain")
            }
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

def test_get_file_by_id(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, "rb") as f:
        response = client.post('/document', 
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    id = response.json()["id"]

    get_pdf_response = client.get(
        f"/documents/{id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert get_pdf_response.status_code == status.HTTP_200_OK

def test_get_file_by_unknown_id(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, "rb") as f:
        response = client.post('/document', 
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED

    get_pdf_response = client.get(
        f"/documents/{0}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert get_pdf_response.status_code == status.HTTP_404_NOT_FOUND

def test_get_another_user_document(client: TestClient):
    user1_id = get_user_id(client)

    user2_email = "new@email.com"
    _, user2_password = user_registration_helper(client, user2_email)

    user2_token = user_login_helper(client, user2_email, user2_password)

    with open(test_txt_file, "rb") as f:
        user2_response = client.post('/document',
            headers = {
                "Authorization": f"Bearer {user2_token}"
            },
            files = {
                "file": (test_txt_file.name, f, "text/plain")
            }
        )

    assert user2_response.status_code == status.HTTP_201_CREATED

    get_doc_response = client.get(f'/documents/{user1_id}',
        headers={
            "Authorization": f"Bearer {user2_token}",
        }
    )

    assert get_doc_response.status_code == status.HTTP_404_NOT_FOUND

def test_get_documents(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    get_docs_response = client.get(
        f"/documents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert get_docs_response.status_code == status.HTTP_200_OK

def test_delete_user_document(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_doc_file, "rb") as f:
        response = client.post('/document',
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (test_doc_file.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            }
        )

    id = response.json()["id"]

    delete_doc_response = client.delete(f'/documents/{id}', headers={"Authorization": f"Bearer {token}"})

    assert delete_doc_response.status_code == status.HTTP_200_OK

def test_delete_unknown_document(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    id = -1

    delete_doc_response = client.delete(f'/documents/{id}', headers={"Authorization": f"Bearer {token}"})

    assert delete_doc_response.status_code == status.HTTP_404_NOT_FOUND

def test_delete_another_user_document(client: TestClient):
    user1_id = get_user_id(client)

    user2_email = "new@email.com"
    _, user2_password = user_registration_helper(client, user2_email)

    user2_token = user_login_helper(client, user2_email, user2_password)

    with open(test_txt_file, "rb") as f:
        user2_response = client.post('/document',
            headers = {
                "Authorization": f"Bearer {user2_token}"
            },
            files = {
                "file": (test_txt_file.name, f, "text/plain")
            }
        )

    assert user2_response.status_code == status.HTTP_201_CREATED

    get_doc_response = client.delete(f'/documents/{user1_id}',
        headers={
            "Authorization": f"Bearer {user2_token}",
        }
    )

    assert get_doc_response.status_code == status.HTTP_404_NOT_FOUND

def test_download_user_document(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_md_file, "rb") as f:
        response = client.post('/document',
            headers = {
                "Authorization": f"Bearer {token}"
            },
            files = {
                "file": (test_md_file.name, f, "text/markdown")
            }
        )

    id = response.json()["id"]

    download_response = client.get(f'/documents/download/{id}', 
        headers = {
            "Authorization": f"Bearer {token}"
        }
    )

    assert download_response.status_code == status.HTTP_200_OK

def test_download_nonexistent_document(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    id = -1

    download_response = client.get(f'/documents/download/{id}', 
        headers = {
            "Authorization": f"Bearer {token}"
        }
    )

    assert download_response.status_code == status.HTTP_404_NOT_FOUND

def test_download_another_user_document(client: TestClient):
    user1_id = get_user_id(client)

    user2_email = "new@email.com"
    _, user2_password = user_registration_helper(client, user2_email)

    user2_token = user_login_helper(client, user2_email, user2_password)

    with open(test_txt_file, "rb") as f:
        user2_response = client.post('/document',
            headers = {
                "Authorization": f"Bearer {user2_token}"
            },
            files = {
                "file": (test_txt_file.name, f, "text/plain")
            }
        )

    assert user2_response.status_code == status.HTTP_201_CREATED

    download_response = client.get(f'/documents/download/{user1_id}', 
        headers = {
            "Authorization": f"Bearer {user2_token}"
        }
    )

    assert download_response.status_code == status.HTTP_404_NOT_FOUND

def test_db_failure_after_s3_upload_removes_object(
    client: TestClient,
    mock_s3_client: boto3.client,
    monkeypatch,
):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    def fail_commit(_session: Session) -> None:
        raise HTTPException("Simulated DB failure")

    with monkeypatch.context() as request_patch:
        request_patch.setattr(Session, "commit", fail_commit)

        with open(test_pdf_file, "rb") as f:
            response = client.post(
                "/document",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (test_pdf_file.name, f, "application/pdf")},
            )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert mock_s3_client.list_objects_v2(Bucket=bucket).get("Contents", []) == []

def test_s3_cleanup_failure_after_committed_delete(
    client: TestClient,
    mock_s3_client: boto3.client,
    monkeypatch,
    caplog,
):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, "rb") as f:
        response = client.post('/document',
            headers = {
                "Authorization": f"Bearer {token}"
            },
            files = {
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    id = response.json()["id"]

    def fail_cleanup(**_kwargs) -> None:
        raise ClientError(
            {"Error": {"Code": "InternalError", "Message": "Failed cleanup operation"}},
            "DeleteObject",
        )

    with monkeypatch.context() as request_patch:
        request_patch.setattr(mock_s3_client, "delete_object", fail_cleanup)

        response = client.delete(
            f"/documents/{id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert "Failed to delete document from S3" in caplog.text