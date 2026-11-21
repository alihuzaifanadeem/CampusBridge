from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .database import (
    Base,
    CollaborationRequest,
    CollaborationResponse,
    Comment,
    GuidanceRequest,
    Post,
    PostLike,
    SavedPost,
    SessionLocal,
    SiteSetting,
    User,
    engine,
    get_db,
)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(derived).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, expected_b64 = stored.split("$", 2)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(expected_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def make_token(user_id: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"sub": user_id, "exp": int((datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).timestamp())}, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def token_user_id(token: str) -> int:
    try:
        payload, signature = token.split(".", 1)
        expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest()
        received = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, received):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(data["exp"]) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError
        return int(data["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired. Please sign in again.")


bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    user = db.get(User, token_user_id(credentials.credentials))
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="This account is unavailable.")
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You do not have access to this feature.")
        return user
    return checker


class RegisterBody(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: Literal["student", "faculty", "alumni"]
    campus: str = Field(default="Main Campus", max_length=80)
    department: str = Field(default="", max_length=120)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    campus: str | None = Field(default=None, max_length=80)
    department: str | None = Field(default=None, max_length=120)
    designation: str | None = Field(default=None, max_length=120)
    program: str | None = Field(default=None, max_length=120)
    semester: str | None = Field(default=None, max_length=40)
    passing_year: str | None = Field(default=None, max_length=12)
    bio: str | None = Field(default=None, max_length=600)
    expertise: list[str] | None = None
    qualifications: str | None = Field(default=None, max_length=255)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    room: str | None = Field(default=None, max_length=120)
    building: str | None = Field(default=None, max_length=120)
    office_extension: str | None = Field(default=None, max_length=60)
    availability: Literal["available", "busy", "away"] | None = None
    schedule: list[dict[str, Any]] | None = None
    consultation_preferences: list[str] | None = None
    response_time: str | None = Field(default=None, max_length=80)


class PostCreate(BaseModel):
    title: str = Field(min_length=4, max_length=140)
    content: str = Field(min_length=10, max_length=500)
    category: str = Field(default="Academic Help", max_length=80)
    campus: str = Field(default="All Campuses", max_length=80)
    visibility: Literal["all", "campus"] = "all"
    tags: list[str] = Field(default_factory=list, max_length=8)
    resources: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("resources")
    @classmethod
    def resources_must_be_http_links(cls, values: list[str]) -> list[str]:
        for value in values:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Resources must use an http or https URL.")
        return values


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class GuidanceCreate(BaseModel):
    faculty_id: int
    topic: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=10, max_length=1000)
    requested_slot: str = Field(default="Flexible", max_length=120)


class RequestStatusUpdate(BaseModel):
    status: Literal["approved", "declined", "rescheduled"]


class CollaborationCreate(BaseModel):
    title: str = Field(min_length=5, max_length=180)
    description: str = Field(min_length=20, max_length=1600)
    category: str = Field(max_length=80)
    department: str = Field(default="", max_length=120)
    research_area: str = Field(default="", max_length=120)
    expertise_needed: str = Field(default="", max_length=180)
    duration: str = Field(default="", max_length=80)
    priority: Literal["high", "medium", "standard"] = "standard"
    deadline: str = Field(default="", max_length=40)
    campus: str = Field(default="All Campuses", max_length=80)


class AdminUserUpdate(BaseModel):
    verified: bool | None = None
    active: bool | None = None


class ProfileCoverUpdate(BaseModel):
    theme: Literal["blue", "violet", "teal", "sunset"]
    width: int = Field(default=1600, ge=320, le=2400)
    height: int = Field(default=177, ge=100, le=500)


PROFILE_COVER_MEDIA_DIR = Path(os.getenv("MEDIA_DIR", str(Path(__file__).resolve().parents[1] / "media")))
PROFILE_COVER_MAX_BYTES = 2 * 1024 * 1024


