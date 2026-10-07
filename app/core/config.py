import os

class Settings:
    PROJECT_NAME: str = "Bulk Certificate Generator"
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "certificates.db")
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "generated_certificates")

settings = Settings()
