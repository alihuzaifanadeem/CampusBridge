from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .connection import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    profile_image_filename: Mapped[str] = mapped_column(String(80), default="")
    role: Mapped[str] = mapped_column(String(24), index=True)
    campus: Mapped[str] = mapped_column(String(80), default="Main Campus")
    department: Mapped[str] = mapped_column(String(120), default="")
    designation: Mapped[str] = mapped_column(String(120), default="")
    program: Mapped[str] = mapped_column(String(120), default="")
    semester: Mapped[str] = mapped_column(String(40), default="")
    passing_year: Mapped[str] = mapped_column(String(12), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    expertise: Mapped[list[str]] = mapped_column(JSONB, default=list)
    qualifications: Mapped[str] = mapped_column(String(255), default="")
    years_experience: Mapped[int] = mapped_column(Integer, default=0)
    room: Mapped[str] = mapped_column(String(120), default="")
    building: Mapped[str] = mapped_column(String(120), default="")
    office_extension: Mapped[str] = mapped_column(String(60), default="")
    availability: Mapped[str] = mapped_column(String(24), default="busy")
    schedule: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    consultation_preferences: Mapped[list[str]] = mapped_column(JSONB, default=list)
    response_time: Mapped[str] = mapped_column(String(80), default="Within 24 hours")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    posts: Mapped[list[Post]] = relationship(back_populates="author", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(140))
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), default="Academic Help")
    campus: Mapped[str] = mapped_column(String(80), default="Main Campus")
    visibility: Mapped[str] = mapped_column(String(24), default="all")
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    resources: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    author: Mapped[User] = relationship(back_populates="posts")
    comments: Mapped[list[Comment]] = relationship(back_populates="post", cascade="all, delete-orphan", order_by="Comment.created_at")
    likes: Mapped[list[PostLike]] = relationship(cascade="all, delete-orphan")
    saves: Mapped[list[SavedPost]] = relationship(cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    post: Mapped[Post] = relationship(back_populates="comments")
    author: Mapped[User] = relationship()


class PostLike(Base):
    __tablename__ = "post_likes"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)


class SavedPost(Base):
    __tablename__ = "saved_posts"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)


class GuidanceRequest(Base):
    __tablename__ = "guidance_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    requested_slot: Mapped[str] = mapped_column(String(120), default="Flexible")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    faculty: Mapped[User] = relationship(foreign_keys=[faculty_id])


class CollaborationRequest(Base):
    __tablename__ = "collaboration_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(120), default="")
    research_area: Mapped[str] = mapped_column(String(120), default="")
    expertise_needed: Mapped[str] = mapped_column(String(180), default="")
    duration: Mapped[str] = mapped_column(String(80), default="")
    priority: Mapped[str] = mapped_column(String(20), default="standard")
    deadline: Mapped[str] = mapped_column(String(40), default="")
    campus: Mapped[str] = mapped_column(String(80), default="Main Campus")
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    author: Mapped[User] = relationship()


class CollaborationResponse(Base):
    __tablename__ = "collaboration_responses"

    request_id: Mapped[int] = mapped_column(ForeignKey("collaboration_requests.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SiteSetting(Base):
    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AccountRequest(Base):
    __tablename__ = "account_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    student_id: Mapped[str] = mapped_column(String(80), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(24), index=True)
    campus: Mapped[str] = mapped_column(String(80), default="Main Campus")
    department: Mapped[str] = mapped_column(String(120), default="")
    card_front_image: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    card_front_mime: Mapped[str | None] = mapped_column(String(80), nullable=True)
    card_back_image: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    card_back_mime: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
