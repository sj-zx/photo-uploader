from flask import Flask, request, redirect, url_for, session, render_template, jsonify
import os
import uuid
import json
import threading
from dotenv import load_dotenv
import sys

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret_key_for_development')

SCOPES = ['https://www.googleapis.com/auth/drive']

# Global progress tracking
upload_progress = {}

# Runtime-configurable wedding details
def _init_wedding_config():
    # Defaults (can be overridden by CLI args or env)
    default_female = os.getenv('WEDDING_FEMALE_NAME', 'Zi Xun')
    default_male = os.getenv('WEDDING_MALE_NAME', 'Shao Jie')
    default_date = os.getenv('WEDDING_DATE', '19 October 2025')
    default_place = os.getenv('WEDDING_PLACE', 'Peach Garden @ Heeren')

    female, male, date, place = default_female, default_male, default_date, default_place

    # Support invocation: python app.py female_name male_name date place
    # Keep server flags unaffected when running under gunicorn
    if __name__ == "__main__":
        args = sys.argv[1:]
        if len(args) >= 4:
            female, male, date, place = args[0], args[1], args[2], ' '.join(args[3:])

    app.config.update({
        'BRIDE_NAME': female,
        'GROOM_NAME': male,
        'WEDDING_DATE': date,
        'WEDDING_PLACE': place,
    })

_init_wedding_config()

@app.context_processor
def inject_wedding_details():
    return dict(
        bride_name=app.config.get('BRIDE_NAME'),
        groom_name=app.config.get('GROOM_NAME'),
        wedding_date=app.config.get('WEDDING_DATE'),
        wedding_place=app.config.get('WEDDING_PLACE'),
    )

def get_client_config():
    """Get OAuth2 client configuration from environment variables"""
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables must be set")
    
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": [os.getenv('REDIRECT_URI', 'http://localhost:5000/oauth2callback')]
        }
    }

def get_credentials_from_env():
    """Get credentials from environment variables"""
    refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    if refresh_token and client_id and client_secret:
        return Credentials(
            token=None,  # Will be refreshed automatically
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES
        )
    return None

def get_valid_credentials():
    """Get valid credentials from environment variables"""
    print("🔍 Checking for valid credentials...")
    
    # Try to get credentials from environment variables
    creds = get_credentials_from_env()
    if creds:
        print("✅ Found credentials in environment variables")
        # Refresh the token to get a fresh access token
        try:
            creds.refresh(Request())
            print("✅ Successfully refreshed access token")
            return creds
        except Exception as e:
            print(f"❌ Error refreshing token: {e}")
    
    # Fall back to session credentials (for first-time setup)
    if 'credentials' in session:
        try:
            print("📋 Found credentials in session")
            creds = Credentials(**session['credentials'])
            print("✅ Using session credentials")
            return creds
        except Exception as e:
            print(f"❌ Error loading session credentials: {e}")
    
    print("❌ No valid credentials found")
    return None

# Main page with upload form
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        print("📤 Upload request received")
        
        # Check if we have valid credentials
        creds = get_valid_credentials()
        if not creds:
            print("🔐 No valid credentials - redirecting to auth")
            # Store the intended action in session and redirect to auth
            session['pending_upload'] = True
            return redirect(url_for('authorize'))

        print("✅ Using credentials for upload")
        service = build('drive', 'v3', credentials=creds)

        name = request.form.get("name", "").strip()
        files = request.files.getlist("photos")

        # Filter out empty files
        files = [f for f in files if f and f.filename and f.filename.strip()]
        
        if not files:
            return "No files selected for upload", 400

        print(f"📁 Uploading {len(files)} files for user: {name or 'Unnamed'}")

        # Create or get main folder
        main_folder_id = get_or_create_folder(service, "WeddingPhotos")

        # Folder per user or "Unnamed"
        folder_name = name if name else "Unnamed"
        folder_id = get_or_create_folder(service, folder_name, main_folder_id)

        uploaded_files = []
        for f in files:
            temp_filename = f"{uuid.uuid4()}_{f.filename}"
            f.save(temp_filename)
            media = MediaFileUpload(temp_filename, resumable=True)
            
            file_metadata = {
                'name': f.filename,
                'parents': [folder_id]
            }
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name'
            ).execute()
            
            uploaded_files.append(file.get('name'))
            os.remove(temp_filename)

        print(f"✅ Successfully uploaded {len(uploaded_files)} files")

        return redirect(url_for("success"))

    return render_template("index.html")

