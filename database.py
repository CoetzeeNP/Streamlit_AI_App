import requests
import json
import logging
import streamlit as st
from datetime import datetime
import google.auth.transport.requests
from google.oauth2 import service_account

logger = logging.getLogger("firebase")

SCOPES = [
    "https://www.googleapis.com/auth/firebase.database",
    "https://www.googleapis.com/auth/userinfo.email"
]

@st.cache_resource
def get_db_session():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    base_url = st.secrets["firebase_db_url"].rstrip('/')
    service_account_info = dict(st.secrets["firebase_service_account"])
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    return session, base_url, credentials

def _get_token(credentials):
    if not credentials.valid:
        credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token

def _firebase_patch(session, url, credentials, data: dict):
    try:
        token = _get_token(credentials)
        with session.patch(
            url,
            data=json.dumps(data),
            headers={"Authorization": f"Bearer {token}"},
            stream=True
        ) as response:
            logger.info(f"Firebase PATCH {response.status_code} → {url}")
            response.close()
    except Exception as e:
        logger.error(f"Firebase REST Error: {e}")

def save_to_firebase(user_id, model_name, messages, interaction_type, session_id, feedback_value=None):
    session, base_url, credentials = get_db_session()
    clean_uid = str(user_id).replace(".", "_")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_index = len(messages) - 1

    url = f"{base_url}/logs/{clean_uid}/{session_id}.json"

    update_data = {
        "last_interaction": interaction_type,
        "last_updated": current_time,
        f"transcript/{last_index}": {
            "model_name": model_name,
            "content": messages[-1]["content"],
            "role": messages[-1]["role"],
            "timestamp": current_time,
            "interaction": interaction_type,
            "user_understood": feedback_value
        }
    }

    _firebase_patch(session, url, credentials, update_data)

def update_previous_feedback(user_id, session_id, messages, understood_value):
    session, base_url, credentials = get_db_session()
    clean_uid = str(user_id).replace(".", "_")
    target_index = len(messages) - 2

    if target_index >= 0:
        url = f"{base_url}/logs/{clean_uid}/{session_id}/transcript/{target_index}.json"
        _firebase_patch(session, url, credentials, {"user_understood": understood_value})