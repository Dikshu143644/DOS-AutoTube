"""Upload: YouTube Data API v3 (resumable upload, thumbnail, scheduling, AI-disclosure flag).

Important: videos uploaded through an *unverified* Google Cloud API project are locked to private
by YouTube. Until the project passes Google's audit, upload through YouTube Studio in the browser
(that is what DOS uses today) or keep API uploads private and flip them manually.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def _client():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token = Path(os.environ.get("YOUTUBE_TOKEN_FILE", ".secrets/youtube_token.json"))
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(os.environ.get("YOUTUBE_CLIENT_SECRETS", ".secrets/client_secret.json"), SCOPES)
            creds = flow.run_local_server(port=0)
        token.parent.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(video: Path, meta: dict, thumbnail: Path | None = None, privacy: str = "private",
           publish_at: str | None = None, made_for_kids: bool = False) -> str:
    """Upload one video. publish_at (RFC3339 UTC, e.g. 2026-11-03T14:00:00Z) requires privacy='private'."""
    from googleapiclient.http import MediaFileUpload

    yt = _client()
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": made_for_kids,
              "containsSyntheticMedia": True}  # honest disclosure: AI voice + AI visuals
    if publish_at:
        status.update({"privacyStatus": "private", "publishAt": publish_at})
    body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": meta.get("tags", []),
                        "categoryId": meta.get("category_id", "28"),  # 28 = Science & Technology
                        "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": status}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st:
            print(f"[upload] {int(st.progress() * 100)}%")
    vid = resp["id"]
    if thumbnail:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumbnail))).execute()
    print(json.dumps({"video_id": vid, "url": f"https://youtu.be/{vid}", "status": status}))
    return vid
