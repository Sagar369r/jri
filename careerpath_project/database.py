# database.py
# This file sets up the database connection using PostgreSQL.
# CORRECTED: This version prioritizes the DATABASE_URL from the hosting environment.

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file (primarily for local development)
load_dotenv(find_dotenv())

# --- Database URL Configuration ---
# Vercel, Render, and other hosts provide a single DATABASE_URL.
# This code prioritizes that URL for deployment.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# If DATABASE_URL is not found, fall back to constructing it from individual
# variables. This is useful for local development with a .env file.
if not SQLALCHEMY_DATABASE_URL:
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")

    # Check if all the required components are present
    if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
        raise ValueError("Database connection details are not fully set. Please check your environment variables.")
    
    SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# The engine is the core interface to the database.
# It will now use the correct URL for either local or deployed environments.
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# The SessionLocal class is a factory for creating new database sessions.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is a factory for creating declarative model classes.
Base = declarative_base()
