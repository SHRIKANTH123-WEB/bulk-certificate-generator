"""
Integration and Unit Test Suite for Bulk Certificate Generator API (Pure SQL).
Tests cover:
1. Input validation (empty recipient list, invalid email, whitespace names)
2. Direct PDF certificate generation via CertificateRenderer
3. Creating generation job and tracking status via background processing
4. Failure isolation (single corrupted recipient doesn't stop the rest)
5. Downloading generated PDF certificate and bulk ZIP archive
"""

import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db, get_db, get_db_connection
from app.services.generator import CertificateRenderer
from app.services.job_processor import process_generation_job

TEST_DB_PATH = "test_certificates.db"


def override_get_db():
    conn = get_db_connection(TEST_DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    # Setup test database tables via SQL
    init_db(TEST_DB_PATH)
    yield
    # Cleanup test db file
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except PermissionError:
            pass


@pytest.fixture
def client():
    return TestClient(app)


# 1. Test Input Validation
def test_input_validation_empty_recipient_list(client):
    payload = {
        "title": "FastAPI Masterclass",
        "issuer_name": "Dev Academy",
        "recipients": []
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_input_validation_invalid_email(client):
    payload = {
        "title": "FastAPI Masterclass",
        "issuer_name": "Dev Academy",
        "recipients": [
            {"recipient_name": "Alice Smith", "recipient_email": "not-an-email"}
        ]
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_input_validation_blank_name(client):
    payload = {
        "title": "FastAPI Masterclass",
        "issuer_name": "Dev Academy",
        "recipients": [
            {"recipient_name": "   ", "recipient_email": "alice@example.com"}
        ]
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


# 2. Test Certificate Renderer
def test_certificate_pdf_rendering(tmp_path):
    output_pdf = str(tmp_path / "sample_cert.pdf")
    created_path = CertificateRenderer.generate_pdf(
        output_path=output_pdf,
        recipient_name="John Doe",
        certificate_title="Full Stack Bootcamp",
        issuer_name="Tech University",
        issue_date="October 07, 2026",
        description="For excellence in backend engineering.",
        custom_message="Outstanding performance in coursework.",
        certificate_id="cert-12345"
    )
    assert os.path.exists(created_path)
    assert os.path.getsize(created_path) > 1000


# 3. Test Creating Generation Job & Job Status Tracking
def test_create_and_process_job_success(client):
    payload = {
        "title": "Python Certification",
        "issuer_name": "Code Academy",
        "issue_date": "October 07, 2026",
        "description": "for successfully mastering Python and modern API development.",
        "recipients": [
            {"recipient_name": "Alice Johnson", "recipient_email": "alice@example.com"},
            {"recipient_name": "Bob Smith", "recipient_email": "bob@example.com", "custom_message": "Top 5% score"}
        ]
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202
    job_data = response.json()
    job_id = job_data["id"]
    assert job_data["total_count"] == 2
    assert job_data["status"] == "PENDING"

    # Execute processor synchronously for test
    process_generation_job(job_id, db_path=TEST_DB_PATH)

    # Verify status
    status_response = client.get(f"/api/v1/jobs/{job_id}")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["status"] == "COMPLETED"
    assert status_data["success_count"] == 2
    assert status_data["failure_count"] == 0
    assert len(status_data["certificates"]) == 2
    assert all(c["status"] == "SUCCESS" for c in status_data["certificates"])
    assert status_data["zip_download_url"] is not None


# 4. Test Single Certificate Failure Isolation
def test_failure_handling_isolation(client):
    payload = {
        "title": "Resilience Workshop",
        "issuer_name": "Safety First Institute",
        "recipients": [
            {"recipient_name": "Valid Recipient One", "recipient_email": "one@example.com"},
            {"recipient_name": "__FORCE_FAILURE__", "recipient_email": "fail@example.com"},
            {"recipient_name": "Valid Recipient Two", "recipient_email": "two@example.com"}
        ]
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202
    job_id = response.json()["id"]

    # Run processor
    process_generation_job(job_id, db_path=TEST_DB_PATH)

    # Check job status
    status_response = client.get(f"/api/v1/jobs/{job_id}")
    assert status_response.status_code == 200
    status_data = status_response.json()

    assert status_data["total_count"] == 3
    assert status_data["success_count"] == 2
    assert status_data["failure_count"] == 1

    # Check individual certificates
    certs = {c["recipient_name"]: c for c in status_data["certificates"]}
    assert certs["Valid Recipient One"]["status"] == "SUCCESS"
    assert certs["Valid Recipient Two"]["status"] == "SUCCESS"
    assert certs["__FORCE_FAILURE__"]["status"] == "FAILED"
    assert "Simulated certificate generation failure" in certs["__FORCE_FAILURE__"]["error_message"]


# 5. Test Certificate Download and ZIP Download
def test_download_certificate_and_zip(client):
    payload = {
        "title": "Cloud Architecture",
        "issuer_name": "Cloud Guild",
        "recipients": [
            {"recipient_name": "Charlie Brown", "recipient_email": "charlie@example.com"}
        ]
    }
    res = client.post("/api/v1/jobs", json=payload)
    job_id = res.json()["id"]
    process_generation_job(job_id, db_path=TEST_DB_PATH)

    status_data = client.get(f"/api/v1/jobs/{job_id}").json()
    cert_id = status_data["certificates"][0]["id"]

    # Download PDF
    pdf_res = client.get(f"/api/v1/certificates/{cert_id}/download")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert len(pdf_res.content) > 1000

    # Download ZIP
    zip_res = client.get(f"/api/v1/jobs/{job_id}/download-all")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"
    assert len(zip_res.content) > 100