def user_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "campus": user.campus,
        "department": user.department,
        "designation": user.designation,
        "program": user.program,
        "semester": user.semester,
        "passing_year": user.passing_year,
        "bio": user.bio,
        "expertise": user.expertise or [],
        "qualifications": user.qualifications,
        "years_experience": user.years_experience,
        "room": user.room,
        "building": user.building,
        "office_extension": user.office_extension,
        "availability": user.availability,
        "schedule": user.schedule or [],
        "consultation_preferences": user.consultation_preferences or [],
        "response_time": user.response_time,
        "verified": user.verified,
        "active": user.active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def post_dict(db: Session, post: Post, viewer: User) -> dict[str, Any]:
    like_count = db.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == post.id)) or 0
    comment_count = len(post.comments)
    liked = db.get(PostLike, (viewer.id, post.id)) is not None
    saved = db.get(SavedPost, (viewer.id, post.id)) is not None
    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "category": post.category,
        "campus": post.campus,
        "visibility": post.visibility,
        "tags": post.tags or [],
        "resources": post.resources or [],
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "author": user_dict(post.author),
        "like_count": like_count,
        "comment_count": comment_count,
        "liked": liked,
        "saved": saved,
        "comments": [{"id": c.id, "content": c.content, "created_at": c.created_at.isoformat(), "author": user_dict(c.author)} for c in post.comments],
    }


def guidance_dict(item: GuidanceRequest) -> dict[str, Any]:
    return {
        "id": item.id,
        "topic": item.topic,
        "message": item.message,
        "requested_slot": item.requested_slot,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "requester": user_dict(item.requester),
        "faculty": user_dict(item.faculty),
    }


def collaboration_dict(db: Session, item: CollaborationRequest, viewer: User) -> dict[str, Any]:
    interested = db.scalar(select(func.count()).select_from(CollaborationResponse).where(CollaborationResponse.request_id == item.id)) or 0
    accepted = db.get(CollaborationResponse, (item.id, viewer.id)) is not None
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "department": item.department,
        "research_area": item.research_area,
        "expertise_needed": item.expertise_needed,
        "duration": item.duration,
        "priority": item.priority,
        "deadline": item.deadline,
        "campus": item.campus,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "author": user_dict(item.author),
        "interested_count": interested,
        "accepted": accepted,
    }


