# main.py
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from dotenv import load_dotenv, find_dotenv
import PyPDF2
import docx
import io
import json

# Import all local modules
import crud, models, schemas, auth, ai_analysis, gdrive_service, email_service, user_logger
from database import SessionLocal, engine

load_dotenv(find_dotenv())
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="JRI Career World API")

# CORS Middleware to allow ONLY your Vercel frontend to connect
origins = [
    "https://jri-l5ci.vercel.app",
    "https://jri-omega.vercel.app", # Added your newer frontend URL
    "null" 
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user

# --- Root Route ---
# ✅ FIX: Added a root GET endpoint to handle health checks and prevent 404 on the base URL.
@app.get("/")
def read_root():
    return {"message": "Welcome to the JRI Career World API!"}


# --- API ENDPOINTS ---

@app.post("/auth/magic-link/request", status_code=status.HTTP_202_ACCEPTED)
async def request_magic_link(request: schemas.MagicLinkRequest, db: Session = Depends(get_db)):
    user = crud.get_or_create_user(db, email=request.email)
    user_logger.log_user_email(user.email)
    plain_token, token_hash = auth.create_magic_link_token()
    crud.create_magic_token(db, email=request.email, token_hash=token_hash)
    email_service.send_magic_link(email=request.email, token=plain_token)
    return {"message": "If an account with this email exists, a magic link has been sent."}

@app.post("/auth/magic-link/login", response_model=schemas.Token)
async def login_with_magic_link(request: schemas.MagicLinkLogin, db: Session = Depends(get_db)):
    all_tokens = db.query(models.MagicToken).filter(models.MagicToken.is_used == False).all()
    db_token_record = None
    for token_record in all_tokens:
        if auth.verify_magic_link_token(request.token, token_record.token_hash):
            db_token_record = crud.use_magic_token(db, token_hash=token_record.token_hash)
            break
    if not db_token_record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired magic link.")
    access_token = auth.create_access_token(data={"sub": db_token_record.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=schemas.User)
async def read_users_me(current_user: schemas.User = Depends(get_current_user)):
    return current_user

@app.post("/users/me/resume", response_model=schemas.User)
async def upload_and_analyze_resume(current_user: schemas.User = Depends(get_current_user), file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    filename = file.filename
    text = ""
    if filename.endswith(".pdf"):
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
        for page in pdf_reader.pages: text += page.extract_text() or ""
    elif filename.endswith(".docx"):
        doc = docx.Document(io.BytesIO(contents))
        for para in doc.paragraphs: text += para.text + "\n"
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type.")
    if not text: raise HTTPException(status_code=400, detail="Could not extract text.")
    analysis_results = await ai_analysis.analyze_resume_text(text)
    sanitized_text = text.replace('\x00', '')
    sanitized_analysis = analysis_results.replace('\x00', '')
    try:
        gdrive_service.upload_file_to_drive(filename, contents, file.content_type)
    except Exception as e:
        print(f"A Google Drive API error occurred: {e}")
    return crud.update_user_resume_data(db, user_id=current_user.id, text=sanitized_text, analysis=sanitized_analysis)

@app.get("/assessment/questions", response_model=List[schemas.Question])
def read_questions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_questions(db, skip=skip, limit=limit)

@app.post("/assessment/submit", response_model=schemas.Assessment)
async def submit_assessment(assessment_data: schemas.AssessmentSubmit, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    total_score, categories_summary, incorrect_answers = 0, {}, []
    for answer_data in assessment_data.answers:
        option = crud.get_option(db, option_id=answer_data.selected_option_id)
        if not option: continue
        question = crud.get_question(db, question_id=answer_data.question_id)
        if not question: continue
        total_score += option.points
        category = question.category
        if category not in categories_summary: categories_summary[category] = {'score': 0, 'total': 0}
        max_points = crud.get_max_points_for_question(db, question.id)
        categories_summary[category]['score'] += option.points
        categories_summary[category]['total'] += max_points
        if option.points == 0: incorrect_answers.append({"question": question.text, "selected_option": option.text})
    ai_feedback = await ai_analysis.generate_assessment_feedback(categories_summary, incorrect_answers)
    analysis_text = ai_feedback.get("performance_report", "Analysis not available.")
    suggestions_json = json.dumps(ai_feedback.get("course_suggestions", []))
    sanitized_analysis_text = analysis_text.replace('\x00', '')
    email_service.send_assessment_report(email=current_user.email, report_markdown=sanitized_analysis_text, score=total_score)
    return crud.create_assessment(db=db, user_id=current_user.id, score=total_score, answers=assessment_data.answers, analysis=sanitized_analysis_text, suggestions=suggestions_json)

@app.get("/assessment/history", response_model=List[schemas.Assessment])
def get_assessment_history(db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    return db.query(models.Assessment).filter(models.Assessment.owner_id == current_user.id).all()
