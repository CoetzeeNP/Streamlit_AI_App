import streamlit as st
from ai_strategy import AIManager
from database import save_to_firebase, get_firebase_connection, load_selected_chat
from streamlit_cookies_controller import CookieController
from datetime import datetime
import json

if "session_id" not in st.session_state:
    st.session_state["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")

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
def handle_feedback(understood: bool, selected_label):
    if understood:
        # Log successful interaction
        save_to_firebase(
            st.session_state["current_user"],
            selected_label,
            st.session_state["messages"],
            "UNDERSTOOD_FEEDBACK",
            st.session_state["session_id"],
        )
    else:
        # 1. Append the prompt for the LLM
        st.session_state["messages"].append({
            "role": "user",
            "content": "I don't understand the previous explanation. Please break it down further."
        })
        # 2. Set the flag to trigger the AI in the main loop
        st.session_state["trigger_clarification"] = True

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

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()

        with col2:
            # Your new MS Form button
            st.link_button("Feedback",
                           "https://forms.office.com/Pages/ResponsePage.aspx?id=uRv8jg-5SEq_bLoGhhk7gBvkZQsfRhhErcivaQmEhItUNENSMEJNQTM3UzQ1RlBMSFBUVTFKTFg2VS4u",
                           use_container_width=True)


        # --- Download Button ---
        if st.session_state["messages"]:
            chat_text = "Business Planning Assistant Transcript\n" + "=" * 30
            for m in st.session_state["messages"]:
                chat_text += f"\n{m['role'].upper()}: {m['content']}\n"

            st.download_button("📥 Download Current Chat", chat_text, file_name="chat.txt", use_container_width=True)

            # 2. LOAD PREVIOUS CHATS
        st.markdown("---")
        db_ref = get_firebase_connection()
        clean_user_id = str(st.session_state['current_user']).replace(".", "_")
        user_logs = db_ref.child("logs").child(clean_user_id).get()

        if user_logs:
            # 1. Create the mapping for clean timestamps
            display_options = {}
            for raw_key in sorted(user_logs.keys(), reverse=True):
                try:
                    dt_obj = datetime.fromisoformat(str(raw_key))
                    clean_date = dt_obj.strftime("%b %d, %Y - %I:%M %p")
                except ValueError:
                    clean_date = str(raw_key)
                display_options[clean_date] = raw_key

            # 2. Selection UI
            st.subheader("Chat History")
            selected_display = st.selectbox(
                "Choose a previous session:",
                options=list(display_options.keys())
            )

            # Get the actual key and the data associated with it
            sel_log_key = display_options[selected_display]
            log_content = user_logs[sel_log_key]

            with st.container(border=True):
                st.caption("🔍 Preview of selected session")

                if isinstance(log_content, list) and len(log_content) > 0:
                    # Get the last message in the list for context, or [0] for the start
                    last_msg = log_content[-1]

                    # Handle cases where messages are dicts or JSON strings
                    if isinstance(last_msg, str):
                        try:
                            last_msg = json.loads(last_msg)
                        except:
                            pass

                    if isinstance(last_msg, dict):
                        role = "User" if last_msg.get("role") == "user" else "AI"
                        content = last_msg.get("content", "")
                        st.markdown(f"**{role}**: {content[:150]}...")
                    else:
                        st.text(str(last_msg)[:150] + "...")
                else:
                    # If log_content is a single string or dict
                    st.info("No message preview available.")

            # 4. Action Button
            if st.button("🔄 Load & Continue Session", type="primary", use_container_width=True):
                st.session_state["messages"] = []
                load_selected_chat(st.session_state['current_user'], sel_log_key)
                st.rerun()

        # 3. CLEAR CHAT (Important: resets session_id)
        if st.button("New Chat", use_container_width=True):
            st.session_state["messages"] = []
            st.session_state["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.rerun()

# --- Main Logic ---
if not st.session_state["authenticated"]:
    st.warning("Please login with an authorized Student ID in the sidebar.")
else:
    for msg in st.session_state["messages"]:
        role_label = st.session_state["current_user"] if msg["role"] == "user" else "Assistant"

        with st.chat_message(msg["role"]):
            # Show the interaction type as a small caption if it exists
            if "interaction" in msg:
                st.caption(f"Action: {msg['interaction'].replace('_', ' ')}")

            with st.container(border=True):
                st.markdown(f"**{role_label}:**")
                st.markdown(msg["content"])

    # 2. NEW: The Clarification Trigger Catch
    # This block runs if handle_feedback set the trigger_clarification flag
    if st.session_state.get("trigger_clarification", False):
        with st.chat_message("assistant"):
            with st.container(border=True):
                st.markdown("**Business Planning Assistant:**")
                ai_manager = AIManager(selected_label)
                full_response = st.write_stream(
                    ai_manager.get_response_stream(st.session_state["messages"], system_instr)
                )

        # Finalize Clarification State
        save_to_firebase(
            st.session_state["current_user"],
            selected_label,
            st.session_state["messages"],  # Correct: passing the list
            "CLARIFICATION_RESPONSE",  # Correct: the interaction type
            st.session_state["session_id"]  # Correct: the missing session_id
        )

        st.session_state["messages"].append({"role": "assistant", "content": full_response})
        st.session_state["trigger_clarification"] = False
        st.session_state["feedback_pending"] = True
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

        save_to_firebase(
            user_id=st.session_state["current_user"],
            model_name=selected_label,
            messages=st.session_state["messages"],  # Pass the history list
            interaction_type="INITIAL_QUERY",
            session_id=st.session_state["session_id"]
        )
        st.session_state["messages"].append({"role": "assistant", "content": full_response})
        st.session_state["feedback_pending"] = True
        st.rerun()

    # 4. Feedback Section
    if st.session_state["feedback_pending"]:
        st.divider()
        st.info("Did you understand the assistant's response?")
        c1, c2 = st.columns(2)
        with c1:
            st.button("I understand!", on_click=handle_feedback, args=(True, selected_label), use_container_width=True)
        with c2:
            st.button("I need some help!", on_click=handle_feedback, args=(False, selected_label), use_container_width=True)