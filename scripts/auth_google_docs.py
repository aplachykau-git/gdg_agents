#!/usr/bin/env python3
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]


def main():
    project_root = Path(__file__).resolve().parent.parent
    credentials_file = project_root / "configs" / "credentials.json"
    token_file = project_root / "configs" / "token.json"

    if not credentials_file.exists():
        print(f"❌ Error: {credentials_file} does not exist.")
        sys.exit(1)

    print("🔑 Opening browser for Google Docs & Google Drive authorization...")
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
    creds = flow.run_local_server(port=0)

    token_file.parent.mkdir(parents=True, exist_ok=True)
    with open(token_file, "w") as f:
        f.write(creds.to_json())

    print(f"\n🎉 SUCCESS! Authorized token saved to: {token_file}")


if __name__ == "__main__":
    main()
