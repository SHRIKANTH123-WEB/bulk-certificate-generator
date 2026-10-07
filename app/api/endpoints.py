import os
import zipfile
import uuid
import sqlite3
from datetime import date, datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Request
from fastapi.responses import FileResponse

from app.core.database import get_db
from app.models.models import JobStatus, CertificateStatus
from app.schemas.schemas import (
    CertificateCreateRequest,
    JobResponse,
    JobDetailResponse,
    CertificateResponse,
)
from app.services.job_processor import process_generation_job

router = APIRouter(prefix="/api/v1", tags=["Certificates"])


def utc_now_str():
    return datetime.now(timezone.utc).isoformat()


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a bulk certificate generation request"
)
def create_generation_job(
    payload: CertificateCreateRequest,
    background_tasks: BackgroundTasks,
    conn: sqlite3.Connection = Depends(get_db)
):
    job_id = str(uuid.uuid4())
    issue_date = payload.issue_date or date.today().strftime("%B %d, %Y")
    now_str = utc_now_str()

    cursor = conn.cursor()

    # 1. Insert generation job
    cursor.execute("""
        INSERT INTO generation_jobs (
            id, title, description, issuer_name, issue_date, status,
            total_count, success_count, failure_count, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id, payload.title, payload.description, payload.issuer_name, issue_date,
        JobStatus.PENDING, len(payload.recipients), 0, 0, now_str, now_str
    ))

    # 2. Insert each recipient certificate record
    for rec in payload.recipients:
        cert_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO certificates (
                id, job_id, recipient_name, recipient_email, custom_message,
                status, file_path, error_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
        """, (
            cert_id, job_id, rec.recipient_name, str(rec.recipient_email),
            rec.custom_message, CertificateStatus.PENDING, now_str, now_str
        ))

    conn.commit()

    # Fetch inserted job to return
    cursor.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,))
    job_row = cursor.fetchone()

    # Queue async processing
    background_tasks.add_task(process_generation_job, job_id)

    return dict(job_row)


@router.get(
    "/jobs",
    response_model=List[JobResponse],
    summary="List all certificate generation jobs"
)
def list_jobs(conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM generation_jobs ORDER BY created_at DESC")
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


@router.get(
    "/jobs/{job_id}",
    response_model=JobDetailResponse,
    summary="Retrieve status, progress, and certificates for a job"
)
def get_job_status(job_id: str, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    cursor.execute("SELECT * FROM certificates WHERE job_id = ? ORDER BY created_at ASC", (job_id,))
    certs = cursor.fetchall()

    base_url = str(request.base_url).rstrip("/")
    cert_responses = []
    for c in certs:
        download_url = None
        if c["status"] == CertificateStatus.SUCCESS and c["file_path"]:
            download_url = f"{base_url}/api/v1/certificates/{c['id']}/download"

        cert_responses.append(CertificateResponse(
            id=c["id"],
            job_id=c["job_id"],
            recipient_name=c["recipient_name"],
            recipient_email=c["recipient_email"],
            custom_message=c["custom_message"],
            status=c["status"],
            error_message=c["error_message"],
            download_url=download_url,
            created_at=c["created_at"]
        ))

    zip_url = None
    if job["success_count"] > 0:
        zip_url = f"{base_url}/api/v1/jobs/{job_id}/download-all"

    job_dict = dict(job)
    job_dict["certificates"] = cert_responses
    job_dict["zip_download_url"] = zip_url

    return job_dict


@router.get(
    "/certificates/{cert_id}/download",
    summary="Download an individual generated certificate PDF"
)
def download_certificate(cert_id: str, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM certificates WHERE id = ?", (cert_id,))
    cert = cursor.fetchone()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if cert["status"] != CertificateStatus.SUCCESS or not cert["file_path"] or not os.path.exists(cert["file_path"]):
        raise HTTPException(
            status_code=400,
            detail=f"Certificate file is not available. Status: {cert['status']}. Error: {cert['error_message']}"
        )

    clean_name = "".join(c if c.isalnum() else "_" for c in cert["recipient_name"])
    download_filename = f"Certificate_{clean_name}.pdf"

    return FileResponse(
        path=cert["file_path"],
        media_type="application/pdf",
        filename=download_filename
    )


@router.get(
    "/jobs/{job_id}/download-all",
    summary="Download all successfully generated certificates in a ZIP archive"
)
def download_job_zip(job_id: str, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    cursor.execute("SELECT * FROM certificates WHERE job_id = ? AND status = ?", (job_id, CertificateStatus.SUCCESS))
    successful_certs = cursor.fetchall()

    valid_certs = [c for c in successful_certs if c["file_path"] and os.path.exists(c["file_path"])]

    if not valid_certs:
        raise HTTPException(
            status_code=400,
            detail="No completed certificates found for this job to bundle into ZIP."
        )

    from app.core.config import settings
    job_dir = os.path.join(settings.STORAGE_DIR, job_id)
    zip_path = os.path.join(job_dir, f"certificates_job_{job_id}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for cert in valid_certs:
            clean_name = "".join(c if c.isalnum() else "_" for c in cert["recipient_name"])
            arcname = f"{clean_name}_{cert['id'][:8]}.pdf"
            zip_file.write(cert["file_path"], arcname=arcname)

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"certificates_job_{job_id[:8]}.zip"
    )
