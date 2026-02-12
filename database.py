import firebase_admin
from firebase_admin import credentials, db
import datetime
import streamlit as st

# Load service account credentials from st.secrets
# Fix formatting for the private key (common issue with environment variables)
@st.cache_resource
def get_firebase_connection():
    if not firebase_admin._apps:
        cred_info = dict(st.secrets["firebase_service_account"])
        cred_info["private_key"] = cred_info["private_key"].replace("\\n", "\n")
        db_url = st.secrets["firebase_db_url"].strip()
        cred = credentials.Certificate(cred_info)
        firebase_admin.initialize_app(cred, {'databaseURL': db_url})
    return db.reference("/")

#The save_to_firebase function uses Flattened Updates to avoid overwriting existing chat data.
def save_to_firebase(user_id, model_name, messages, interaction_type, session_id, feedback_value=None):
    db_ref = get_firebase_connection()
    clean_uid = str(user_id).replace(".", "_")

    session_ref = db_ref.child("logs").child(clean_uid).child(session_id)
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_index = len(messages) - 1

    update_data = {
        "last_interaction": interaction_type,
        "last_updated": current_time,
        f"transcript/{last_index}/model_name": model_name,
        f"transcript/{last_index}/content": messages[-1]["content"],
        f"transcript/{last_index}/role": messages[-1]["role"],
        f"transcript/{last_index}/timestamp": current_time,
        f"transcript/{last_index}/interaction": interaction_type,
        # --- NEW FIELD ---
        f"transcript/{last_index}/user_understood": feedback_value
    }

    session_ref.update(update_data)

#Loads a specific conversation from the database into Streamlit's session_state.
# Efficiently fetch only the message list (the transcript)
# Firebase sometimes returns JSON arrays as Python lists.
# This list comprehension removes 'None' holes created by manual indexing.
# Firebase sometimes returns JSON arrays as Python lists.
# This list comprehension removes 'None' holes created by manual indexing.
def load_selected_chat(user_id, session_key):
    db_ref = get_firebase_connection()
    clean_user_id = str(user_id).replace(".", "_")

    transcript = db_ref.child("logs").child(clean_user_id).child(session_key).child("transcript").get()

    if transcript:
        if isinstance(transcript, list):
            st.session_state["messages"] = [m for m in transcript if m is not None]
        else:
            st.session_state["messages"] = list(transcript.values())
            
        st.session_state["session_id"] = session_key

# Calculate the index of the AI message that just occurred
# Update only the specific field 'user_understood' for that specific message
def update_previous_feedback(user_id, session_id, messages, understood_value):
    db_ref = get_firebase_connection()
    clean_uid = str(user_id).replace(".", "_")

    target_index = len(messages) - 2

    if target_index >= 0:
        path = f"logs/{clean_uid}/{session_id}/transcript/{target_index}"
        db_ref.child(path).update({
            "user_understood": understood_value
        })