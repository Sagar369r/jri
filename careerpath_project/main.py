# main.py
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import os
import io
import json
import hashlib # Added for secure token handling

# Import all local modules
import crud, models, schemas, auth, ai_analysis, gdrive_service, email_service, user_logger
from database import SessionLocal, engine

# It's good practice to use Alembic for production migrations, 
# but for development, create_all is fine.
models.Base.metadata.create_all(bind=engine)

# The FastAPI app instance
app = FastAPI(
    title="JRI Career World API",
    description="API service for JRI Career World, optimized for Vercel/Render deployment."
)

# --- CORS Middleware Configuration ---
# This is a critical step for allowing your Vercel frontend to communicate with your Render backend.
# The regex allows your main Vercel domain and all preview deployment domains.
origins = [
    "https://jri-omega.vercel.app",  # CORRECTED: Your new production frontend URL
    "null"                          # For local development or specific tools like Postman
]
# Regex to match Vercel's preview deployment URLs (e.g., jri-omega-*-your-team.vercel.app)
# This prevents CORS errors during development and testing on preview branches.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex="https://jri-omega-.*\.vercel\.app", # CORRECTED: Regex for your new Vercel preview URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dependencies ---
def get_db():
    """Dependency to get a database session for each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(token: str = Depends(auth.oauth2_scheme), db: Session = Depends(get_db)):
    """Dependency to get the current authenticated user from a JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    email = auth.verify_access_token(token, credentials_exception)
    if email is None:
        raise credentials_exception
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user

# --- API ENDPOINTS ---
# =======================================================================================
# IMPORTANT NOTE: The "/api" prefix has been removed from all routes.
# Vercel's `vercel.json` rewrite configuration (e.g., { "source": "/api/(.*)", 
# "destination": "https://your-render-backend.onrender.com/(.*)" }) handles adding
# the prefix. If you include it here, the backend will receive a path like "/api/api/...",
# which will result in a 404 Not Found error.
# =======================================================================================

@app.get("/", tags=["Health Check"])
def read_root():
    """A root endpoint for health checks. Helps verify the service is running."""
    return {"status": "ok", "message": "Welcome to JRI Career World API"}

@app.post("/auth/magic-link/request", status_code=status.HTTP_202_ACCEPTED, tags=["Authentication"])
async def request_magic_link(request: schemas.MagicLinkRequest, db: Session = Depends(get_db)):
    """Requests a magic login link for a user."""
    user = crud.get_or_create_user(db, email=request.email)
    user_logger.log_user_email(user.email)
    
    # Create a secure token and its hash for verification
    plain_token, token_hash = auth.create_magic_link_token()
    
    crud.create_magic_token(db, email=request.email, token_hash=token_hash)
    email_service.send_magic_link(email=request.email, token=plain_token)
    
    return {"message": "If an account with this email exists, a magic link has been sent."}

