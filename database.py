import pyrebase
import streamlit as st
from datetime import datetime


# Initialize Pyrebase connection
@st.cache_resource
def get_firebase_db():
    config = {
        "apiKey": st.secrets["firebase"]["apiKey"],
        "authDomain": st.secrets["firebase"]["authDomain"],
        "databaseURL": st.secrets["firebase"]["databaseURL"],
        "storageBucket": st.secrets["firebase"]["storageBucket"]
    }
    firebase = pyrebase.initialize_app(config)
    return firebase.database()


def save_to_firebase(user_id, model_name, messages, interaction_type, session_id, feedback_value=None):
    db = get_firebase_db()

    clean_uid = str(user_id).replace(".", "_")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_index = len(messages) - 1

    # Path: logs/user_id/session_id
    # We use .update() to merge new keys without overwriting the whole node
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

    try:
        db.child("logs").child(clean_uid).child(session_id).update(update_data)
    except Exception as e:
        st.error(f"Firebase Update Error: {e}")


def update_previous_feedback(user_id, session_id, messages, understood_value):
    db = get_firebase_db()
    clean_uid = str(user_id).replace(".", "_")
    target_index = len(messages) - 2

    if target_index >= 0:
        try:
            # Targeting the specific index inside the transcript
            db.child("logs").child(clean_uid).child(session_id) \
                .child("transcript").child(target_index) \
                .update({"user_understood": understood_value})
        except Exception as e:
            st.error(f"Firebase Feedback Error: {e}")