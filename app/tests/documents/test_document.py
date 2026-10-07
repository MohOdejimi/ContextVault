from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient



uploads_dir = Path(__file__).resolve().parents[2] / "upload"

test_pdf_file = Path(uploads_dir) / "test.pdf"
test_doc_file = Path(uploads_dir) / "test.docx"
test_txt_file = Path(uploads_dir) / "test.txt"
test_md_file = Path(uploads_dir) / "test.md"
test_yml_file = Path(uploads_dir) / "test.yaml"


def user_registration_helper(client: TestClient):
    email = "TEST@SAMPLE.COM"
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


def test_get_pdf_file_by_id(client: TestClient):
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

def test_get_doc_file_by_id(client: TestClient):
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

    get_doc_response = client.get(
        f"/documents/{id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert get_doc_response.status_code == status.HTTP_200_OK

def test_get_txt_file_by_id(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_txt_file, "rb") as f:
        response = client.post('/document', 
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (test_txt_file.name, f, "text/plain")
            }
        )

    id = response.json()["id"]

    get_txt_response = client.get(
        f"/documents/{id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert get_txt_response.status_code == status.HTTP_200_OK

def test_get_documents(client: TestClient):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_doc_file, "rb") as f:
        response = client.post('/document', 
            headers={"Authorization": f"Bearer {token}"},
            files={
                "file": (test_doc_file.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            }
        )

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