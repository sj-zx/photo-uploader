from google_auth_oauthlib.flow import InstalledAppFlow
import json
import os

# Define the scope you need (Drive read/write)
SCOPES = ['https://www.googleapis.com/auth/drive']

# Load your client_id/client_secret file
CLIENT_SECRETS_FILE = 'drive_credentials.json'
if not os.path.exists(CLIENT_SECRETS_FILE):
    raise FileNotFoundError(
        f"{CLIENT_SECRETS_FILE} not found. Place your OAuth client JSON as '{CLIENT_SECRETS_FILE}' in the project root.")

flow = InstalledAppFlow.from_client_secrets_file(
    CLIENT_SECRETS_FILE, SCOPES)

# Run local server flow (will open browser to login)
creds = flow.run_local_server(port=8080, prompt="consent")

# Save as owner_credentials.json
with open('owner_credentials.json', 'w') as f:
    f.write(creds.to_json())

print("✅ Saved owner_credentials.json with refresh_token!")

# Also print env vars to copy/paste
data = json.loads(creds.to_json())
refresh_token = data.get('refresh_token')
client_id = data.get('client_id')
client_secret = data.get('client_secret')

print("\n🔑 Copy these environment variables:")
print("=" * 50)
if refresh_token:
    print(f"GOOGLE_REFRESH_TOKEN={refresh_token}")
else:
    print("GOOGLE_REFRESH_TOKEN=<! no refresh_token found — re-run with prompt='consent' and ensure access_type='offline' !>")
print(f"GOOGLE_CLIENT_ID={client_id}")
print(f"GOOGLE_CLIENT_SECRET={client_secret}")
print("=" * 50)
print("📝 Add these to your .env (local) or Render environment variables (production).")
