import firebase_admin
from firebase_admin import credentials, db
import datetime
import streamlit as st

@st.cache_resource
def get_firebase_connection():
    if not firebase_admin._apps:
        cred_info = dict(st.secrets["firebase_service_account"])
        cred_info["private_key"] = cred_info["private_key"].replace("\\n", "\n")
        db_url = st.secrets["firebase_db_url"].strip()
        cred = credentials.Certificate(cred_info)
        firebase_admin.initialize_app(cred, {'databaseURL': db_url})
    return db.reference("/")


def save_to_firebase(user_id, model_name, messages, interaction_type, session_id):
    db_ref = get_firebase_connection()
    if db_ref:
        clean_user_id = str(user_id).replace(".", "_")

        if messages:
            messages[-1]["interaction"] = interaction_type

        db_ref.child("logs").child(clean_user_id).child(session_id).update({
            "model_name": model_name,
            "transcript": messages,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

# This stays the same and works better with Option 1
def load_selected_chat(user_id, session_key):
    db_ref = get_firebase_connection()
    clean_user_id = str(user_id).replace(".", "_")

    # 1. Fetch only the transcript from the OLD session
    old_transcript_ref = db_ref.child("logs").child(clean_user_id).child(session_key).child("transcript")
    transcript = old_transcript_ref.get()

    if transcript:
        # Normalize: Handle if Firebase returns a dict or a list with Nones
        if isinstance(transcript, dict):
            clean_messages = list(transcript.values())
        else:
            clean_messages = [m for m in transcript if m is not None]

        # 2. Generate a NEW session ID
        # Using datetime.now() requires 'from datetime import datetime'
        new_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 3. Prepare the data for the new session
        new_session_data = {
            "transcript": clean_messages,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model_name": "ThunderbAIrd"
        }

        # 4. Save to Firebase as a NEW entry
        db_ref.child("logs").child(clean_user_id).child(new_session_id).set(new_session_data)

        # 5. Update Streamlit state
        st.session_state["messages"] = clean_messages
        st.session_state["session_id"] = new_session_id
    else:
        # If no transcript, just start a fresh session
        st.session_state["messages"] = []
        st.session_state["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")