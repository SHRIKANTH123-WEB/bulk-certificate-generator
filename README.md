# Bulk Certificate Generator API

An asynchronous RESTful backend service built with **FastAPI**, **SQLite**, and **ReportLab** designed to handle bulk certificate generation workflows for courses, conferences, and institutional events.

---

## 📋 Table of Contents
- [Project Overview](#project-overview)
- [Architecture & Design Decisions](#architecture--design-decisions)
- [Project Structure](#project-structure)
- [How to Set Up the Project](#how-to-set-up-the-project)
- [How to Run the Application](#how-to-run-the-application)
- [How to Run Tests](#how-to-run-tests)
- [How to Submit a Certificate Generation Request](#how-to-submit-a-certificate-generation-request)
- [How to Retrieve Generated Certificates](#how-to-retrieve-generated-certificates)
- [API Documentation](#api-documentation)

---

## 🎯 Project Overview

Organizations often need to generate personalized certificates for hundreds or thousands of participants after an event or bootcamp. Generating these certificates synchronously locks up HTTP request worker threads and causes client timeouts. 

This project solves this problem by providing:
1. **Bulk Request Submission**: Accept complete lists of recipients in a single API call.
2. **Asynchronous Background Processing**: Offloads PDF generation to background worker tasks and provides immediate `HTTP 202 Accepted` tracking tickets.
3. **Graceful Fault Isolation**: A corrupt recipient entry does not stop or fail the rest of the batch.
4. **Pure SQL Relational Database**: Uses standard SQL tables with foreign key constraints to track batches, counts, and individual certificate statuses.
5. **Flexible Retrieval**: Allows downloading single certificates as PDFs or downloading all generated certificates in a single aggregated `.zip` archive.

---

## 💡 Important Implementation & Design Decisions

### 1. Framework: FastAPI
- **Reasoning**: FastAPI offers native asynchronous support, type-safe data parsing via Pydantic, high performance, and automatic interactive OpenAPI/Swagger documentation at `/docs`.

### 2. Processing Strategy: Asynchronous Background Tasks
- **Reasoning**: Vector PDF compilation takes ~30–100ms per certificate. Generating 100+ certificates in a single synchronous HTTP call would block server threads and risk client-side network timeouts.
- **Workflow**:
  - The API validates the payload and writes initial `PENDING` records to the database.
  - Returns `HTTP 202 Accepted` with a tracking `id` within milliseconds.
  - FastAPI's `BackgroundTasks` executes the rendering sequentially in an isolated thread.
  - The client polls `GET /api/v1/jobs/{job_id}` to inspect real-time progress.

### 3. Failure Handling & Error Isolation
- **Reasoning**: In large batch uploads, malformed recipient data or rare rendering edge cases should not invalidate the entire job.
- **Implementation**: Each recipient rendering is wrapped in an individual `try...except` block. If an error occurs, that recipient's record is updated to `status = 'FAILED'` with the exact error saved to `error_message`. The loop then immediately proceeds to the next recipient.
- The parent job aggregates `total_count`, `success_count`, and `failure_count`.

### 4. Database: Pure SQL with SQLite
- **Reasoning**: Python's standard library `sqlite3` driver was chosen with direct SQL statements (`CREATE TABLE`, `INSERT`, `SELECT`, `UPDATE`). This avoids complex ORM layers and makes the database interactions transparent, readable, and easy to explain.
- **Data Model**:
  - `generation_jobs`: Tracks batch ID, event title, issuer, issue date, status (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`), and metrics.
  - `certificates`: Relational child table linked by foreign key (`job_id`) storing recipient details, file path, status, and error logs.

### 5. PDF Generation: Vector ReportLab Canvas
- **Reasoning**: ReportLab compiles resolution-independent vector graphics (US Letter Landscape, 792 x 612 pt). It generates dual navy/gold ornamental borders, verified seals, dynamic recipient names, issue dates, and signature lines without requiring external font or image file dependencies.

---

## 📁 Project Structure

```text
bulk-cert-generator/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints.py        # REST API endpoints (Jobs & Downloads)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration paths and settings
│   │   └── database.py         # SQLite connection setup & SQL table schemas
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py           # Status constants
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic validation schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── generator.py        # ReportLab vector certificate renderer
│   │   └── job_processor.py    # Background worker with fault isolation
│   ├── __init__.py
│   └── main.py                 # Application root & startup lifespan
├── tests/
│   ├── __init__.py
│   └── test_bulk_generator.py  # Comprehensive Pytest test suite
├── .gitignore                  # Git ignore rules
├── requirements.txt            # Project dependencies
└── README.md                   # Project documentation
```

---

## ⚙️ How to Set Up the Project

### Prerequisites
- Python 3.10+ installed

### Step 1: Clone the Repository
```bash
git clone https://github.com/SHRIKANTH123-WEB/bulk-certificate-generator.git
cd bulk-certificate-generator
```

### Step 2: Create and Activate a Virtual Environment (Optional but Recommended)
**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🚀 How to Run the Application

Start the Uvicorn ASGI server:
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running:
- **Interactive Swagger UI**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) in your browser.
- **Root URL**: Navigating to [http://127.0.0.1:8000/](http://127.0.0.1:8000/) will automatically redirect to `/docs`.
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 🧪 How to Run Tests

The test suite covers input validation, PDF canvas generation, asynchronous job processing, fault isolation, and certificate downloads.

To execute all tests with detailed verbosity:
```bash
python -m pytest tests -v
```

All 7 test cases will execute and verify the system end-to-end:
```text
tests/test_bulk_generator.py::test_input_validation_empty_recipient_list PASSED
tests/test_bulk_generator.py::test_input_validation_invalid_email PASSED
tests/test_bulk_generator.py::test_input_validation_blank_name PASSED
tests/test_bulk_generator.py::test_certificate_pdf_rendering PASSED
tests/test_bulk_generator.py::test_create_and_process_job_success PASSED
tests/test_bulk_generator.py::test_failure_handling_isolation PASSED
tests/test_bulk_generator.py::test_download_certificate_and_zip PASSED
```

---

## 📤 How to Submit a Certificate Generation Request

Send a `POST` request to `/api/v1/jobs` with the event details and the list of recipients:

### Endpoint
`POST http://127.0.0.1:8000/api/v1/jobs`

### Request Body (JSON)
```json
{
  "title": "Backend Engineering Masterclass",
  "issuer_name": "Dev Academy",
  "issue_date": "October 07, 2026",
  "description": "for successfully mastering API architecture, databases, and microservices.",
  "recipients": [
    {
      "recipient_name": "Alice Johnson",
      "recipient_email": "alice@example.com",
      "custom_message": "Top performer in practical assessment"
    },
    {
      "recipient_name": "Bob Smith",
      "recipient_email": "bob@example.com"
    }
  ]
}
```

### Response (`HTTP 202 Accepted`)
```json
{
  "id": "e2c74d6b-1934-4bc6-8d6f-703487c67420",
  "title": "Backend Engineering Masterclass",
  "issuer_name": "Dev Academy",
  "issue_date": "October 07, 2026",
  "description": "for successfully mastering API architecture, databases, and microservices.",
  "status": "PENDING",
  "total_count": 2,
  "success_count": 0,
  "failure_count": 0,
  "created_at": "2026-10-07T15:10:00+00:00",
  "updated_at": "2026-10-07T15:10:00+00:00"
}
```

---

## 📥 How to Retrieve Generated Certificates

### Step 1: Check Job Status & Progress
Make a `GET` request using the `id` returned from the submission step:

`GET http://127.0.0.1:8000/api/v1/jobs/e2c74d6b-1934-4bc6-8d6f-703487c67420`

**Response (`HTTP 200 OK`):**
```json
{
  "id": "e2c74d6b-1934-4bc6-8d6f-703487c67420",
  "title": "Backend Engineering Masterclass",
  "issuer_name": "Dev Academy",
  "issue_date": "October 07, 2026",
  "description": "for successfully mastering API architecture, databases, and microservices.",
  "status": "COMPLETED",
  "total_count": 2,
  "success_count": 2,
  "failure_count": 0,
  "zip_download_url": "http://127.0.0.1:8000/api/v1/jobs/e2c74d6b-1934-4bc6-8d6f-703487c67420/download-all",
  "certificates": [
    {
      "id": "f5e921d7-2f31-419b-89da-5a468d6d6ce1",
      "job_id": "e2c74d6b-1934-4bc6-8d6f-703487c67420",
      "recipient_name": "Alice Johnson",
      "recipient_email": "alice@example.com",
      "custom_message": "Top performer in practical assessment",
      "status": "SUCCESS",
      "error_message": null,
      "download_url": "http://127.0.0.1:8000/api/v1/certificates/f5e921d7-2f31-419b-89da-5a468d6d6ce1/download",
      "created_at": "2026-10-07T15:10:00+00:00"
    }
  ]
}
```

### Step 2: Download Certificates

- **Download an Individual Certificate (PDF)**:
  `GET /api/v1/certificates/{cert_id}/download`  
  Returns the certificate as a vector PDF (`application/pdf`).

- **Download All Certificates in Bulk (ZIP)**:
  `GET /api/v1/jobs/{job_id}/download-all`  
  Returns a compressed ZIP archive (`application/zip`) containing all successfully generated PDF certificates for the job.
