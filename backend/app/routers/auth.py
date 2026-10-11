"""认证与个人中心：注册、登录、个人信息、修改密码、头像上传"""
import time

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import ALLOWED_AVATAR_EXTS, AVATAR_DIR, MAX_AVATAR_SIZE
from ..deps import get_current_user, get_db
from ..models import User
from ..schemas import LoginIn, PasswordChange, ProfileUpdate, RegisterIn, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_payload(user: User) -> dict:
    return {
        "token": create_access_token(user.id, user.role),
        "user": UserOut.model_validate(user).model_dump(),
    }


@router.post("/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    username = data.username.strip()
    if not (2 <= len(username) <= 30):
        raise HTTPException(status_code=400, detail="用户名长度需为 2-30 个字符")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=username,
        password_hash=hash_password(data.password),
        nickname=data.nickname.strip() or username,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _login_payload(user)


@router.post("/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username.strip()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    return _login_payload(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user).model_dump()


@router.put("/profile")
def update_profile(data: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.nickname is not None:
        user.nickname = data.nickname.strip() or user.nickname
    if data.email is not None:
        user.email = data.email.strip()
    if data.phone is not None:
        user.phone = data.phone.strip()
    db.commit()
    return UserOut.model_validate(user).model_dump()


@router.post("/avatar")
async def upload_avatar(file: UploadFile, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in (file.filename or "") else ""
    if ext not in ALLOWED_AVATAR_EXTS:
        raise HTTPException(status_code=400, detail="头像仅支持 png / jpg / jpeg / gif / webp")
    data = await file.read()
    if len(data) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="头像不能超过 5MB")
    name = f"u{user.id}_{int(time.time() * 1000)}.{ext}"
    (AVATAR_DIR / name).write_bytes(data)
    user.avatar = f"/files/avatars/{name}"
    db.commit()
    return {"avatar": user.avatar}


@router.put("/password")
def change_password(data: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"ok": True}
