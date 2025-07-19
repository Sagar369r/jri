# main.py
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import os
import io
import json
import re
from datetime import datetime

# Import all local modules
import crud, models, schemas, auth, ai_analysis, email_service, user_logger
import cloudinary_service # <-- IMPORT THE NEW CLOUDINARY SERVICE
from database import SessionLocal, engine
import load_database

# Create database tables
models.Base.metadata.create_all(bind=engine)

# --- AUTOMATIC DATABASE POPULATION ---
def initialize_database():
    db = SessionLocal()
    try:
        question_count = db.query(models.Question).count()
        if question_count == 0:
            print("--- DATABASE INITIALIZATION ---")
            print("The 'questions' table is empty. Populating with initial data...")
            load_database.populate_database(db)
            print("Database population complete.")
            print("-----------------------------")
        else:
            print(f"Database already contains {question_count} questions. Skipping population.")
    finally:
        db.close()

initialize_database()
# ------------------------------------


app = FastAPI(
    title="JRI Career World API",
    description="API service for JRI Career World, optimized for Vercel/Render deployment."
)

# --- CORS Middleware Configuration ---
origins = [
    "https://jri-omega.vercel.app",
    "null"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://jri-omega-.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dependencies ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(token: str = Depends(auth.oauth2_scheme), db: Session = Depends(get_db)):
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

@app.post("/users/me/resume", response_model=schemas.User, tags=["Users"])
async def upload_and_analyze_resume(
    current_user: schemas.User = Depends(get_current_user),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    UPDATED: This endpoint now uploads resumes to Cloudinary instead of Google Drive.
    """
    contents = await file.read()
    filename = file.filename
    text = ""
    
    if filename.endswith(".pdf"):
        try:
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
    
    sanitized_text = text.replace('\x00', '')
    sanitized_analysis = analysis_results.replace('\x00', '')

    try:
        # --- UPDATED LOGIC ---
        # Call the Cloudinary upload function
        file_url = cloudinary_service.upload_file_to_cloudinary(
            filename=filename,
            file_contents=contents,
            mimetype=file.content_type
        )
        print(f"Successfully uploaded {filename} to Cloudinary.")
        # You could optionally save the file_url to the user's profile here if needed.
        # For example: crud.update_user_resume_url(db, user_id=current_user.id, url=file_url)
        # --- END OF UPDATED LOGIC ---
    except Exception as e:
        print(f"A Cloudinary API error occurred: {e}")
        # We don't raise an exception here because the core analysis succeeded.
        # The user doesn't need to know if the cloud backup failed.

    return crud.update_user_resume_data(db, user_id=current_user.id, text=sanitized_text, analysis=sanitized_analysis)


# (The rest of your main.py file remains the same)
@app.get("/", tags=["Health Check"])
def read_root():
    return {"status": "ok", "message": "Welcome to JRI Career World API"}

@app.post("/auth/magic-link/request", status_code=status.HTTP_202_ACCEPTED, tags=["Authentication"])
async def request_magic_link(request: schemas.MagicLinkRequest, db: Session = Depends(get_db)):
    user = crud.get_or_create_user(db, email=request.email)
    user_logger.log_user_email(user.email)
    plain_token, token_hash = auth.create_magic_link_token()
    crud.create_magic_token(db, email=request.email, token_hash=token_hash)
    email_service.send_magic_link(email=request.email, token=plain_token)
    return {"message": "If an account with this email exists, a magic link has been sent."}

@app.post("/auth/magic-link/login", response_model=schemas.Token, tags=["Authentication"])
async def login_with_magic_link(request: schemas.MagicLinkLogin, db: Session = Depends(get_db)):
    valid_tokens = db.query(models.MagicToken).filter(
        models.MagicToken.is_used == False,
        models.MagicToken.expires_at > datetime.utcnow()
    ).all()

    db_token_record = None
    for token_record in valid_tokens:
        if auth.verify_magic_link_token(request.token, token_record.token_hash):
            db_token_record = crud.use_magic_token(db, token_hash=token_record.token_hash)
            break

    if not db_token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used magic link.",
        )

    access_token = auth.create_access_token(data={"sub": db_token_record.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=schemas.User, tags=["Users"])
async def read_users_me(current_user: schemas.User = Depends(get_current_user)):
    return current_user

@app.get("/assessment/questions", response_model=List[schemas.Question], tags=["Assessment"])
def read_questions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_questions(db, skip=skip, limit=limit)

@app.post("/assessment/submit", response_model=schemas.Assessment, tags=["Assessment"])
async def submit_assessment(
    assessment_data: schemas.AssessmentSubmit,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
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
    
    sanitized_analysis_text = "Analysis not available."
    sanitized_suggestions = []

    analysis_text = ai_feedback.get("performance_report")
    if isinstance(analysis_text, str):
        sanitized_analysis_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', analysis_text)

    course_suggestions = ai_feedback.get("course_suggestions")
    if isinstance(course_suggestions, list):
        for course in course_suggestions:
            if isinstance(course, dict):
                sanitized_course = {}
                for key, value in course.items():
                    if isinstance(value, str):
                        sanitized_course[key] = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
                    else:
                        sanitized_course[key] = value
                sanitized_suggestions.append(sanitized_course)

    suggestions_json = json.dumps(sanitized_suggestions)

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
    return db.query(models.Assessment).filter(models.Assessment.owner_id == current_user.id).all()
