import streamlit as st
from supabase import create_client, Client
from bs4 import BeautifulSoup

@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def strip_html(html_content):

    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    return soup.get_text(separator=" ")

def save_to_supabase(user_id, model_name, messages, interaction_type, session_id, feedback_value=None):
    if not messages:
        return None

    supabase = get_supabase_client()
    last_msg = messages[-1]

    # Clean the content specifically for the database
    clean_content = strip_html(last_msg.get("content", ""))

    data = {
        "user_id": str(user_id),
        "session_id": session_id,
        "interaction_type": interaction_type,
        "model_name": model_name,
        "role": last_msg.get("role"),
        "content": clean_content,
        "user_understood": feedback_value
    }

    try:
        response = supabase.table("chat_logs").insert(data).execute()
        if response.data:
            return response.data[0]["id"]
    except Exception as e:
        st.error(f"Database error: {e}")

    return None

def update_previous_feedback(user_id, session_id, messages, understood_value):
    """Updates the 'user_understood' flag for the last assistant response"""
    supabase = get_supabase_client()

    # Find the last record for this user/session that was an assistant response
    try:
        response = (
            supabase.table("chat_logs")
            .select("id")
            .eq("user_id", str(user_id))
            .eq("session_id", session_id)
            .eq("role", "assistant")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if response.data:
            record_id = response.data[0]["id"]
            supabase.table("chat_logs").update({"user_understood": understood_value}).eq("id", record_id).execute()
    except Exception as e:
        st.error(f"Error updating feedback: {e}")