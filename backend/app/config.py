import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "biotrack-dev-secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "biotrack-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://biotrack:biotrack_pass@127.0.0.1:3306/biotrack_db?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "isolation_level": "READ COMMITTED",
    }
    ESCALATION_TIMEOUT_SECONDS = int(os.getenv("ESCALATION_TIMEOUT_SECONDS", "600"))
    AUTH_PROVIDER = os.getenv("AUTH_PROVIDER", "local")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL",
        "mysql+pymysql://biotrack:biotrack_pass@127.0.0.1:3306/biotrack_test_db?charset=utf8mb4",
    )
    ESCALATION_TIMEOUT_SECONDS = 5
