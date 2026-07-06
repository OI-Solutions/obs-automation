import json
import os
import time
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

HERE = os.path.dirname(__file__)
TOKEN_PATH = os.path.join(HERE, "token.json")
STATE_PATH = os.path.join(HERE, "current_broadcast.json")
SCOPES = ["https://www.googleapis.com/auth/youtube"]


def get_client():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def get_persistent_stream_id(youtube, obs_key):
    streams = youtube.liveStreams().list(part="id,cdn", mine=True, maxResults=25).execute()
    items = streams.get("items", [])
    for s in items:
        if s["cdn"].get("ingestionInfo", {}).get("streamName") == obs_key:
            return s["id"]
    if len(items) == 1:
        return items[0]["id"]
    raise RuntimeError("Could not find a persistent YouTube stream key matching OBS's configured key")


def create_and_bind_broadcast(youtube, stream_id, title):
    now = datetime.now(timezone.utc).isoformat()
    body = {
        "snippet": {
            "title": title,
            "scheduledStartTime": now,
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
        "contentDetails": {
            "enableAutoStart": False,
            "enableAutoStop": False,
            "monitorStream": {
                "enableMonitorStream": False,
            },
        },
    }
    broadcast = youtube.liveBroadcasts().insert(
        part="id,snippet,status,contentDetails", body=body
    ).execute()
    broadcast_id = broadcast["id"]
    youtube.liveBroadcasts().bind(
        id=broadcast_id, part="id,contentDetails", streamId=stream_id
    ).execute()
    return broadcast_id


def wait_for_active_stream(youtube, stream_id, timeout=90, interval=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = youtube.liveStreams().list(part="status", id=stream_id).execute()
        items = s.get("items", [])
        if items and items[0]["status"]["streamStatus"] == "active":
            return True
        time.sleep(interval)
    return False


def transition(youtube, broadcast_id, status):
    youtube.liveBroadcasts().transition(
        broadcastStatus=status, id=broadcast_id, part="id,status"
    ).execute()


def save_state(broadcast_id, stream_id):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"broadcast_id": broadcast_id, "stream_id": stream_id}, f)


def load_state():
    if not os.path.exists(STATE_PATH):
        return None
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def clear_state():
    if os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)
