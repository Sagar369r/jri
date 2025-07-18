# crud.py
# Updated for Magic Link authentication.

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import datetime, timedelta

import models, schemas, auth

# --- User Functions ---

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Retrieves a user by their email address."""
    return db.query(models.User).filter(models.User.email == email).first()

def get_or_create_user(db: Session, email: str) -> models.User:
    """
    Retrieves a user by email. If the user does not exist, a new one is created.
    This simplifies the login/signup process into a single step.
    """
    db_user = get_user_by_email(db, email=email)
    if db_user:
        return db_user
    # User does not exist, create a new one
    new_user = models.User(email=email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def update_user_resume_data(db: Session, user_id: int, text: str, analysis: str):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        db_user.resume_text = text
        db_user.resume_analysis = analysis
        db.commit(); db.refresh(db_user)
    return db_user

# --- Magic Token Functions ---

def create_magic_token(db: Session, email: str, token_hash: str) -> models.MagicToken:
    """Stores a new magic link token hash in the database."""
    expires_at = datetime.utcnow() + timedelta(minutes=auth.MAGIC_LINK_EXPIRE_MINUTES)
    db_token = models.MagicToken(email=email, token_hash=token_hash, expires_at=expires_at)
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token

def get_magic_token(db: Session, token_hash: str) -> Optional[models.MagicToken]:
    """Retrieves a magic token record from the database by its hash."""
    return db.query(models.MagicToken).filter(models.MagicToken.token_hash == token_hash).first()

def use_magic_token(db: Session, token_hash: str) -> Optional[models.MagicToken]:
    """
    Finds a valid, unused, and unexpired magic token and marks it as used.
    Returns the token record if successful, otherwise None.
    """
    now = datetime.utcnow()
    # Find a token that matches the hash, has not been used, and has not expired
    db_token = db.query(models.MagicToken).filter(
        models.MagicToken.token_hash == token_hash,
        models.MagicToken.is_used == False,
        models.MagicToken.expires_at > now
    ).first()

    if db_token:
        db_token.is_used = True
        db.commit()
        return db_token
    return None


# --- Question and Option Functions ---

def create_question(db: Session, question: schemas.QuestionCreate):
    """Creates a new question in the database."""
    db_question = models.Question(text=question.text, category=question.category)
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

def create_option_for_question(db: Session, option: schemas.OptionBase, question_id: int):
    """Creates an option associated with a given question."""
    db_option = models.Option(**option.model_dump(), question_id=question_id)
    db.add(db_option)
    db.commit()
    db.refresh(db_option)
    return db_option

def get_questions(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Question).offset(skip).limit(limit).all()

def get_question(db: Session, question_id: int):
    return db.query(models.Question).filter(models.Question.id == question_id).first()

def get_question_by_text(db: Session, text: str):
    return db.query(models.Question).filter(models.Question.text == text).first()

def get_option(db: Session, option_id: int):
    return db.query(models.Option).filter(models.Option.id == option_id).first()

def get_max_points_for_question(db: Session, question_id: int):
    result = db.query(func.max(models.Option.points)).filter(models.Option.question_id == question_id).scalar()
    return result or 0

# --- Assessment Functions ---

def create_assessment(db: Session, user_id: Optional[int], score: float, answers: List[schemas.AnswerSubmit], analysis: Optional[str] = None, suggestions: Optional[str] = None):
    db_assessment = models.Assessment(score=score, owner_id=user_id, analysis=analysis, course_suggestions=suggestions)
    db.add(db_assessment); db.commit(); db.refresh(db_assessment)
    for answer in answers:
        db_answer = models.Answer(assessment_id=db_assessment.id, question_id=answer.question_id, selected_option_id=answer.selected_option_id)
        db.add(db_answer)
    db.commit()
    return db_assessment
