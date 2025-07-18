# schemas.py
# Updated for Magic Link authentication.

from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

# --- NEW SCHEMAS for Magic Link Flow ---

class MagicLinkRequest(BaseModel):
    email: EmailStr # Pydantic will validate that this is a valid email format

class MagicLinkLogin(BaseModel):
    token: str

# --- Token and User Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str

class UserBase(BaseModel):
    email: EmailStr

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    resume_text: Optional[str] = None
    resume_analysis: Optional[str] = None
    assessments: List['Assessment'] = []
    class Config:
        from_attributes = True

# --- Question and Option Schemas ---

class OptionBase(BaseModel):
    text: str
    points: float

class Option(OptionBase):
    id: int
    class Config:
        from_attributes = True

class QuestionCreate(BaseModel):
    text: str
    category: str

class Question(QuestionCreate):
    id: int
    options: List[Option] = []
    class Config:
        from_attributes = True

# --- Assessment Schemas ---

class AnswerSubmit(BaseModel):
    question_id: int
    selected_option_id: int

class AssessmentSubmit(BaseModel):
    answers: List[AnswerSubmit]

class Assessment(BaseModel):
    id: int
    owner_id: Optional[int] = None
    score: float
    analysis: Optional[str] = None
    course_suggestions: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

# This is needed for the User schema to correctly handle the relationship
User.model_rebuild()
