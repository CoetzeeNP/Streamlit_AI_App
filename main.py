import streamlit as st
from ai_strategy import AIManager
from database import save_to_firebase, get_firebase_connection, load_selected_chat
from streamlit_cookies_controller import CookieController

# 1. Initialize Cookie Controller before Page Config
controller = CookieController()

# --- Constants & State Initialization ---
AUTHORIZED_STUDENT_IDS = st.secrets["AUTHORIZED_STUDENT_LIST"]

# --- Session State Defaults ---
if "messages" not in st.session_state: st.session_state["messages"] = []
if "feedback_pending" not in st.session_state: st.session_state["feedback_pending"] = False
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "current_user" not in st.session_state: st.session_state["current_user"] = None

# --- Cookie Persistence Check ---
# This runs every time the page loads/refreshes
cached_uid = controller.get('student_auth_id')
if cached_uid and not st.session_state["authenticated"]:
    if cached_uid in AUTHORIZED_STUDENT_IDS:
        st.session_state["authenticated"] = True
        st.session_state["current_user"] = cached_uid

# --- Page Config & Styling ---
st.set_page_config(layout="wide", page_title="Business Planning Assistant")

st.markdown("""
    <style>
    div[data-testid="stColumn"]:nth-of-type(1) button { background-color: #28a745 !important; color: white !important; }
    div[data-testid="stColumn"]:nth-of-type(2) button { background-color: #dc3545 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- Internal AI Configuration ---
AI_CONFIG = {
    "active_model": "gemini-3-pro-preview",
    "system_instruction": "You are a helpful Business Planning Assistant. Provide clear, professional, and actionable advice."
}
selected_label = AI_CONFIG["active_model"]
system_instr = AI_CONFIG["system_instruction"]

def convert_messages_to_text():
    """Converts session messages to a readable format for download."""
    transcript = "Chat History - Business Planning Assistant\n" + "=" * 40 + "\n"
    for msg in st.session_state["messages"]:
        role = "User" if msg["role"] == "user" else "Assistant"
        transcript += f"\n[{role}]: {msg['content']}\n"
    return transcript


# --- Helper Functions ---
def handle_feedback(understood: bool, selected_label, system_instruction):
    # Standard logging logic
    interaction = "UNDERSTOOD_FEEDBACK" if understood else "CLARIFICATION_REQUESTED"
    last_ai_reply = st.session_state["messages"][-1]["content"]
    save_to_firebase(st.session_state["current_user"], selected_label, "N/A", last_ai_reply, interaction)

    if not understood:
        clarification_prompt = f"I don't understand the previous explanation. Please break it down further."

        # 1. Append the user message to history
        st.session_state["messages"].append({"role": "user", "content": clarification_prompt})

        # 2. Set the flags
        st.session_state["trigger_clarification"] = True
        st.session_state["feedback_pending"] = False

        # 3. Explicit rerun to catch the trigger
        st.rerun()
    else:
        st.session_state["feedback_pending"] = False

# --- UI Header ---
st.image("combined_logo.jpg")
st.title("Business Planning Assistant")

# --- Sidebar Management ---
with st.sidebar:
    st.image("icdf.png")
    st.header("Menu")

    if not st.session_state["authenticated"]:
        u_id = st.text_input("Enter Student ID", type="password")
        if st.button("Login", use_container_width=True):
            if u_id in AUTHORIZED_STUDENT_IDS:
                controller.set('student_auth_id', u_id)  # Save cookie
                st.session_state["authenticated"] = True
                st.session_state["current_user"] = u_id
                st.rerun()
            else:
                st.error("Invalid ID")
    else:
        st.write(f"**Logged in as:** {st.session_state['current_user']}")

        # --- Download Button ---
        if st.session_state["messages"]:
            chat_text = convert_messages_to_text()
            st.download_button(
                label="📥 Download Chat (.txt)",
                data=chat_text,
                file_name=f"chat_log_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )

        # --- Load History Section ---
        st.markdown("---")
        st.subheader("Previous Chats")
        db_ref = get_firebase_connection()
        clean_user_id = str(st.session_state['current_user']).replace(".", "_")

        # Get list of previous session keys (timestamps)
        user_logs = db_ref.child("logs").child(clean_user_id).get()

        if user_logs:
            # Show keys in descending order (newest first)
            log_keys = sorted(user_logs.keys(), reverse=True)
            selected_session = st.selectbox("Select a past session", log_keys)

            if st.button("Load Session", use_container_width=True):
                load_selected_chat(st.session_state['current_user'], selected_session)
                st.rerun()
        else:
            st.info("No history found.")

        st.markdown("---")
        # ... rest of your logout/clear buttons ...

        st.markdown("---")
        if st.button("Clear Chat", use_container_width=True, type="secondary"):
            st.session_state["messages"], st.session_state["feedback_pending"] = [], False
            st.rerun()

# --- Main Logic ---
if not st.session_state["authenticated"]:
    st.warning("Please login with an authorized Student ID in the sidebar.")
else:
    # 1. Display History
    for msg in st.session_state["messages"]:
        label = st.session_state["current_user"] if msg["role"] == "user" else "Business Planning Assistant"
        with st.chat_message(msg["role"]):
            with st.container(border=True):
                st.markdown(f"**{label}:**")
                st.markdown(msg["content"])

    # 2. NEW: The Clarification Trigger Catch
    # This block runs if handle_feedback set the trigger_clarification flag
    if st.session_state.get("trigger_clarification", False):
        with st.chat_message("assistant"):
            with st.container(border=True):
                st.markdown("**Business Planning Assistant:**")
                ai_manager = AIManager(selected_label)
                # Stream the response for the clarification prompt
                full_response = st.write_stream(
                    ai_manager.get_response_stream(st.session_state["messages"], system_instr)
                )

        # Finalize Clarification State
        save_to_firebase(st.session_state["current_user"], selected_label, "Clarification Request", full_response, "CLARIFICATION_RESPONSE")
        st.session_state["messages"].append({"role": "assistant", "content": full_response})
        st.session_state["trigger_clarification"] = False  # Reset the trigger
        st.session_state["feedback_pending"] = True       # Show feedback buttons again
        st.rerun()

    # 3. Standard Chat Input
    input_ph = "Please give feedback on the last answer..." if st.session_state["feedback_pending"] else "Ask your question here..."
    if prompt := st.chat_input(input_ph, disabled=st.session_state["feedback_pending"]):

        st.session_state["messages"].append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.container(border=True):
                st.markdown("**Business Planning Assistant:**")
                ai_manager = AIManager(selected_label)
                full_response = st.write_stream(
                    ai_manager.get_response_stream(st.session_state["messages"], system_instr)
                )

        save_to_firebase(st.session_state["current_user"], selected_label, prompt, full_response, "INITIAL_QUERY")
        st.session_state["messages"].append({"role": "assistant", "content": full_response})
        st.session_state["feedback_pending"] = True
        st.rerun()

    # 4. Feedback Section
    if st.session_state["feedback_pending"]:
        st.divider()
        st.info("Did you understand the assistant's response?")
        c1, c2 = st.columns(2)
        with c1:
            st.button("I understand!", on_click=handle_feedback, args=(True, selected_label, system_instr), use_container_width=True)
        with c2:
            st.button("I need some help!", on_click=handle_feedback, args=(False, selected_label, system_instr), use_container_width=True)