app = FastAPI(title="CampusBridge API", version="1.0.0", description="Student, faculty, and alumni collaboration API.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(select(1))
    return {"status": "ok", "database": "connected"}


@app.post("/api/auth/register", status_code=201)
def register(body: RegisterBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        role=body.role,
        campus=body.campus,
        department=body.department,
        verified=body.role != "faculty",
        availability="busy",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": make_token(user.id), "token_type": "bearer", "user": user_dict(user)}


@app.post("/api/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return {"access_token": make_token(user.id), "token_type": "bearer", "user": user_dict(user)}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)) -> dict[str, Any]:
    return user_dict(user)


@app.patch("/api/auth/me")
def update_me(body: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    allowed = body.model_dump(exclude_unset=True)
    if user.role != "faculty":
        allowed.pop("availability", None)
        allowed.pop("schedule", None)
        allowed.pop("room", None)
        allowed.pop("building", None)
        allowed.pop("office_extension", None)
        allowed.pop("designation", None)
        allowed.pop("qualifications", None)
        allowed.pop("years_experience", None)
        allowed.pop("consultation_preferences", None)
        allowed.pop("response_time", None)
    for key, value in allowed.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user_dict(user)


@app.get("/api/users")
def list_users(
    q: str = "",
    role: str = "",
    department: str = "",
    campus: str = "",
    availability: str = "",
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> list[dict[str, Any]]:
    query = select(User).where(User.active.is_(True))
    if role:
        query = query.where(User.role == role)
    if role == "faculty" or not role:
        query = query.where(or_(User.role != "faculty", User.verified.is_(True)))
    if department:
        query = query.where(User.department == department)
    if campus and campus != "All Campuses":
        query = query.where(User.campus == campus)
    if availability:
        query = query.where(User.availability == availability)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(or_(User.full_name.ilike(pattern), User.department.ilike(pattern), User.designation.ilike(pattern), User.expertise.cast(String).ilike(pattern), User.bio.ilike(pattern)))
    query = query.order_by(User.full_name).limit(150)
    return [user_dict(u) for u in db.scalars(query).all()]


@app.get("/api/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db), viewer: User = Depends(current_user)) -> dict[str, Any]:
    target = db.get(User, user_id)
    if not target or not target.active or (target.role == "faculty" and not target.verified and viewer.role not in {"admin", "system_admin"}):
        raise HTTPException(status_code=404, detail="Profile not found.")
    return user_dict(target)


@app.get("/api/posts")
def list_posts(
    q: str = "",
    campus: str = "All Campuses",
    category: str = "",
    saved: bool = False,
    db: Session = Depends(get_db),
    viewer: User = Depends(current_user),
) -> list[dict[str, Any]]:
    query = select(Post).join(User).where(User.active.is_(True))
    if campus and campus != "All Campuses":
        query = query.where(or_(Post.visibility == "all", Post.campus == campus))
    if category:
        query = query.where(Post.category.ilike(f"%{category}%"))
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Post.title.ilike(pattern), Post.content.ilike(pattern), Post.tags.cast(String).ilike(pattern)))
    if saved:
        query = query.join(SavedPost, SavedPost.post_id == Post.id).where(SavedPost.user_id == viewer.id)
    posts = db.scalars(query.order_by(Post.created_at.desc()).limit(100)).unique().all()
    return [post_dict(db, item, viewer) for item in posts]


@app.post("/api/posts", status_code=201)
def create_post(body: PostCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    post = Post(author_id=user.id, title=body.title.strip(), content=body.content.strip(), category=body.category, campus=body.campus, visibility=body.visibility, tags=body.tags)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post_dict(db, post, user)


@app.post("/api/posts/{post_id}/comments", status_code=201)
def create_comment(post_id: int, body: CommentCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Discussion not found.")
    comment = Comment(post_id=post_id, author_id=user.id, content=body.content.strip())
    db.add(comment)
    db.commit()
    db.refresh(post)
    return post_dict(db, post, user)


@app.post("/api/posts/{post_id}/like")
def toggle_like(post_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    if not db.get(Post, post_id):
        raise HTTPException(status_code=404, detail="Discussion not found.")
    current = db.get(PostLike, (user.id, post_id))
    if current:
        db.delete(current)
        liked = False
    else:
        db.add(PostLike(user_id=user.id, post_id=post_id))
        liked = True
    db.commit()
    return {"liked": liked, "like_count": db.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id)) or 0}


@app.post("/api/posts/{post_id}/save")
def toggle_saved(post_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, bool]:
    if not db.get(Post, post_id):
        raise HTTPException(status_code=404, detail="Discussion not found.")
    current = db.get(SavedPost, (user.id, post_id))
    if current:
        db.delete(current)
        saved = False
    else:
        db.add(SavedPost(user_id=user.id, post_id=post_id))
        saved = True
    db.commit()
    return {"saved": saved}


@app.get("/api/guidance-requests")
def list_guidance(db: Session = Depends(get_db), user: User = Depends(current_user)) -> list[dict[str, Any]]:
    query = select(GuidanceRequest)
    if user.role == "student" or user.role == "alumni":
        query = query.where(GuidanceRequest.requester_id == user.id)
    elif user.role == "faculty":
        query = query.where(GuidanceRequest.faculty_id == user.id)
    items = db.scalars(query.order_by(GuidanceRequest.created_at.desc())).all()
    return [guidance_dict(item) for item in items]


@app.post("/api/guidance-requests", status_code=201)
def create_guidance(body: GuidanceCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("student"))) -> dict[str, Any]:
    faculty = db.get(User, body.faculty_id)
    if not faculty or faculty.role != "faculty" or not faculty.active or not faculty.verified:
        raise HTTPException(status_code=404, detail="Verified faculty profile not found.")
    item = GuidanceRequest(requester_id=user.id, faculty_id=faculty.id, topic=body.topic.strip(), message=body.message.strip(), requested_slot=body.requested_slot)
    db.add(item)
    db.commit()
    db.refresh(item)
    return guidance_dict(item)


@app.patch("/api/guidance-requests/{request_id}")
def update_guidance(request_id: int, body: RequestStatusUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("faculty"))) -> dict[str, Any]:
    item = db.get(GuidanceRequest, request_id)
    if not item or item.faculty_id != user.id:
        raise HTTPException(status_code=404, detail="Request not found.")
    item.status = body.status
    db.commit()
    db.refresh(item)
    return guidance_dict(item)


@app.get("/api/collaborations")
def list_collaborations(
    q: str = "",
    department: str = "",
    status_filter: str = "active",
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("faculty", "admin", "system_admin")),
) -> list[dict[str, Any]]:
    if user.role == "faculty" and not user.verified:
        raise HTTPException(status_code=403, detail="Faculty verification is required to access collaboration requests.")
    query = select(CollaborationRequest).where(CollaborationRequest.status == status_filter)
    if department:
        query = query.where(CollaborationRequest.department == department)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(or_(CollaborationRequest.title.ilike(pattern), CollaborationRequest.description.ilike(pattern), CollaborationRequest.expertise_needed.ilike(pattern), CollaborationRequest.research_area.ilike(pattern)))
    return [collaboration_dict(db, item, user) for item in db.scalars(query.order_by(CollaborationRequest.created_at.desc()).limit(100)).all()]


@app.post("/api/collaborations", status_code=201)
def create_collaboration(body: CollaborationCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("faculty"))) -> dict[str, Any]:
    if not user.verified:
        raise HTTPException(status_code=403, detail="A verified faculty profile is required to publish a collaboration request.")
    item = CollaborationRequest(author_id=user.id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return collaboration_dict(db, item, user)


@app.post("/api/collaborations/{request_id}/respond")
def respond_to_collaboration(request_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("faculty"))) -> dict[str, Any]:
    if not user.verified:
        raise HTTPException(status_code=403, detail="Faculty verification is required to respond to collaboration requests.")
    item = db.get(CollaborationRequest, request_id)
    if not item or item.status != "active":
        raise HTTPException(status_code=404, detail="Active collaboration request not found.")
    if item.author_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot respond to your own request.")
    response = db.get(CollaborationResponse, (request_id, user.id))
    if not response:
        db.add(CollaborationResponse(request_id=request_id, user_id=user.id))
        db.commit()
    return collaboration_dict(db, item, user)


@app.get("/api/admin/overview")
def admin_overview(db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "system_admin"))) -> dict[str, Any]:
    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "students": db.scalar(select(func.count()).select_from(User).where(User.role == "student")) or 0,
        "faculty": db.scalar(select(func.count()).select_from(User).where(User.role == "faculty")) or 0,
        "pending_faculty": db.scalar(select(func.count()).select_from(User).where(User.role == "faculty", User.verified.is_(False))) or 0,
        "posts": db.scalar(select(func.count()).select_from(Post)) or 0,
        "pending_requests": db.scalar(select(func.count()).select_from(GuidanceRequest).where(GuidanceRequest.status == "pending")) or 0,
    }


