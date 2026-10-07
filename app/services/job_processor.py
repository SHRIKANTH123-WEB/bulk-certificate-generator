import os
import logging
from datetime import datetime, timezone
from app.core.database import get_db_context
from app.core.config import settings
from app.models.models import JobStatus, CertificateStatus
from app.services.generator import CertificateRenderer

logger = logging.getLogger(__name__)


def utc_now_str():
    return datetime.now(timezone.utc).isoformat()


def process_generation_job(job_id: str, db_path: str = None):
    """
    Background worker that fetches pending certificates, renders the PDFs,
    and updates statuses using pure SQL queries with robust failure isolation.
    """
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()

        # 1. Fetch the job details
        cursor.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,))
        job = cursor.fetchone()
        if not job:
            logger.error(f"Job with id {job_id} not found.")
            return

        # 2. Mark job as PROCESSING
        cursor.execute(
            "UPDATE generation_jobs SET status = ?, updated_at = ? WHERE id = ?",
            (JobStatus.PROCESSING, utc_now_str(), job_id)
        )
        conn.commit()

        # 3. Fetch all certificates belonging to this job
        cursor.execute("SELECT * FROM certificates WHERE job_id = ?", (job_id,))
        certificates = cursor.fetchall()

        success_count = 0
        failure_count = 0

        job_dir = os.path.join(settings.STORAGE_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)

        for cert in certificates:
            cert_id = cert["id"]
            recipient_name = cert["recipient_name"]
            custom_message = cert["custom_message"]

            try:
                # Test edge-case trigger
                if recipient_name == "__FORCE_FAILURE__":
                    raise RuntimeError("Simulated certificate generation failure for test verification.")

                safe_name = "".join(c if c.isalnum() else "_" for c in recipient_name)
                filename = f"{cert_id}_{safe_name}.pdf"
                output_path = os.path.join(job_dir, filename)

                # Render PDF using ReportLab
                CertificateRenderer.generate_pdf(
                    output_path=output_path,
                    recipient_name=recipient_name,
                    certificate_title=job["title"],
                    issuer_name=job["issuer_name"],
                    issue_date=job["issue_date"],
                    description=job["description"] or "",
                    custom_message=custom_message or "",
                    certificate_id=cert_id
                )

                # Update certificate to SUCCESS
                cursor.execute("""
                    UPDATE certificates
                    SET status = ?, file_path = ?, error_message = NULL, updated_at = ?
                    WHERE id = ?
                """, (CertificateStatus.SUCCESS, output_path, utc_now_str(), cert_id))
                success_count += 1

            except Exception as e:
                logger.exception(f"Error generating certificate for {recipient_name} ({cert_id}): {e}")
                cursor.execute("""
                    UPDATE certificates
                    SET status = ?, error_message = ?, updated_at = ?
                    WHERE id = ?
                """, (CertificateStatus.FAILED, str(e), utc_now_str(), cert_id))
                failure_count += 1

            conn.commit()

        # 4. Finalize Job status and counts
        final_status = JobStatus.COMPLETED
        if failure_count > 0 and success_count == 0:
            final_status = JobStatus.FAILED

        cursor.execute("""
            UPDATE generation_jobs
            SET status = ?, success_count = ?, failure_count = ?, updated_at = ?
            WHERE id = ?
        """, (final_status, success_count, failure_count, utc_now_str(), job_id))
        conn.commit()
