import os
from pathlib import Path

import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_google_credentials():
    """
    Returns Google credentials for Drive/Docs API access.

    Controlled by GOOGLE_AUTH_METHOD env var:
      auto            - tries oauth → service_account → adc (default)
      oauth           - token.json only; errors if missing/invalid
      service_account - service_account.json only; errors if missing
      adc             - Application Default Credentials only (Cloud Run / gcloud ADC)
    """
    method = os.getenv("GOOGLE_AUTH_METHOD", "auto").lower()

    if method in ("auto", "oauth"):
        creds = _try_oauth_token()
        if creds:
            return creds
        if method == "oauth":
            raise RuntimeError(
                "GOOGLE_AUTH_METHOD=oauth but no valid token.json found. Run scripts/auth_google_docs.py first."
            )

    if method in ("auto", "service_account"):
        creds = _try_service_account()
        if creds:
            return creds
        if method == "service_account":
            raise RuntimeError(
                "GOOGLE_AUTH_METHOD=service_account but no service_account.json found in configs/ or project root."
            )

    credentials, _ = google.auth.default(scopes=SCOPES)
    return credentials


def _try_oauth_token():
    for candidate in [
        _PROJECT_ROOT / "configs" / "token.json",
        _PROJECT_ROOT / "token.json",
    ]:
        if candidate.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(candidate), SCOPES)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    candidate.write_text(creds.to_json())
                if creds and creds.valid:
                    return creds
            except Exception as err:
                print(f"Notice: OAuth token load failed ({candidate}): {err}")
    return None


def _try_service_account():
    for candidate in [
        _PROJECT_ROOT / "configs" / "service_account.json",
        _PROJECT_ROOT / "service_account.json",
    ]:
        if candidate.exists():
            try:
                return service_account.Credentials.from_service_account_file(str(candidate), scopes=SCOPES)
            except Exception as err:
                print(f"Notice: Service account load failed ({candidate}): {err}")
    return None
