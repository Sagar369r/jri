# auth.py
# Updated for Magic Link authentication.

import os
from datetime import datetime, timedelta
from typing import Optional
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
# This is the access token for the user's session after they log in
ACCESS_TOKEN_EXPIRE_MINUTES = 60 
# This is how long the magic link itself is valid
MAGIC_LINK_EXPIRE_MINUTES = 15

# This context is for hashing and verifying the magic link tokens
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # This remains for session management

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates the standard session JWT for the user."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str, credentials_exception):
    """Verifies the standard session JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
        return email
    except JWTError:
        raise credentials_exception

# --- NEW MAGIC LINK FUNCTIONS ---

def create_magic_link_token() -> (str, str):
    """
    Generates a secure, URL-safe token for the magic link and its hash.
    Returns the plain token (to be sent to the user) and its hash (to be stored).
    """
    plain_token = secrets.token_urlsafe(32)
    token_hash = pwd_context.hash(plain_token)
    return plain_token, token_hash

def verify_magic_link_token(plain_token: str, hashed_token: str) -> bool:
    """Verifies a plain token against its stored hash."""
    return pwd_context.verify(plain_token, hashed_token)
