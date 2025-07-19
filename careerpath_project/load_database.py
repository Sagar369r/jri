# load_database.py
# This script reads questions from a CSV file and populates the database.

import pandas as pd
from sqlalchemy.orm import Session
import crud, schemas

# The CSV file must be in the same directory as your python files on Render.
CSV_PATH = "diddy.csv"

# FIXED: The function has been renamed to 'populate_database' to match main.py
def populate_database(db: Session):
    """
    Populates the database with questions from the diddy.csv file.
    This function is called by main.py on startup if the database is empty.
    """
    print("Attempting to populate database from CSV...")
    
    try:
        df = pd.read_csv(CSV_PATH)
        # Handle potential empty values in text fields by filling them with an empty string
        df.fillna('', inplace=True)
        print(f"Found {len(df)} questions in {CSV_PATH}")
    except FileNotFoundError:
        print(f"FATAL ERROR: The file '{CSV_PATH}' was not found.")
        print("Please make sure 'diddy.csv' is uploaded to your Render project.")
        return
    except Exception as e:
        print(f"An error occurred reading the CSV file: {e}")
        return

    questions_added = 0
    
    for index, row in df.iterrows():
        try:
            # Use column names from your CSV file and cast to string to avoid type errors
            question_text = str(row["questionText"])
            category = str(row["category"])
            points_for_correct_answer = float(str(row["points"]))
            correct_answer_letter = str(row["correctAnswer"]).upper()

            # Skip if question already exists
            if crud.get_question_by_text(db, text=question_text):
                continue

            # Create the Question in the database
            question_schema = schemas.QuestionCreate(text=question_text, category=category)
            db_question = crud.create_question(db=db, question=question_schema)
            
            # Define the options and their corresponding letters
            option_map = {
                'A': str(row["optionA"]),
                'B': str(row["optionB"]),
                'C': str(row["optionC"]),
                'D': str(row["optionD"])
            }

            # Iterate through the options, assign points correctly, and create them
            for letter, text in option_map.items():
                if not text:
                    continue
                
                points = points_for_correct_answer if letter == correct_answer_letter else 0.0
                
                option_schema = schemas.OptionBase(text=text, points=points)
                crud.create_option_for_question(db=db, option=option_schema, question_id=db_question.id)
            
            questions_added += 1

        except KeyError as e:
            print(f"ERROR: A required column is missing from the CSV file: {e}. Skipping row {index + 2}.")
            continue
        except Exception as e:
            print(f"An unexpected error occurred at row {index + 2}: {e}. Skipping row.")
            continue

    print("-" * 20)
    print(f"Successfully added {questions_added} new questions to the database.")
    print("Database population check complete.")
