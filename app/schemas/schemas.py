from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class RecipientInput(BaseModel):
    recipient_name: str = Field(..., min_length=1, max_length=255, description="Full name of recipient")
    recipient_email: EmailStr = Field(..., description="Valid email address of recipient")
    custom_message: Optional[str] = Field(None, max_length=500, description="Optional custom appreciation text")

    @field_validator("recipient_name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Recipient name cannot be blank or only whitespace.")
        return clean


class CertificateCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, description="Certificate title (e.g., Certificate of Completion)")
    issuer_name: str = Field(..., min_length=2, max_length=255, description="Issuing organization or instructor")
    issue_date: Optional[str] = Field(None, description="Date formatted string, defaults to current date if omitted")
    description: Optional[str] = Field(
        "for successfully participating and completing the program requirements.",
        max_length=500,
        description="General description or award clause"
    )
    recipients: List[RecipientInput] = Field(..., min_length=1, description="List of recipients to generate certificates for")


class CertificateResponse(BaseModel):
    id: str
    job_id: str
    recipient_name: str
    recipient_email: str
    custom_message: Optional[str]
    status: str
    error_message: Optional[str]
    download_url: Optional[str] = None
    created_at: str


class JobResponse(BaseModel):
    id: str
    title: str
    issuer_name: str
    issue_date: str
    description: Optional[str]
    status: str
    total_count: int
    success_count: int
    failure_count: int
    created_at: str
    updated_at: str


class JobDetailResponse(JobResponse):
    certificates: List[CertificateResponse]
    zip_download_url: Optional[str] = None
