# auth.py
import os
from datetime import datetime, timedelta
from typing import Optional
import secrets

from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv, find_dotenv

# These are needed for the router and dependencies
import crud, models, schemas, email_service, user_logger
from database import SessionLocal

load_dotenv(find_dotenv())

# --- Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 
MAGIC_LINK_EXPIRE_MINUTES = 15

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Helper Functions (Token Logic) ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
        return email
    except JWTError:
        raise credentials_exception

def create_magic_link_token() -> (str, str):
    plain_token = secrets.token_urlsafe(32)
    token_hash = pwd_context.hash(plain_token)
    return plain_token, token_hash

def verify_magic_link_token(plain_token: str, hashed_token: str) -> bool:
    return pwd_context.verify(plain_token, hashed_token)

# --- FastAPI Router ---
router = APIRouter()

# Dependency to get a DB session for the router
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ FIX: The get_current_user function is now correctly placed in this file.
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    email = verify_access_token(token, credentials_exception)
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user

# --- API Endpoints for Authentication ---

@router.post("/magic-link/request", status_code=status.HTTP_202_ACCEPTED)
async def request_magic_link(request: schemas.MagicLinkRequest, db: Session = Depends(get_db)):
    user = crud.get_or_create_user(db, email=request.email)
    user_logger.log_user_email(user.email)
    plain_token, token_hash = create_magic_link_token()
    crud.create_magic_token(db, email=request.email, token_hash=token_hash)
    email_service.send_magic_link(email=request.email, token=plain_token)
    return {"message": "If an account with this email exists, a magic link has been sent."}

@router.post("/magic-link/login", response_model=schemas.Token)
async def login_with_magic_link(request: schemas.MagicLinkLogin, db: Session = Depends(get_db)):
    all_tokens = db.query(models.MagicToken).filter(models.MagicToken.is_used == False).all()
    db_token_record = None
    for token_record in all_tokens:
        if verify_magic_link_token(request.token, token_record.token_hash):
            db_token_record = crud.use_magic_token(db, token_hash=token_record.token_hash)
            break
    if not db_token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired magic link.",
        )
    access_token = create_access_token(data={"sub": db_token_record.email})
    return {"access_token": access_token, "token_type": "bearer"}
