import os
import gspread
from typing import List
from django.conf import settings
import requests
import base64

def initialize_gspread() -> gspread.client.Client:
    """
    Initialize a gspread client with the given credentials.
    """
    return gspread.service_account_from_dict(get_credentials())  # Note: we could move this to settings to do this once.


def get_credentials() -> dict:
    """
    Return gspread credentials.
    """
    creds = {
        "type": os.getenv("TYPE"),
        "project_id": os.getenv("PROJECT_ID"),
        "private_key_id": os.getenv("PRIVATE_KEY_ID"),
        "private_key": os.getenv("PRIVATE_KEY"),
        "client_email": os.getenv("CLIENT_EMAIL"),
        "client_id": os.getenv("CLIENT_ID"),
        "auth_uri": os.getenv("AUTH_URI"),
        "token_uri": os.getenv("TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL"),
        "universe_domain": os.getenv("UNIVERSE_DOMAIN")
    }
    return creds


def get_worksheet(doc_name: str, sheet_name: str = None):
    sh = settings.GSPREAD_CLIENT.open(doc_name)
    worksheet = sh.worksheet(sheet_name) if sheet_name else sh.get_worksheet(0)
    return worksheet


def get_all_rows(doc_name: str, sheet_name: str = None) -> List[dict]:
    """
    Fetches all rows from a given Google Sheet worksheet.
    """
    worksheet = get_worksheet(doc_name, sheet_name)
    return worksheet.get_all_records()


def imgur_delete(delete_hash):
    # Set the Imgur's Client ID
    authorization_header = f"Client-ID {os.getenv('IMGUR_CLIENT_ID')}"
    headers = {
        'Authorization': authorization_header
    }
    try:
        delete = requests.delete(f'https://api.imgur.com/3/image/{delete_hash}', headers=headers)
    except:
        pass


def imgur_upload(image, delete_hash):
    # Set the Imgur's Client ID
    authorization_header = f"Client-ID {os.getenv('IMGUR_CLIENT_ID')}"

    try:
        # Read the file content into a byte array
        file_bytes = image.read()

        # Convert the byte array to a base64-encoded string
        base64_string = base64.b64encode(file_bytes).decode('utf-8')

        # Prepare the data for the request
        data = {
            'image': base64_string
        }

        # Set the headers for the request
        headers = {
            'Authorization': authorization_header
        }

        # Send request to Imgur
        response = requests.post('https://api.imgur.com/3/image', data=data, headers=headers)

        # Handle the response
        response_json = response.json()

        # Handle the response
        if 'status' in response_json and response_json['status'] == 200:
            # The upload was successful
            imgur_delete(delete_hash)

            return {
                'success': True,
                'data': response_json['data']
            }
        else:
            # There was an error
            error_message = response_json['data']['error']
            return {
                'success': False,
                'error': f"Error: {error_message}"
            }

    except Exception as e:
        # Handle any other errors that might occur
        return {
            'success': False,
            'error': f"An unexpected error occurred: {str(e)}"
        }