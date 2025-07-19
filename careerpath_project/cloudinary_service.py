# cloudinary_service.py
# Handles file uploads to Cloudinary.

import os
import cloudinary
import cloudinary.uploader

def configure_cloudinary():
    """
    Configures the Cloudinary SDK using credentials from environment variables.
    """
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    api_secret = os.getenv('CLOUDINARY_API_SECRET')

    if not all([cloud_name, api_key, api_secret]):
        print("--- CLOUDINARY ERROR: Missing Cloudinary environment variables. ---")
        return False
    
    try:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True  # Ensures URLs are HTTPS
        )
        print("--- Cloudinary configured successfully. ---")
        return True
    except Exception as e:
        print(f"--- CLOUDINARY ERROR: Failed to configure Cloudinary: {e} ---")
        return False

# Configure Cloudinary when the module is first imported
IS_CONFIGURED = configure_cloudinary()

def upload_file_to_cloudinary(filename: str, file_contents: bytes, mimetype: str):
    """
    Uploads a file to a specific Cloudinary folder.
    For PDFs and DOCX, we must specify the resource_type as 'raw'.
    """
    if not IS_CONFIGURED:
        raise Exception("Cloudinary service is not configured.")

    try:
        # For non-image files like PDF, DOCX, etc., use resource_type='raw'
        # We can also specify a folder to keep things organized.
        upload_result = cloudinary.uploader.upload(
            file_contents,
            public_id=filename,
            folder="resumes",  # This will create a 'resumes' folder in your Cloudinary account
            resource_type="raw"
        )
        
        # The secure_url is the public URL to access the file
        file_url = upload_result.get('secure_url')
        print(f"--- CLOUDINARY SUCCESS: File '{filename}' uploaded. URL: {file_url} ---")
        return file_url

    except Exception as e:
        print(f"--- CLOUDINARY ERROR: An error occurred during upload: {e} ---")
        raise Exception(f"An error occurred during Cloudinary upload: {e}")

