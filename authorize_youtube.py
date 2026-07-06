import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube"]
HERE = os.path.dirname(__file__)
CLIENT_SECRET = os.path.join(HERE, "client_secret.json")
TOKEN_PATH = os.path.join(HERE, "token.json")

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
creds = flow.run_local_server(port=0, prompt="consent")

with open(TOKEN_PATH, "w", encoding="utf-8") as f:
    f.write(creds.to_json())

print(f"Saved token to {TOKEN_PATH}")