# Progress tracking endpoint
@app.route('/upload-progress/<upload_id>')
def get_upload_progress(upload_id):
    if upload_id in upload_progress:
        return jsonify(upload_progress[upload_id])
    return jsonify({'error': 'Upload not found'}), 404

# Upload endpoint with progress tracking
@app.route('/upload', methods=['POST'])
def upload_with_progress():
    print("📤 Upload request received")
    
    # Check if we have valid credentials
    creds = get_valid_credentials()
    if not creds:
        print("🔐 No valid credentials - redirecting to auth")
        return jsonify({'error': 'Authentication required'}), 401

    print("✅ Using credentials for upload")
    service = build('drive', 'v3', credentials=creds)

    name = request.form.get("name", "").strip()
    files = request.files.getlist("photos")

    # Filter out empty files
    files = [f for f in files if f and f.filename and f.filename.strip()]
    
    if not files:
        return jsonify({'error': 'No files selected'}), 400

    print(f"📁 Uploading {len(files)} files for user: {name or 'Unnamed'}")

    # Generate upload ID for progress tracking
    upload_id = str(uuid.uuid4())
    upload_progress[upload_id] = {
        'status': 'starting',
        'current_file': 0,
        'total_files': len(files),
        'percentage': 0,
        'message': 'Getting ready...',
        'uploaded_files': []
    }

    # Save files to temporary storage before background processing
    temp_files = []
    for f in files:
        temp_filename = f"{uuid.uuid4()}_{f.filename}"
        f.save(temp_filename)
        temp_files.append({
            'temp_path': temp_filename,
            'original_name': f.filename
        })

    def upload_files():
        try:
            # Create or get main folder
            main_folder_id = get_or_create_folder(service, "WeddingPhotos")
            
            # Folder per user or "Unnamed"
            folder_name = name if name else "Unnamed"
            folder_id = get_or_create_folder(service, folder_name, main_folder_id)

            # Compute total bytes for accurate progress
            total_bytes = 0
            for file_info in temp_files:
                try:
                    total_bytes += os.path.getsize(file_info['temp_path'])
                except Exception:
                    pass

            uploaded_files = []
            bytes_uploaded_so_far = 0
            for i, file_info in enumerate(temp_files):
                try:
                    upload_progress[upload_id].update({
                        'status': 'uploading',
                        'current_file': i + 1,
                        'percentage': int(((i + 1) / len(temp_files)) * 100),
                        'message': f'{i + 1}/{len(temp_files)} photo loading...'
                    })
                    file_size = 0
                    try:
                        file_size = os.path.getsize(file_info['temp_path'])
                    except Exception:
                        pass

                    media = MediaFileUpload(file_info['temp_path'], resumable=True)
                    
                    file_metadata = {
                        'name': file_info['original_name'],
                        'parents': [folder_id]
                    }
                    request_upload = service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id,name'
                    )

                    response = None
                    last_reported_percentage = -1
                    while response is None:
                        status, response = request_upload.next_chunk()
                        if status is not None:
                            # status.progress() returns 0..1
                            current_file_bytes = int((status.progress() or 0) * file_size)
                            overall = 0
                            if total_bytes > 0:
                                overall = int(((bytes_uploaded_so_far + current_file_bytes) / total_bytes) * 100)
                            # Avoid spamming updates if same percent
                            if overall != last_reported_percentage:
                                upload_progress[upload_id].update({
                                    'status': 'uploading',
                                    'current_file': i + 1,
                                    'percentage': int(((i + 1) / len(temp_files)) * 100),
                                    'message': f'{i + 1}/{len(temp_files)} photo loading...'
                                })
                                last_reported_percentage = overall

                    # Completed this file
                    bytes_uploaded_so_far += file_size

                    file = response or {}
                    uploaded_files.append(file.get('name'))
                    upload_progress[upload_id]['uploaded_files'].append(file.get('name'))
                    
                    # Clean up temp file
                    try:
                        os.remove(file_info['temp_path'])
                    except:
                        pass  # Ignore cleanup errors
                    
                except Exception as e:
                    print(f"❌ Error uploading {file_info['original_name']}: {e}")
                    upload_progress[upload_id].update({
                        'status': 'error',
                        'message': f'Could not load: {file_info["original_name"]}'
                    })
                    # Clean up temp file on error
                    try:
                        os.remove(file_info['temp_path'])
                    except:
                        pass
                    return

            # Update final progress
            upload_progress[upload_id].update({
                'status': 'completed',
                'percentage': 100,
                'message': 'completed!'
            })

            print(f"✅ Successfully uploaded {len(uploaded_files)} files")

        except Exception as e:
            print(f"❌ Upload error: {e}")
            upload_progress[upload_id].update({
                'status': 'error',
                'message': f'Loading error: {str(e)}'
            })
        finally:
            # Clean up any remaining temp files
            for file_info in temp_files:
                try:
                    if os.path.exists(file_info['temp_path']):
                        os.remove(file_info['temp_path'])
                except:
                    pass

    # Start upload in background thread
    thread = threading.Thread(target=upload_files)
    thread.start()

    return jsonify({'upload_id': upload_id})

