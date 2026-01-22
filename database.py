import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import streamlit as st
import datetime

@st.cache_resource
def get_firebase_connection():
    if not firebase_admin._apps:
        cred_info = dict(st.secrets["firebase_service_account"])
        cred_info["private_key"] = cred_info["private_key"].replace("\\n", "\n")
        db_url = st.secrets["firebase_db_url"].strip()
        cred = credentials.Certificate(cred_info)
        firebase_admin.initialize_app(cred, {'databaseURL': db_url})
    return db.reference("/")

def save_to_firebase(user_id, model_name, prompt_, full_response, interaction_type, messages):
    db_ref = get_firebase_connection()
    if db_ref:
        clean_user_id = str(user_id).replace(".", "_")
        timestamp_key = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_ref.child("logs").child(clean_user_id).child(timestamp_key).set({
            "model_name": model_name,
            "prompt": prompt_,
            "response": full_response,
            "transcript": messages,
            "interaction_type": interaction_type,
            "full_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })


def load_selected_chat(user_id, session_key):
    db_ref = get_firebase_connection()
    clean_user_id = str(user_id).replace(".", "_")
    chat_data = db_ref.child("logs").child(clean_user_id).child(session_key).get()

    if chat_data and "transcript" in chat_data:
        # Overwrite current session messages with the historical transcript
        st.session_state["messages"] = chat_data["transcript"]
        st.success("Chat history loaded!")