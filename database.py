import threading
import firebase_admin
from firebase_admin import credentials, db
import datetime
import streamlit as st


@st.cache_resource
def get_firebase_app():
    """Initializes the Firebase App once and caches it."""
    if not firebase_admin._apps:
        cred_info = dict(st.secrets["firebase_service_account"])
        # Efficiently handle the newline issue
        cred_info["private_key"] = cred_info["private_key"].replace("\\n", "\n")
        db_url = st.secrets["firebase_db_url"].strip()
        cred = credentials.Certificate(cred_info)
        return firebase_admin.initialize_app(cred, {'databaseURL': db_url})
    return firebase_admin.get_app()


# Inside database.py, change your update helper to this:
def _async_update(path, data):
    try:
        # Pass the app explicitly to ensure we aren't using a global default
        # that might be compromised by a root reference.
        app = get_firebase_app()
        ref = db.reference(path, app=app)
        ref.update(data)
    except Exception as e:
        print(f"Firebase Async Error: {e}")


def save_to_firebase(user_id, model_name, messages, interaction_type, session_id, feedback_value=None):
    # Ensure app is ready
    get_firebase_app()

    clean_uid = str(user_id).replace(".", "_")
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_index = len(messages) - 1

    # Target path for the specific session
    base_path = f"logs/{clean_uid}/{session_id}"

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

    # Offload the network I/O to a background thread
    threading.Thread(target=_async_update, args=(base_path, update_data)).start()


def update_previous_feedback(user_id, session_id, messages, understood_value):
    get_firebase_app()
    clean_uid = str(user_id).replace(".", "_")
    target_index = len(messages) - 2

    if target_index >= 0:
        path = f"logs/{clean_uid}/{session_id}/transcript/{target_index}"
        data = {"user_understood": understood_value}

        # Async call to prevent UI lag on feedback click
        threading.Thread(target=_async_update, args=(path, data)).start()