@app.post("/auth/magic-link/login", response_model=schemas.Token, tags=["Authentication"])
async def login_with_magic_link(request: schemas.MagicLinkLogin, db: Session = Depends(get_db)):
    """
    Logs a user in using a magic link token.

    FIXED: The original implementation was insecure and inefficient. It fetched all unused tokens
    and checked them one by one, which is vulnerable to timing attacks and scales poorly.

    The corrected approach hashes the incoming token and queries the database for that specific hash.
    This requires your `auth.create_magic_link_token` to use a consistent hashing algorithm 
    (e.g., SHA-256) instead of a salted one (like bcrypt) for the magic link token itself.
    """
    # This is a placeholder for how you should hash the incoming token.
    # The hashing algorithm MUST match the one used in `auth.create_magic_link_token`.
    # For this example, we assume SHA-256 is used.
    try:
        # Hashing the token provided by the user to find its match in the database.
        token_hash_from_request = hashlib.sha256(request.token.encode('utf-8')).hexdigest()
    except Exception:
        # Handle cases where the token might not be a simple string
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token format.",
        )
        
    db_token_record = crud.get_magic_token_by_hash(db, token_hash=token_hash_from_request)

    if not db_token_record or db_token_record.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used magic link.",
        )
    
    # Mark the token as used to prevent replay attacks
    crud.use_magic_token(db, token_hash=db_token_record.token_hash)
    
    # Create a standard JWT access token for the user session
    access_token = auth.create_access_token(data={"sub": db_token_record.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=schemas.User, tags=["Users"])
async def read_users_me(current_user: schemas.User = Depends(get_current_user)):
    """Fetches the profile of the currently authenticated user."""
    return current_user

@app.post("/users/me/resume", response_model=schemas.User, tags=["Users"])
async def upload_and_analyze_resume(
    current_user: schemas.User = Depends(get_current_user),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Uploads, parses, and analyzes a user's resume."""
    contents = await file.read()
    filename = file.filename
    text = ""

    if filename.endswith(".pdf"):
        try:
            # PyPDF2 is deprecated, switching to pypdf is recommended when possible
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read PDF file: {e}")
    elif filename.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(contents))
            for para in doc.paragraphs:
                text += para.text + "\n"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read DOCX file: {e}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a .pdf or .docx file.")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract any text from the uploaded file.")

    analysis_results = await ai_analysis.analyze_resume_text(text)
    
    # Sanitizing text to remove null bytes which can cause database errors.
    sanitized_text = text.replace('\x00', '')
    sanitized_analysis = analysis_results.replace('\x00', '')

    try:
        gdrive_service.upload_file_to_drive(filename, contents, file.content_type)
        print(f"Successfully attempted to upload {filename} to Google Drive.")
    except Exception as e:
        # In production, you should use a proper logger instead of print.
        print(f"A Google Drive API error occurred: {e}")
        # Not raising an exception here, as the core function (resume analysis) succeeded.
        # The user doesn't need to know if the Drive backup failed.

    return crud.update_user_resume_data(db, user_id=current_user.id, text=sanitized_text, analysis=sanitized_analysis)

@app.get("/assessment/questions", response_model=List[schemas.Question], tags=["Assessment"])
def read_questions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Fetches a list of assessment questions."""
    return crud.get_questions(db, skip=skip, limit=limit)

@app.post("/assessment/submit", response_model=schemas.Assessment, tags=["Assessment"])
async def submit_assessment(
    assessment_data: schemas.AssessmentSubmit,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Submits user answers for an assessment and returns the analysis."""
    total_score, categories_summary, incorrect_answers = 0, {}, []

    for answer_data in assessment_data.answers:
        option = crud.get_option(db, option_id=answer_data.selected_option_id)
        if not option: continue
        
        question = crud.get_question(db, question_id=answer_data.question_id)
        if not question: continue
        
        total_score += option.points
        category = question.category
        
        if category not in categories_summary:
            categories_summary[category] = {'score': 0, 'total': 0}
            
        max_points = crud.get_max_points_for_question(db, question.id)
        categories_summary[category]['score'] += option.points
        categories_summary[category]['total'] += max_points
        
        if option.points == 0:
            incorrect_answers.append({"question": question.text, "selected_option": option.text})

    ai_feedback = await ai_analysis.generate_assessment_feedback(categories_summary, incorrect_answers)
    
    analysis_text = ai_feedback.get("performance_report", "Analysis not available.")
    suggestions_json = json.dumps(ai_feedback.get("course_suggestions", []))
    
    sanitized_analysis_text = analysis_text.replace('\x00', '')

    email_service.send_assessment_report(
        email=current_user.email, 
        report_markdown=sanitized_analysis_text, 
        score=total_score
    )
    
    return crud.create_assessment(
        db=db, 
        user_id=current_user.id, 
        score=total_score, 
        answers=assessment_data.answers, 
        analysis=sanitized_analysis_text, 
        suggestions=suggestions_json
    )

@app.get("/assessment/history", response_model=List[schemas.Assessment], tags=["Assessment"])
def get_assessment_history(db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    """Retrieves the assessment history for the current user."""
    # Ensure you have an index on owner_id for performance
    return db.query(models.Assessment).filter(models.Assessment.owner_id == current_user.id).all()
