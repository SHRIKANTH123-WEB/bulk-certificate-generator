import sqlite3
from contextlib import contextmanager
from app.core.config import settings


def get_db_connection(db_path: str = None) -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.
    row_factory = sqlite3.Row allows column access by name (like dict keys).
    """
    path = db_path or settings.DATABASE_PATH
    conn = sqlite3.connect(path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db_context(db_path: str = None):
    """
    Context manager for background tasks and tests.
    Automatically commits transactions and closes the connection.
    """
    conn = get_db_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    """
    FastAPI dependency that provides a database connection per request.
    """
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str = None):
    """
    Initializes the database schema using straightforward SQL CREATE TABLE statements.
    """
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. generation_jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generation_jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                issuer_name TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                total_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 2. certificates table with Foreign Key to generation_jobs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                recipient_name TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                custom_message TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                file_path TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES generation_jobs (id) ON DELETE CASCADE
            )
        """)
        conn.commit()
