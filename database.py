import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def save_to_firebase(user_id, model_name, messages, interaction_type, session_id, feedback_value=None):
    supabase = get_supabase_client()
    last_msg = messages[-1]

    data = {
        "user_id": str(user_id),
        "session_id": session_id,
        "interaction_type": interaction_type,
        "model_name": model_name,
        "role": last_msg["role"],
        "content": last_msg["content"],
        "user_understood": feedback_value
    }

    # .execute() returns the inserted row. We catch the ID.
    response = supabase.table("chat_logs").insert(data).execute()
    if response.data:
        return response.data[0]["id"]
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