# Upload audio endpoint with progress tracking
@app.route('/upload-audio', methods=['POST'])
def upload_audio_with_progress():
    print("🎙️ Audio upload request received")
    creds = get_valid_credentials()
    if not creds:
        return jsonify({'error': 'Authentication required'}), 401

    service = build('drive', 'v3', credentials=creds)

    name = request.form.get('name', '').strip()
    audio = request.files.get('audio')
    if not audio or not audio.filename:
        return jsonify({'error': 'No audio provided'}), 400

    upload_id = str(uuid.uuid4())
    upload_progress[upload_id] = {
        'status': 'starting',
        'current_file': 0,
        'total_files': 1,
        'percentage': 0,
        'message': 'Getting ready...',
        'uploaded_files': []
    }

# Google OAuth2 authorization start (only for first-time setup)
@app.route('/authorize')
def authorize():
    client_config = get_client_config()
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # This ensures we get a refresh token
    )
    session['state'] = state
    return redirect(authorization_url)

# OAuth2 callback endpoint (only for first-time setup)
@app.route('/oauth2callback')
def oauth2callback():
    state = session.get('state', None)
    client_config = get_client_config()
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    creds = flow.credentials
    
    # Save to session temporarily
    session['credentials'] = creds_to_dict(creds)
    
    # Clear pending upload flag
    session.pop('pending_upload', None)

    return redirect(url_for('index'))

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/debug/auth')
def debug_auth():
    """Debug endpoint to check authentication status"""
    creds = get_valid_credentials()
    if creds:
        return {
            'authenticated': True,
            'expired': creds.expired,
            'has_refresh_token': bool(creds.refresh_token),
            'token_expiry': str(creds.expiry) if creds.expiry else None
        }
    else:
        return {
            'authenticated': False,
            'session_has_credentials': 'credentials' in session
        }

# Helpers
def get_or_create_folder(service, folder_name, parent_id=None):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, fields="files(id)").execute()
    items = results.get('files', [])
    if items:
        return items[0]['id']

    folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    if parent_id:
        folder_metadata['parents'] = [parent_id]
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    return folder.get('id')

def creds_to_dict(creds):
    return {'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes}

if __name__ == "__main__":
    app.run('localhost', 5000, debug=True)
