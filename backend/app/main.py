"""智能简历优化工具 - FastAPI 后端入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import UPLOAD_DIR
from .routers import admin, ai, auth, resumes

app = FastAPI(title="智能简历优化工具 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(resumes.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

app.mount("/files", StaticFiles(directory=str(UPLOAD_DIR)), name="files")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "resume-optimizer-api"}
