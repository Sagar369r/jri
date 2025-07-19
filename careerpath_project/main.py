# main.py
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

# Import local modules
import crud, models, schemas, ai_analysis, gdrive_service, email_service
from database import SessionLocal, engine
# ✅ Import the router from your updated auth.py file
from auth import router as auth_router, get_current_user

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="JRI Career World API")

# CORS Middleware to allow your Vercel frontend(s) to connect
origins = [
    "https://jri-omega.vercel.app",
    "https://jri-l5ci.vercel.app",
    "https://jri-uz4s.onrender.com",
    "null"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include the authentication router as you specified.
# This adds the "/magic-link/request" and "/magic-link/login" routes
# with the prefix "/api/auth".
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])


# --- Dependencies ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Root Route for Health Check ---
@app.get("/")
def read_root():
    return {"message": "Welcome to the JRI Career World API!"}


# --- All OTHER API Endpoints remain here ---

@app.get("/api/users/me", response_model=schemas.User)
async def read_users_me(current_user: schemas.User = Depends(get_current_user)):
    return current_user

@app.post("/api/users/me/resume", response_model=schemas.User)
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

@app.get("/api/assessment/questions", response_model=List[schemas.Question])
def read_questions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_questions(db, skip=skip, limit=limit)

@app.post("/api/assessment/submit", response_model=schemas.Assessment)
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

@app.get("/api/assessment/history", response_model=List[schemas.Assessment])
def get_assessment_history(db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    return db.query(models.Assessment).filter(models.Assessment.owner_id == current_user.id).all()
