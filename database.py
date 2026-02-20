import requests
import json
import streamlit as st
from datetime import datetime

@st.cache_resource
def get_db_session():
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "X-HTTP-Method-Override": "PATCH"  # Explicit method signaling
    })
    base_url = st.secrets["firebase_db_url"].rstrip('/')
    return session, base_url

def _firebase_patch(session, url, data: dict):
    """Send a PATCH to Firebase and discard the response body immediately."""
    try:
        with session.patch(url, data=json.dumps(data), stream=True) as response:
            response.close()  # Discard body — we don't need Firebase's echo
    except Exception as e:
        print(f"Firebase REST Error: {e}")

def save_to_firebase(user_id, model_name, messages, interaction_type, session_id, feedback_value=None):
    session, base_url = get_db_session()
    clean_uid = str(user_id).replace(".", "_")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_index = len(messages) - 1

    path = f"{base_url}/logs/{clean_uid}/{session_id}.json"

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

    _firebase_patch(session, path, update_data)

def update_previous_feedback(user_id, session_id, messages, understood_value):
    session, base_url = get_db_session()
    clean_uid = str(user_id).replace(".", "_")
    target_index = len(messages) - 2

    if target_index >= 0:
        path = f"{base_url}/logs/{clean_uid}/{session_id}/transcript/{target_index}.json"
        _firebase_patch(session, path, {"user_understood": understood_value})