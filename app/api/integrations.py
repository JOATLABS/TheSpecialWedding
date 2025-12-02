
import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from app.dependencies.auth import AuthUser, get_current_user
from google_auth_oauthlib.flow import Flow
from app.core.r2 import upload_to_r2
from app.core.database import get_database


router = APIRouter(prefix="/integrations", tags=["Integrations"])

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

@router.get("/gmail/auth")
async def gmail_auth(current_user: AuthUser = Depends(get_current_user)):
    client_config = {
        "web": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": [os.environ.get("GOOGLE_REDIRECT_URI")],
        }
    }
    flow = Flow.from_client_config(
        client_config, scopes=SCOPES,
        redirect_uri=os.environ.get("GOOGLE_REDIRECT_URI"))

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')

    return {'authorization_url': authorization_url}

@router.get("/gmail/callback")
async def gmail_callback(code: str, current_user: AuthUser = Depends(get_current_user)):
    client_config = {
        "web": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": [os.environ.get("GOOGLE_REDIRECT_URI")],
        }
    }
    flow = Flow.from_client_config(
        client_config, scopes=SCOPES,
        redirect_uri=os.environ.get("GOOGLE_REDIRECT_URI"))

    flow.fetch_token(code=code)
    credentials = flow.credentials

    db = await get_database()
    await db.users.update_one(
        {"email": current_user.email},
        {"$set": {
            "google_credentials": {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
            }
        }}
    )

    return {"message": "Gmail authentication successful"}

@router.post("/attachments")
async def handle_attachment(file: UploadFile = File(...), current_user: AuthUser = Depends(get_current_user)):
    file_url = upload_to_r2(file, current_user.email)
    return {"url": file_url}
