import requests
import json
import streamlit as st
from datetime import datetime


# We use cache_resource to keep the session alive across reruns
@st.cache_resource
def get_db_session():
    session = requests.Session()
    # Add a prefix to the URL for convenience
    base_url = st.secrets["firebase_db_url"].rstrip('/')
    return session, base_url


def save_to_firebase(user_id, model_name, messages, interaction_type, session_id, feedback_value=None):
    session, base_url = get_db_session()

    clean_uid = str(user_id).replace(".", "_")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_index = len(messages) - 1

    # Path for the specific log entry
    path = f"logs/{clean_uid}/{session_id}"

    # Construct the payload
    # Note: We only send the specific NEW data to save bandwidth
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

    # PATCH performs an incremental update (merges keys)
    # Adding .json to the URL is required by Firebase REST API
    try:
        url = f"{base_url}/{path}.json"
        session.patch(url, data=json.dumps(update_data))
    except Exception as e:
        print(f"Firebase REST Error: {e}")


def update_previous_feedback(user_id, session_id, messages, understood_value):
    session, base_url = get_db_session()
    clean_uid = str(user_id).replace(".", "_")
    target_index = len(messages) - 2

    if target_index >= 0:
        path = f"logs/{clean_uid}/{session_id}/transcript/{target_index}.json"
        data = {"user_understood": understood_value}
        try:
            session.patch(f"{base_url}/{path}", data=json.dumps(data))
        except Exception as e:
            print(f"Firebase Feedback Error: {e}")