# database.py
# This file sets up the database connection using PostgreSQL.
# CORRECTED: Using a more robust method to find and load the .env file.

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv, find_dotenv # Import find_dotenv

# Use find_dotenv() to reliably locate the .env file
load_dotenv(find_dotenv())

# Load database configuration from environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Construct the PostgreSQL database URL from the loaded variables
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# The engine is the core interface to the database.
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# The SessionLocal class is a factory for creating new database sessions.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is a factory for creating declarative model classes.
Base = declarative_base()
