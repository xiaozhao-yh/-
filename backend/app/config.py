"""全局配置：从 backend/.env 读取，未设置时使用默认值。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
load_dotenv(BASE_DIR / ".env")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "000000")
DB_NAME = os.getenv("DB_NAME", "resume_optimizer")

SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

JWT_SECRET = os.getenv("JWT_SECRET", "resume-optimizer-jwt-secret-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
AVATAR_DIR = UPLOAD_DIR / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
MAX_AVATAR_SIZE = 5 * 1024 * 1024   # 5MB

ALLOWED_RESUME_EXTS = {"pdf", "docx", "txt", "html", "htm"}
ALLOWED_AVATAR_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