@app.get("/api/profile-cover")
def get_profile_cover(db: Session = Depends(get_db)) -> dict[str, Any]:
    theme_setting = db.get(SiteSetting, "profile_cover_theme")
    image_setting = db.get(SiteSetting, "profile_cover_image")
    width_setting = db.get(SiteSetting, "profile_cover_width")
    height_setting = db.get(SiteSetting, "profile_cover_height")
    theme = theme_setting.value if theme_setting and theme_setting.value in {"blue", "violet", "teal", "sunset"} else "blue"
    width = int(width_setting.value) if width_setting and width_setting.value.isdigit() else 1600
    height = int(height_setting.value) if height_setting and height_setting.value.isdigit() else 177
    image_version = int(image_setting.updated_at.timestamp() * 1_000_000) if image_setting else 0
    return {
        "theme": theme,
        "width": width,
        "height": height,
        "image_url": f"/api/profile-cover/image?v={image_version}" if image_setting else None,
    }


@app.get("/api/profile-cover/image")
def get_profile_cover_image(db: Session = Depends(get_db)) -> FileResponse:
    setting = db.get(SiteSetting, "profile_cover_image")
    if not setting or not setting.value:
        raise HTTPException(status_code=404, detail="No shared profile cover image is configured.")
    filename = setting.value
    extensions = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}
    extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
    stem = filename.rsplit(".", 1)[0] if "." in filename else ""
    if len(stem) != 32 or any(char not in "0123456789abcdef" for char in stem) or extension not in extensions:
        raise HTTPException(status_code=404, detail="The shared profile cover image is unavailable.")
    path = PROFILE_COVER_MEDIA_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="The shared profile cover image is unavailable.")
    return FileResponse(path, media_type=extensions[extension], headers={"Cache-Control": "public, max-age=3600"})


