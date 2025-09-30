# Wedding Photo Upload App

A simple web application to effortlessly collect wedding photos from your guests.

Instead of chasing down everyone after the big day, deploy this app and generate a QR code linked to your upload page. Place the QR code on each table at your wedding—guests can instantly upload their photos, sending cherished memories directly to your Google Drive.

No more missing moments. Just scan, upload, and relive your special day!

## Features

- 📸 Photo upload with preview and selection
- 🎨 Beautiful, responsive design
- 🔐 Google Drive integration for secure storage
- 📱 Mobile-friendly interface

## Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd wedding-photos
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   - Create a `.env` file in the project root
   - Add the following environment variables:
     ```
     SECRET_KEY=your_super_secret_key_here
     GOOGLE_CLIENT_ID=your_google_client_id_here
     GOOGLE_CLIENT_SECRET=your_google_client_secret_here
     GOOGLE_REFRESH_TOKEN=your_refresh_token_here
     ```
   ### Optional (defaults to http://localhost:5000/oauth2callback)
   ```
   REDIRECT_URI=http://localhost:5000/oauth2callback
   FLASK_ENV=development
   FLASK_DEBUG=True
     ```

4. **Set up Google OAuth**
   - Create a Google Cloud Project
   - Enable "Google Drive API"
   - Create OAuth 2.0 credentials (Web application type)
   - Download the OAuth client JSON as `drive_credentials.json`
   - Add redirect URI: `http://localhost:5000/oauth2callback`

5. **Generate a refresh token (one-time)**
    - Place `drive_credentials.json` in the project root
    - Run:
       ```bash
       python3 drive_helper.py
       ```
    - Complete the Google login; this will:
       - Save `owner_credentials.json` locally
       - Print `GOOGLE_REFRESH_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
    - Copy those values into your `.env`

6. **Run the application**
   ```bash
   # Default (values can be customized via CLI args or env vars)
   python app.py

   # Optional: run with names/date/place
   python app.py "Gül" "Fatih" "30 Ağustos 2025" "İstanbul, Türkiye"
   ```

## Deployment to Render

1. **Push your code to GitHub**

2. **Connect to Render**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository

3. **Configure the service**
   - **Name**: `wedding-photos` (or your preferred name)
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

4. **Set environment variables in Render**
   - `SECRET_KEY`: Generate a secure random string
   - `GOOGLE_CLIENT_ID`: Your Google OAuth Client ID
   - `GOOGLE_CLIENT_SECRET`: Your Google OAuth Client Secret
   - `GOOGLE_REFRESH_TOKEN`: Your Google OAuth Refresh Token
   - `FLASK_ENV`: `production`
   - `FLASK_DEBUG`: `false`

5. **Update Google OAuth redirect URI (Render)**
   - Add your Render URL to Google Cloud Console
   - Format: `https://your-app-name.onrender.com/oauth2callback`

6. **No Google login on Render**
   - After setting the env vars above (from your local `drive_helper.py` run), guests can upload photos without logging in.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key for sessions | Yes |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | Yes |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | Yes |
| `GOOGLE_REFRESH_TOKEN` | Google OAuth Refresh Token | Yes |
| `REDIRECT_URI` | OAuth redirect URI override (optional) | No |
| `FLASK_ENV` | Flask environment (development/production) | No |
| `FLASK_DEBUG` | Enable Flask debug mode | No |

## File Structure

```
wedding-photos/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables (not in git)
├── .gitignore           # Git ignore rules
├── render.yaml          # Render deployment config
├── drive_helper.py       # One-time script to get refresh token
├── drive_credentials.json # OAuth client JSON (do not commit)
├── owner_credentials.json # Owner's Google credentials (not in git)
├── static/
│   └── logo.png         # App logo
└── templates/
    ├── index.html       # Main upload page
    └── success.html     # Success page
```

## Security Notes

- Never commit `.env` or `owner_credentials.json` to version control
- Never commit OAuth client JSON (e.g., `drive_credentials.json`)
- Use strong, randomly generated `SECRET_KEY` in production
- Keep your Google OAuth credentials secure
- Regularly rotate your OAuth credentials
- Store sensitive environment variables securely in production
- The app stores your Google credentials locally - keep the server secure

## License

This project is for personal use only.

It is designed initially for weddings, but can be altered to be used in any kind of event.

Feel free to contact for questions: [mfteloglu@gmail.com](mailto:mfteloglu@gmail.com)