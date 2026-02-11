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
    clean_uid = str(user_id).replace(".", "_")

    # Path to the specific session
    session_ref = db_ref.child("logs").child(clean_uid).child(session_id)

    # 1. Prepare top-level metadata
    # 2. Update the last message in the transcript to include the model_name
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # We only update the 'model_name' on the very last message being logged
    last_index = len(messages) - 1

    update_data = {
        "last_interaction": interaction_type,
        "last_updated": current_time,
        f"transcript/{last_index}/model_name": model_name,
        f"transcript/{last_index}/content": messages[-1]["content"],
        f"transcript/{last_index}/role": messages[-1]["role"],
        f"transcript/{last_index}/timestamp": current_time,
        f"transcript/{last_index}/interaction": interaction_type
    }

    # Using update() ensures we don't overwrite the whole session,
    # just the specific keys we've defined.
    session_ref.update(update_data)

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
