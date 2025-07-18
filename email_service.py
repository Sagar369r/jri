# email_service.py
# This service now sends real emails using the Brevo API.

import os
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file
load_dotenv(find_dotenv())

# --- Configuration ---
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:8001") 

# --- Brevo API Setup ---
configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = BREVO_API_KEY
api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

def send_magic_link(email: str, token: str):
    """
    Constructs and sends a magic link email using the Brevo API.
    """
    if not BREVO_API_KEY or not SENDER_EMAIL:
        print("--- EMAIL ERROR: BREVO_API_KEY or SENDER_EMAIL not set. ---")
        return False

    magic_link = f"{FRONTEND_URL}/?token={token}"
    
    html_content = f"""
    <html><body><div style="font-family: sans-serif; text-align: center; padding: 20px;">
        <h2>Welcome to JRI Career World!</h2>
        <p>Click the button below to securely log in to your account.</p>
        <p>This link will expire in 15 minutes and can only be used once.</p>
        <a href="{magic_link}" style="background-color: #5a8bd1; color: white; padding: 15px 25px; text-decoration: none; border-radius: 5px; font-size: 16px; display: inline-block;">Log In</a>
        <p style="margin-top: 20px; font-size: 12px; color: #888;">If you did not request this email, you can safely ignore it.</p>
    </div></body></html>
    """

    sender = {"name": "JRI Career World", "email": SENDER_EMAIL}
    to = [{"email": email}]
    
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=to,
        sender=sender,
        subject="Your Magic Link to JRI Career World",
        html_content=html_content
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        print(f"--- EMAIL: Magic link sent to {email}. Response: {api_response} ---")
        return True
    except ApiException as e:
        print(f"--- EMAIL ERROR: Failed to send magic link to {email}. Error: {e} ---")
        return False

def send_assessment_report(email: str, report_markdown: str, score: float):
    """
    Sends the user their assessment report via email using the Brevo API.
    """
    if not BREVO_API_KEY or not SENDER_EMAIL:
        print("--- EMAIL ERROR: BREVO_API_KEY or SENDER_EMAIL not set. ---")
        return False
        
    html_content = f"""
    <html><body><div style="font-family: sans-serif; padding: 20px;">
        <h2>Your JRI Career World Quest Results!</h2>
        <p>Hello Player!</p>
        <p>You completed your quest and earned <strong>{score} EXP!</strong></p>
        <p>Here is your detailed performance report:</p>
        <pre style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; white-space: pre-wrap; font-family: monospace;">{report_markdown}</pre>
        <p>Keep leveling up your skills!</p>
    </div></body></html>
    """

    sender = {"name": "JRI Career World", "email": SENDER_EMAIL}
    to = [{"email": email}]

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=to,
        sender=sender,
        subject="Your JRI Assessment Report",
        html_content=html_content
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        print(f"--- EMAIL: Assessment report sent to {email}. Response: {api_response} ---")
        return True
    except ApiException as e:
        print(f"--- EMAIL ERROR: Failed to send report to {email}. Error: {e} ---")
        return False
