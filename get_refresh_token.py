# get_refresh_token.py
# FINAL VERSION: Includes a fix for the InsecureTransportError.

import os
from google_auth_oauthlib.flow import Flow

# --- FIX for InsecureTransportError ---
# This line tells the library to allow an http:// redirect for localhost.
# It is safe to use for this one-time script.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
# ------------------------------------

SCOPES = ['https://www.googleapis.com/auth/drive']
flow = Flow.from_client_secrets_file(
    'client_secret.json',
    scopes=SCOPES,
    redirect_uri='http://localhost:8080'
)

auth_url, _ = flow.authorization_url(prompt='consent')

print('Please go to this URL and authorize the app:')
print(auth_url)
print()

code = input('Enter the full callback URL you were redirected to (it starts with http://localhost:8080/): ')

# Paste the full URL from your browser's address bar after you see the error page.
flow.fetch_token(authorization_response=code)

credentials = flow.credentials
print("\nSUCCESS! Your refresh token is:\n")
print(credentials.refresh_token)
print("\nCopy this token and add it to your .env file as GOOGLE_REFRESH_TOKEN")