@app.put("/api/admin/profile-cover")
async def update_profile_cover(
    theme: Literal["blue", "violet", "teal", "sunset"] = Form(...),
    width: int = Form(default=1600, ge=320, le=2400),
    height: int = Form(default=177, ge=100, le=500),
    image: UploadFile | None = File(default=None),
    remove_image: bool = Form(default=False),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin", "system_admin")),
) -> dict[str, Any]:
    body = ProfileCoverUpdate(theme=theme, width=width, height=height)
    old_image_setting = db.get(SiteSetting, "profile_cover_image")
    old_filename = old_image_setting.value if old_image_setting else None
    new_filename = None
    image_bytes = None

    if image is not None:
        image_bytes = await image.read(PROFILE_COVER_MAX_BYTES + 1)
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Choose a non-empty image file.")
        if len(image_bytes) > PROFILE_COVER_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Profile cover images must be 2 MB or smaller.")
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            extension = "png"
        elif image_bytes.startswith(b"\xff\xd8\xff"):
            extension = "jpg"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            extension = "webp"
        else:
            raise HTTPException(status_code=415, detail="Use a PNG, JPG, or WebP image.")
        new_filename = f"{uuid.uuid4().hex}.{extension}"
        PROFILE_COVER_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        (PROFILE_COVER_MEDIA_DIR / new_filename).write_bytes(image_bytes)

    def save_setting(key: str, value: str) -> SiteSetting:
        setting = db.get(SiteSetting, key)
        if setting is None:
            setting = SiteSetting(key=key, value=value)
            db.add(setting)
        else:
            setting.value = value
            setting.updated_at = datetime.now(timezone.utc)
        return setting

    save_setting("profile_cover_theme", body.theme)
    save_setting("profile_cover_width", str(body.width))
    save_setting("profile_cover_height", str(body.height))
    if new_filename:
        save_setting("profile_cover_image", new_filename)
    elif remove_image and old_image_setting:
        db.delete(old_image_setting)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if new_filename:
            (PROFILE_COVER_MEDIA_DIR / new_filename).unlink(missing_ok=True)
        raise

    if old_filename and (new_filename or remove_image):
        (PROFILE_COVER_MEDIA_DIR / old_filename).unlink(missing_ok=True)
    image_setting = db.get(SiteSetting, "profile_cover_image")
    image_version = int(image_setting.updated_at.timestamp() * 1_000_000) if image_setting else 0
    return {
        "theme": body.theme,
        "width": body.width,
        "height": body.height,
        "image_url": f"/api/profile-cover/image?v={image_version}" if image_setting else None,
    }


@app.get("/api/admin/users")
def admin_users(q: str = "", db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "system_admin"))) -> list[dict[str, Any]]:
    query = select(User)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(or_(User.email.ilike(pattern), User.full_name.ilike(pattern), User.role.ilike(pattern)))
    return [user_dict(item) for item in db.scalars(query.order_by(User.created_at.desc()).limit(250)).all()]


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, body: AdminUserUpdate, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin", "system_admin"))) -> dict[str, Any]:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if actor.id == target.id and body.active is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return user_dict(target)


@app.delete("/api/admin/posts/{post_id}", status_code=204)
def admin_remove_post(post_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "system_admin"))) -> Response:
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    db.delete(post)
    db.commit()
    return Response(status_code=204)


