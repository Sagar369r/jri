# gdrive_service.py
# FIXED: Improved credential refresh logic and error handling.

import os
import io
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
CLIENT_SECRET_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_credentials():
    """
    Creates and returns Google API credentials using the client secrets file
    and the stored refresh token.
    """
    if not all([CLIENT_SECRET_FILE, REFRESH_TOKEN]):
        raise ValueError("Google OAuth credentials (client secret file or refresh token) are not set.")

    creds = None
    
    try:
        # Load the client secrets from the file downloaded from Google Cloud Console.
        with open(CLIENT_SECRET_FILE, 'r') as f:
            client_config = json.load(f).get("web") or json.load(f).get("installed")

        # Create a credentials object by combining the client secrets with the refresh token.
        creds = Credentials(
            token=None,  # No initial access token needed, it will be fetched.
            refresh_token=REFRESH_TOKEN,
            token_uri=client_config["token_uri"],
            client_id=client_config["client_id"],
            client_secret=client_config["client_secret"],
            scopes=SCOPES
        )
        
        # --- NEW: Directly refresh the credentials to get a valid access token. ---
        # This is a more direct and robust way to handle the initial token fetch.
        creds.refresh(Request())

    except FileNotFoundError:
        raise ValueError(f"Client secret file not found at: {CLIENT_SECRET_FILE}")
    except (KeyError, TypeError, json.JSONDecodeError):
        raise ValueError("Invalid client_secret.json file format.")
    except Exception as e:
        # This will catch specific errors from the creds.refresh() call.
        print(f"Failed to refresh token. The refresh token is likely invalid or revoked. Error: {e}")
        raise ValueError("Could not refresh credentials. The refresh token might be invalid.")
            
    return creds

def upload_file_to_drive(filename: str, file_content: bytes, content_type: str):
    """Uploads a file to the specified Google Drive folder."""
    if not FOLDER_ID:
        raise ValueError("GOOGLE_DRIVE_FOLDER_ID is not set.")

    try:
        creds = get_credentials()
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': filename,
            'parents': [FOLDER_ID]
        }
        
        media = io.BytesIO(file_content)
        media_body = MediaIoBaseUpload(media, mimetype=content_type, resumable=True)
        
        file = service.files().create(
            body=file_metadata,
            media_body=media_body,
            fields='id'
        ).execute()

        print(f"--- GDRIVE: Successfully uploaded '{filename}' with File ID: {file.get('id')} ---")
        return file.get('id')

    except Exception as e:
        print(f"--- GDRIVE ERROR: An error occurred: {e} ---")
        # Re-raise the exception so the main app knows something went wrong.
        raise e