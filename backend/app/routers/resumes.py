"""简历管理：列表、创建（粘贴/上传解析）、编辑、删除、Word 下载"""
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import ALLOWED_RESUME_EXTS, MAX_UPLOAD_SIZE
from ..deps import get_current_user, get_db
from ..models import Resume, User
from ..schemas import Page, ResumeCreate, ResumeOut, ResumeUpdate
from ..services.exporter import export_resume_docx
from ..services.parser import normalize_text, parse_resume_file

router = APIRouter(prefix="/resumes", tags=["resumes"])


def get_own_resume(resume_id: int, user: User, db: Session) -> Resume:
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != user.id:
        raise HTTPException(status_code=404, detail="简历不存在")
    return resume


def _page_data(query, page: int, page_size: int, serializer) -> dict:
    total = query.count()
    items = query.order_by(Resume.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [serializer(i) for i in items]}


@router.get("")
def list_resumes(
    page: int = 1,
    page_size: int = 10,
    keyword: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Resume).filter(Resume.user_id == user.id)
    if keyword.strip():
        kw = f"%{keyword.strip()}%"
        q = q.filter((Resume.title.like(kw)) | (Resume.target_position.like(kw)))
    return _page_data(q, page, page_size, lambda r: ResumeOut.model_validate(r).model_dump())


@router.post("")
def create_resume(data: ResumeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not data.title.strip():
        raise HTTPException(status_code=400, detail="请填写简历标题")
    if not data.text.strip():
        raise HTTPException(status_code=400, detail="请上传简历文件或粘贴简历文本")
    text = normalize_text(data.text)
    resume = Resume(
        user_id=user.id,
        title=data.title.strip(),
        target_position=data.target_position.strip(),
        job_desc=data.job_desc.strip(),
        original_text=text,
        current_text=text,
        file_name="",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return ResumeOut.model_validate(resume).model_dump()


@router.post("/upload")
async def upload_resume(
    title: str = Form(...),
    target_position: str = Form(""),
    job_desc: str = Form(""),
    file: UploadFile = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not title.strip():
        raise HTTPException(status_code=400, detail="请填写简历标题")
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="请选择简历文件")
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in ALLOWED_RESUME_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 PDF / Word(docx) / TXT / HTML 格式")
    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")
    text = parse_resume_file(file.filename, data)
    resume = Resume(
        user_id=user.id,
        title=title.strip(),
        target_position=target_position.strip(),
        job_desc=job_desc.strip(),
        original_text=text,
        current_text=text,
        file_name=file.filename,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return ResumeOut.model_validate(resume).model_dump()


@router.post("/{resume_id}/parse")
async def reparse_resume(
    resume_id: int,
    file: UploadFile = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重新上传文件并解析，替换当前简历的原始文本与当前文本"""
    resume = get_own_resume(resume_id, user, db)
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="请选择简历文件")
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in ALLOWED_RESUME_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 PDF / Word(docx) / TXT / HTML 格式")
    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")
    text = parse_resume_file(file.filename, data)
    resume.original_text = text
    resume.current_text = text
    resume.file_name = file.filename
    db.commit()
    db.refresh(resume)
    return ResumeOut.model_validate(resume).model_dump()


@router.get("/{resume_id}")
def get_resume(resume_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = get_own_resume(resume_id, user, db)
    return ResumeOut.model_validate(resume).model_dump()


@router.put("/{resume_id}")
def update_resume(
    resume_id: int,
    data: ResumeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = get_own_resume(resume_id, user, db)
    if data.title is not None and data.title.strip():
        resume.title = data.title.strip()
    if data.target_position is not None:
        resume.target_position = data.target_position.strip()
    if data.job_desc is not None:
        resume.job_desc = data.job_desc.strip()
    if data.current_text is not None:
        resume.current_text = normalize_text(data.current_text)
    db.commit()
    db.refresh(resume)
    return ResumeOut.model_validate(resume).model_dump()


@router.delete("/{resume_id}")
def delete_resume(resume_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = get_own_resume(resume_id, user, db)
    db.delete(resume)
    db.commit()
    return {"ok": True}


@router.get("/{resume_id}/download")
def download_resume(resume_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = get_own_resume(resume_id, user, db)
    content = export_resume_docx(resume.title, resume.current_text)
    filename = quote(f"{resume.title}.docx")
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