def seed_demo_data() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)):
            return
        seed_users = [
            User(email="student@campusbridge.edu", password_hash=hash_password(DEMO_PASSWORD), full_name="Arbaz Khan", role="student", campus="Main Campus", department="Computer Science", program="BS Computer Science", semester="Semester 7", bio="Final-year computer science student interested in AI, machine learning, and research collaboration.", expertise=["Artificial Intelligence", "Machine Learning", "Software Development", "Data Science"], verified=True),
            User(email="faculty@campusbridge.edu", password_hash=hash_password(DEMO_PASSWORD), full_name="Dr. Saira Khurram", role="faculty", campus="Main Campus", department="Computer Science", designation="Senior Lecturer · Head, FYDP Committee", bio="I work with students on machine learning, data science, and final year research.", expertise=["Machine Learning", "Data Science", "Artificial Intelligence"], qualifications="PhD, Computer Science", years_experience=12, room="Room 5, 5th floor", building="Faculty of Computing Building", office_extension="+92 21 3567 8901 ext. 204", availability="available", consultation_preferences=["student_consultations", "fyp_supervision", "research_collaboration"], response_time="Within 24 hours", schedule=[{"day":"Monday","time":"10:00 AM","label":"Office hours","kind":"consultation"},{"day":"Tuesday","time":"02:00 PM","label":"CS 401 · Lecture","kind":"lecture"},{"day":"Wednesday","time":"11:00 AM","label":"Research meeting","kind":"research"},{"day":"Thursday","time":"03:00 PM","label":"Office hours","kind":"consultation"}], verified=True),
            User(email="faculty2@campusbridge.edu", password_hash=hash_password(DEMO_PASSWORD), full_name="Syed Zain Mir", role="faculty", campus="City Campus", department="Software Engineering", designation="Senior Lecturer", bio="Software architecture, cloud computing, and design patterns.", expertise=["Software Architecture", "Cloud Computing", "Design Patterns"], qualifications="MS, Software Engineering", years_experience=8, room="Room 6, North Wing", availability="busy", verified=True),
            User(email="alumni@campusbridge.edu", password_hash=hash_password(DEMO_PASSWORD), full_name="Maya Rodriguez", role="alumni", campus="City Campus", department="Computer Science", passing_year="2024", bio="Software engineer and alumna sharing career advice and practical research experience.", expertise=["Natural Language Processing", "Career Development"], verified=True),
            User(email="admin@campusbridge.edu", password_hash=hash_password(DEMO_PASSWORD), full_name="CampusBridge Admin", role="admin", campus="Main Campus", verified=True),
            User(email="sysadmin@campusbridge.edu", password_hash=hash_password(DEMO_PASSWORD), full_name="System Administrator", role="system_admin", campus="Main Campus", verified=True),
        ]
        db.add_all(seed_users)
        db.flush()
        student, faculty, faculty2, alumni = seed_users[:4]
        demo_posts = [
            Post(author_id=faculty.id, title="Office hours: AI & Machine Learning guidance", content="I have extended my office hours this week for students working on machine learning projects. I can help with model selection, dataset preparation, and implementation questions. Send a consultation request to find a time.", category="Faculty Guidance", campus="Main Campus", tags=["MachineLearning", "FYP", "OfficeHours"]),
            Post(author_id=student.id, title="Looking for research collaboration: NLP project", content="I am building a sentiment analysis tool for social media data as part of my final year project. I am looking for collaborators interested in NLP, data preprocessing, or frontend visualization. Previous ML experience is helpful but not required.", category="Research Discussions", campus="City Campus", tags=["Research", "NLP", "TeamFormation", "FYP"]),
            Post(author_id=alumni.id, title="Career insights: from student to software engineer", content="I have finished my first year in industry and am happy to share what helped me prepare for interviews, choose a first role, and turn university projects into a portfolio.", category="Alumni Insights", campus="All Campuses", tags=["CareerAdvice", "SoftwareEngineering", "AlumniInsights"]),
        ]
        db.add_all(demo_posts)
        db.flush()
        db.add_all([
            Comment(post_id=demo_posts[0].id, author_id=student.id, content="I would like to discuss a dataset for my project. I will send a request."),
            Comment(post_id=demo_posts[1].id, author_id=faculty.id, content="This sounds promising. Consider starting with a small, well-labeled corpus."),
        ])
        db.add(CollaborationRequest(author_id=faculty.id, title="External FYP evaluator for software engineering projects", description="Seeking an experienced faculty evaluator for final year projects in software engineering. Projects cover distributed systems, mobile apps, and AI-integrated platforms.", category="External FYP Evaluation", department="Computer Science", research_area="Software Engineering", expertise_needed="Systems design", duration="2 weeks", priority="high", deadline="December 20, 2026", campus="All Campuses"))
        db.add(GuidanceRequest(requester_id=student.id, faculty_id=faculty.id, topic="FYP proposal review", message="Could we review my proposal outline and discuss a feasible evaluation plan?", requested_slot="Monday, 10:00 AM", status="pending"))
        db.commit()


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_DEMO_DATA", "true").lower() == "true":
        seed_demo_data()
