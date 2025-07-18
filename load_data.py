# load_data.py
# This script is updated for the new CSV format with a single 'points' and 'correctAnswer' column.

import pandas as pd
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import crud, schemas, models

# This command creates the tables in your PostgreSQL database if they don't exist.
print("Creating database tables...")
models.Base.metadata.create_all(bind=engine)
print("Tables created successfully (if they didn't already exist).")

# Path to your CSV file
CSV_PATH = "diddy.csv" # Make sure this is the correct filename

def load_questions_from_csv(db: Session):
    try:
        df = pd.read_csv(CSV_PATH)
        # Handle potential empty values in text fields by filling them with an empty string
        df.fillna('', inplace=True)
        print(f"Found {len(df)} questions in {CSV_PATH}")
    except FileNotFoundError:
        print(f"Error: The file {CSV_PATH} was not found.")
        return

    questions_added = 0
    
    for index, row in df.iterrows():
        # --- UPDATED LOGIC ---
        # Use the new column names from your latest CSV file and cast to string to avoid type errors
        question_text = str(row["questionText"])
        category = str(row["category"])
        points_for_correct_answer = float(str(row["points"]))
        correct_answer_letter = str(row["correctAnswer"])

        # Skip if question already exists
        if crud.get_question_by_text(db, text=question_text):
            print(f"Skipping existing question: '{question_text[:50]}...'")
            continue

        # Create the Question in the database
        question_schema = schemas.QuestionCreate(text=question_text, category=category)
        db_question = crud.create_question(db=db, question=question_schema)
        
        # --- UPDATED LOGIC ---
        # Define the options and their corresponding letters, casting to string
        option_map = {
            'A': str(row["optionA"]),
            'B': str(row["optionB"]),
            'C': str(row["optionC"]),
            'D': str(row["optionD"])
        }

        # Iterate through the options, assign points correctly, and create them
        for letter, text in option_map.items():
            # Determine points: full points if it's the correct answer, 0 otherwise
            points = points_for_correct_answer if letter == correct_answer_letter else 0.0
            
            option_schema = schemas.OptionBase(text=text, points=points)
            crud.create_option_for_question(db=db, option=option_schema, question_id=db_question.id)
        
        questions_added += 1
        print(f"Added question: '{question_text[:50]}...'")

    print("-" * 20)
    print(f"Successfully added {questions_added} new questions to the database.")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        load_questions_from_csv(db)
    finally:
        db.close()
