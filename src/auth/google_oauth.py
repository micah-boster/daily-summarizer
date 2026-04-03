"""Google OAuth2 token management for Calendar and Gmail API access.

Handles token load/refresh/save cycle and initial interactive auth flow.
Credentials are stored in .credentials/token.json (gitignored).
"""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

CREDENTIALS_DIR = Path(".credentials")
TOKEN_PATH = CREDENTIALS_DIR / "token.json"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"


def load_credentials() -> Credentials | None:
    """Load credentials from token file, refresh if expired.

    Returns None if no token exists, token is invalid and cannot be refreshed,
    or refresh fails (e.g., revoked token, expired refresh token).
    """
    if not TOKEN_PATH.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return creds
        except Exception:
            # Refresh failed -- token revoked or expired beyond refresh
            return None

    return None


def save_credentials(creds: Credentials) -> None:
    """Persist credentials to token file. Creates .credentials/ dir if needed."""
    CREDENTIALS_DIR.mkdir(exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())


def run_initial_auth() -> Credentials:
    """Run interactive OAuth flow (first time or re-auth).

    Opens a browser for Google sign-in. Uses access_type='offline' and
    prompt='consent' to ensure a refresh token is always returned,
    even on subsequent authorizations.
    """
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH),
        SCOPES,
    )
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )
    save_credentials(creds)
    return creds


if __name__ == "__main__":
    credentials = load_credentials()
    if credentials:
        print(f"Credentials loaded. Expiry: {credentials.expiry}")
        print(f"Scopes: {credentials.scopes}")
    else:
        print("No valid credentials found. Running OAuth flow...")
        credentials = run_initial_auth()
        print(f"Credentials saved. Expiry: {credentials.expiry}")
        print(f"Scopes: {credentials.scopes}")
