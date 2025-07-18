# user_logger.py
# This new service handles logging user data to a CSV file.

import csv
from datetime import datetime
import os

# The name of the log file.
LOG_FILE = 'user_log.csv'

def log_user_email(email: str):
    """
    Appends a user's email and a timestamp to the log file.
    Creates the file with headers if it doesn't exist.
    """
    # Check if the file exists to determine if we need to write headers.
    file_exists = os.path.isfile(LOG_FILE)
    
    try:
        # Open the file in 'append' mode. 'newline=""' prevents extra blank rows.
        with open(LOG_FILE, 'a', newline='') as csvfile:
            # Define the column headers.
            fieldnames = ['email', 'timestamp']
            
            # Create a writer object that will format the data as a CSV row.
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # If the file is new, write the header row first.
            if not file_exists:
                writer.writeheader()
            
            # Write the user's data.
            writer.writerow({
                'email': email,
                'timestamp': datetime.now().isoformat()
            })
        print(f"--- LOGGER: Successfully logged email: {email} ---")
    except Exception as e:
        print(f"--- LOGGER: FAILED to log email {email}. Error: {e} ---")

