# ai_analysis.py
# This file contains the logic for generating insights using the Gemini AI model.
# CORRECTED: Using a more robust method to find and load the .env file.

import os
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv # Import find_dotenv
import json

# Use find_dotenv() to reliably locate the .env file
load_dotenv(find_dotenv())
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")
genai.configure(api_key=GEMINI_API_KEY)

# Initialize the generative model
model = genai.GenerativeModel('gemini-1.5-flash')

def build_assessment_prompt(categories_summary: dict, incorrect_answers: list) -> str:
    """Builds a detailed prompt for the AI model to get both feedback and course suggestions."""
    
    prompt = """
    You are an expert career coach. Based on the following Job Readiness Index (JRI) assessment results, provide two things:
    1. A concise, encouraging, and actionable performance report in Markdown format. The report must include these sections: 'Overall Summary', 'Key Strengths', 'Areas for Improvement', and 'Action Plan'.
    2. A list of 3 course suggestions to address the user's weakest areas.

    Here is the user's performance data:
    --- PERFORMANCE BY CATEGORY ---
    """
    
    for category, data in categories_summary.items():
        score = data.get('score', 0)
        total = data.get('total', 0)
        percentage = (score / total * 100) if total > 0 else 0
        prompt += f"- {category}: Scored {score:.1f} out of {total:.1f} ({percentage:.0f}%)\n"
        
    if incorrect_answers:
        prompt += "\n--- INCORRECTLY ANSWERED QUESTIONS ---\n"
        for item in incorrect_answers:
            prompt += f"- Question: {item['question']}\n  - Selected Answer: {item['selected_option']}\n"

    prompt += "\nReturn your response as a single JSON object with two keys: 'performance_report' (a string containing the Markdown report) and 'course_suggestions' (a list of JSON objects, where each object has 'course_name', 'platform', and 'reason' keys)."
    return prompt

async def generate_assessment_feedback(categories_summary: dict, incorrect_answers: list) -> dict:
    """Generates a detailed performance report and course suggestions using the AI model."""
    try:
        prompt = build_assessment_prompt(categories_summary, incorrect_answers)
        response = await model.generate_content_async(prompt)
        # Clean up the response to ensure it's valid JSON
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"Error generating AI feedback: {e}")
        # Return a default error structure
        return {
            "performance_report": "We encountered an error generating your personalized feedback. The AI service may be temporarily unavailable.",
            "course_suggestions": []
        }

async def analyze_resume_text(resume_text: str) -> str:
    """Analyzes the provided resume text and returns feedback in Markdown."""
    prompt = f"""
    You are an expert resume reviewer for tech and business roles. Analyze the following resume text.
    Provide a concise, actionable critique in Markdown format. The report must include these sections:
    'Overall Impression', 'Strengths', 'Areas for Improvement', and 'Top 5 Keywords to Add'.

    --- RESUME TEXT ---
    {resume_text}
    --- END RESUME TEXT ---\n
    Generate the report now.
    """
    try:
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        print(f"Error analyzing resume: {e}")
        return "We encountered an error analyzing your resume. The AI service may be temporarily unavailable."
