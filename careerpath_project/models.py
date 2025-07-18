# models.py
# Updated for Magic Link authentication.

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Float, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # The hashed_password and google_id fields are no longer needed for magic links
    # but we can leave them nullable for now to avoid migration issues.
    hashed_password = Column(String, nullable=True) 
    google_id = Column(String, unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resume_text = Column(Text, nullable=True)
    resume_analysis = Column(Text, nullable=True)
    assessments = relationship("Assessment", back_populates="owner")

# --- NEW MODEL ---
# This table will store the magic link tokens.
class MagicToken(Base):
    __tablename__ = "magic_tokens"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    token_hash = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False, unique=True)
    category = Column(String, index=True)
    options = relationship("Option", back_populates="question")

class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    points = Column(Float, nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"))
    question = relationship("Question", back_populates="options")

class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(Integer, primary_key=True, index=True)
    score = Column(Float, nullable=False)
    analysis = Column(Text, nullable=True)
    course_suggestions = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="assessments")
    answers = relationship("Answer", back_populates="assessment")

class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    selected_option_id = Column(Integer, ForeignKey("options.id"))
    assessment = relationship("Assessment", back_populates="answers")
