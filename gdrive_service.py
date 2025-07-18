# gdrive_service.py (Updated for Railway Deployment)
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
# Reads the JSON content directly from the environment variable
GOOGLE_CLIENT_SECRET_JSON = os.getenv("GOOGLE_CLIENT_SECRET_JSON") 
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_credentials():
    """
    Creates Google API credentials from environment variables.
    """
    if not all([GOOGLE_CLIENT_SECRET_JSON, REFRESH_TOKEN]):
        raise ValueError("Google OAuth credentials are not fully set in environment variables.")

    try:
        # Load the client secrets directly from the environment variable string
        client_config_dict = json.loads(GOOGLE_CLIENT_SECRET_JSON)
        client_config = client_config_dict.get("web") or client_config_dict.get("installed")

        # Create a credentials object by combining the client secrets with the refresh token
        creds = Credentials(
            token=None,
            refresh_token=REFRESH_TOKEN,
            token_uri=client_config["token_uri"],
            client_id=client_config["client_id"],
            client_secret=client_config["client_secret"],
            scopes=SCOPES
        )
        
        # Refresh the credentials to get a valid access token
        creds.refresh(Request())
        return creds

    except (json.JSONDecodeError, KeyError, TypeError):
        raise ValueError("Invalid format for GOOGLE_CLIENT_SECRET_JSON variable.")
    except Exception as e:
        print(f"Failed to refresh token. The refresh token is likely invalid or revoked. Error: {e}")
        raise ValueError("Could not refresh credentials.")
            
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
        # Re-raise the exception so the main app knows something went wrong
        raise e
