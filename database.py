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
        # Reference the specific session ID
        session_ref = db_ref.child("logs").child(clean_user_id).child(session_id)

        session_ref.update({
            "model_name": model_name,
            "transcript": messages,  # The list grows, but it updates the SAME key
            "last_interaction_type": interaction_type,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

# This stays the same and works better with Option 1
def load_selected_chat(user_id, session_key):
    db_ref = get_firebase_connection()
    clean_user_id = str(user_id).replace(".", "_")
    chat_data = db_ref.child("logs").child(clean_user_id).child(session_key).get()

    if chat_data and "transcript" in chat_data:
        st.session_state["messages"] = chat_data["transcript"]
        st.session_state["session_id"] = session_key