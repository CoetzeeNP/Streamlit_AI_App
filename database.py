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


def save_to_firebase(user_id, model_name, messages, interaction_type, user_feedback, session_id):
    db_ref = get_firebase_connection()
    if db_ref:
        clean_user_id = str(user_id).replace(".", "_")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if messages:
            # 1. Update the last message with the interaction type only
            messages[-1]["interaction"] = interaction_type
            messages[-1]["user_feedback"] = user_feedback
            if "timestamp" not in messages[-1]:
                messages[-1]["timestamp"] = timestamp

        # 2. Build the update payload
        # We separate feedback into its own key so it's searchable/exportable
        log_data = {
            "model_name": model_name,
            "transcript": messages,
            "last_updated": timestamp
        }

        db_ref.child("logs").child(clean_user_id).child(session_id).update(log_data)

# This stays the same and works better with Option 1
def load_selected_chat(user_id, session_key):
    db_ref = get_firebase_connection()
    clean_user_id = str(user_id).replace(".", "_")
    
    # Target only the transcript node to avoid downloading metadata like 'model_name' 
    # if it's not needed for the UI state
    transcript = db_ref.child("logs").child(clean_user_id).child(session_key).child("transcript").get()

    if transcript:
        # Firebase lists with integer keys often return as lists; 
        # filter out None values caused by 0-indexing quirks
        if isinstance(transcript, list):
            st.session_state["messages"] = [m for m in transcript if m is not None]
        else:
            st.session_state["messages"] = list(transcript.values())
            
        st.session_state["session_id"] = session_key
