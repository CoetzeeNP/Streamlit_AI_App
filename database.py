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
        # Use the session_id as the key so we update the SAME record
        db_ref.child("logs").child(clean_user_id).child(session_id).set({
            "model_name": model_name,
            "transcript": messages,  # Saves the entire list of dictionaries
            "interaction_type": interaction_type,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })


def load_selected_chat(user_id, session_key):
    db_ref = get_firebase_connection()
    clean_user_id = str(user_id).replace(".", "_")
    chat_data = db_ref.child("logs").child(clean_user_id).child(session_key).get()

    if chat_data and "transcript" in chat_data:
        st.session_state["messages"] = chat_data["transcript"]
        st.session_state["session_id"] = session_key  # Keep using this ID to update history
        st.success(f"Loaded session: {session_key}")