import configparser
import os
import smtplib
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import socket
from pathlib import Path

# In-memory storage for progress and logs
progress_data = dict()


# Function to read configuration from config file
def read_config(filename='config.ini'):
    configure = configparser.ConfigParser()
    configure.read(filename)
    return configure


# Email configuration
config = read_config()

smtp_server = config['Email']['smtp_server']
smtp_port = config['Email'].getint('smtp_port')
sender_email = config['Email']['sender_email']
sender_password = config['Email']['sender_password']

# Maximum retry attempts for email sending
MAX_RETRY_ATTEMPTS = 3
RETRY_INTERVAL = 2  # Seconds between retries


def send_email_with_attachment(recipient_email, user_id, filename, matched_file_path):
    """
    Sends an email notification to the user with details about the matched file
    and optionally attaches the PDF if it exists and is accessible. Implements
    a basic retry mechanism with a configurable retry count and interval.

    Args:
        recipient_email (str): User's email address
        user_id (str): User ID
        filename (str): Matched filename containing the user ID
        matched_file_path (str): Full path to the matched file
    """
    attempts = 0
    while attempts < MAX_RETRY_ATTEMPTS:
        try:
            # Validate input for clarity and security
            if not all([recipient_email, user_id, filename]):
                error = "Error: Missing information for email notification."
                return False, error

            # Configure email details
            subject = f"User ID: {user_id} in File: {filename}"
            body = f"Hi {recipient_email},\n\n" \
                   f"Please find the attached file for your reference.\n\n" \
                   f"Regards,\n" \
                   f"Yours Thankfully."

            # Create the message with multipart structure
            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = recipient_email
            message["Subject"] = subject

            # Add the plain text body
            message.attach(MIMEText(body, "plain"))

            # Attach the PDF if provided and accessible
            if matched_file_path and filename.lower().endswith(".pdf") and os.path.isfile(matched_file_path):
                with open(matched_file_path, "rb") as attachment_file:
                    pdf_part = MIMEBase("application", "octet-stream")
                    pdf_part.set_payload(attachment_file.read())
                    encoders.encode_base64(pdf_part)
                    nane = filename.split('_')
                    new_filename = f'{nane[0][:-2]}**_{nane[1]}_{nane[2]}'
                    pdf_part.add_header('Content-Disposition', f'attachment; filename="{new_filename}"')
                    message.attach(pdf_part)
            elif matched_file_path:
                mfp = Path(matched_file_path)
                return False, f"Warning: {mfp.name} is not a PDF file or does not exist."

            # Create a secure connection with SMTP server
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                server.login(sender_email, sender_password)

                # Send the email
                server.sendmail(sender_email, recipient_email, message.as_string())
                error = f"Email notification sent to {recipient_email} for user ID {user_id}."
                return True, error  # Success, exit retry loop

        except (smtplib.SMTPException, FileNotFoundError, socket.gaierror, Exception) as e:
            attempts += 1

            if attempts < MAX_RETRY_ATTEMPTS:
                time.sleep(RETRY_INTERVAL)  # Wait before retrying

            else:
                error = f"Maximum retries ({MAX_RETRY_ATTEMPTS}) reached.\nError sending email notification:\n{str(e)}"
                return False, error

    # End of retry loop
