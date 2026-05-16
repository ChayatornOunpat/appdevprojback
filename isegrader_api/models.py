import uuid
from datetime import datetime, timezone

from .extensions import db


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    user_name = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email_confirmed = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    progresses = db.relationship(
        "UserQuestionProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    test_case = db.Column(db.Text, nullable=False)

    progresses = db.relationship(
        "UserQuestionProgress",
        back_populates="question",
        cascade="all, delete-orphan",
    )


class UserQuestionProgress(db.Model):
    __tablename__ = "user_question_progresses"

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    question_id = db.Column(
        db.Integer,
        db.ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    code = db.Column(db.Text, nullable=False, default="")
    progress = db.Column(db.SmallInteger, nullable=False, default=0)

    user = db.relationship("User", back_populates="progresses")
    question = db.relationship("Question", back_populates="progresses")
