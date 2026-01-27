import streamlit as st
from ai_strategy import AIManager
from database import save_to_firebase, get_firebase_connection, load_selected_chat
from streamlit_cookies_controller import CookieController
from datetime import datetime
import requests
import json


# --- 1. Core Functions & Caching ---

@st.cache_data(show_spinner="Fetching session details...")
def get_cached_session(user_id, session_id):
    """Fetches a specific session's data once and stores it in memory."""
    db_ref = get_firebase_connection()
    clean_id = str(user_id).replace(".", "_")
    return db_ref.child("logs").child(clean_id).child(session_id).get()


def convert_messages_to_text():
    """Converts session messages to a readable format for download."""
    transcript = "Chat History - Business Planning Assistant\n" + "=" * 40 + "\n"
    for msg in st.session_state.get("messages", []):
        role = "User" if msg["role"] == "user" else "Assistant"
        transcript += f"\n[{role}]: {msg['content']}\n"
    return transcript


def handle_feedback(understood: bool, selected_label):
    """Processes user feedback on AI responses."""
    if understood:
        save_to_firebase(
            st.session_state["current_user"],
            selected_label,
            st.session_state["messages"],
            "UNDERSTOOD_FEEDBACK",
            st.session_state["session_id"],
        )
    else:
        st.session_state["messages"].append({
            "role": "user",
            "content": "I don't understand the previous explanation. Please break it down further."
        })
        st.session_state["trigger_clarification"] = True

    st.session_state["feedback_pending"] = False


# --- 2. Session Initialization ---

if "session_id" not in st.session_state:
    st.session_state["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")

if "messages" not in st.session_state: st.session_state["messages"] = []
if "feedback_pending" not in st.session_state: st.session_state["feedback_pending"] = False
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "current_user" not in st.session_state: st.session_state["current_user"] = None

# --- 3. Authentication & Cookies ---

controller = CookieController()
AUTHORIZED_STUDENT_IDS = st.secrets["AUTHORIZED_STUDENT_LIST"]

# Check for existing login cookie
cached_uid = controller.get('student_auth_id')
if cached_uid and not st.session_state["authenticated"]:
    if cached_uid in AUTHORIZED_STUDENT_IDS:
        st.session_state["authenticated"] = True
        st.session_state["current_user"] = cached_uid

# --- 4. Page Configuration ---

st.set_page_config(layout="wide", page_title="Business Planning Assistant")

# Custom Button Styling
st.markdown("""
    <style>
    div[data-testid="stColumn"]:nth-of-type(1) button { background-color: #28a745 !important; color: white !important; }
    div[data-testid="stColumn"]:nth-of-type(2) button { background-color: #dc3545 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

AI_CONFIG = {
    "active_model": "gemini-3-pro-preview",
    "system_instruction": "You are a helpful Business Planning Assistant. Provide clear, professional, and actionable advice."
}
selected_label = AI_CONFIG["active_model"]
system_instr = AI_CONFIG["system_instruction"]

# --- 5. Sidebar Logic ---

with st.sidebar:
    st.image("icdf.png")
    st.header("Menu")

    if not st.session_state["authenticated"]:
        u_id = st.text_input("Enter Student ID", type="password")
        if st.button("Login", use_container_width=True):
            if u_id in AUTHORIZED_STUDENT_IDS:
                controller.set('student_auth_id', u_id)
                st.session_state["authenticated"] = True
                st.session_state["current_user"] = u_id
                st.rerun()
            else:
                st.error("Invalid ID")
    else:
        st.write(f"**Logged in as:** {st.session_state['current_user']}")

        # Logout & Feedback Buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        with col2:
            st.link_button("Form", "https://forms.office.com/...", use_container_width=True)

        # Download Current Chat
        if st.session_state["messages"]:
            chat_text = convert_messages_to_text()
            st.download_button("📥 Download Chat", chat_text, file_name="chat.txt", use_container_width=True)

        st.markdown("---")

        # --- History Section (Optimized Fetching) ---
        clean_user_id = str(st.session_state['current_user']).replace(".", "_")
        base_url = st.secrets["firebase_db_url"].rstrip('/')
        shallow_url = f"{base_url}/logs/{clean_user_id}.json?shallow=true"

        try:
            # Step A: Shallow call to get just the keys/dates
            response = requests.get(shallow_url)
            user_sessions_keys = response.json()
        except:
            user_sessions_keys = None

        if user_sessions_keys:
            display_options = {}
            for raw_key in sorted(user_sessions_keys.keys(), reverse=True):
                try:
                    dt_obj = datetime.strptime(raw_key, "%Y%m%d_%H%M%S")
                    clean_date = dt_obj.strftime("%b %d, %Y - %I:%M %p")
                except:
                    clean_date = str(raw_key)
                display_options[clean_date] = raw_key

            st.subheader("Chat History")
            selected_display = st.selectbox("Previous sessions:", options=list(display_options.keys()))
            sel_log_key = display_options[selected_display]

            # Step B: Get session content from cache or DB
            log_content = get_cached_session(st.session_state['current_user'], sel_log_key)

            # Standardize data format (Firebase can return lists or dicts)
            messages_list = []
            if isinstance(log_content, dict):
                # Sort by key to maintain conversation order
                sorted_keys = sorted(log_content.keys(), key=lambda x: int(x) if x.isdigit() else x)
                messages_list = [log_content[k] for k in sorted_keys]
            elif isinstance(log_content, list):
                messages_list = log_content

            # Step C: Show Preview
            with st.container(border=True):
                st.caption("🔍 Preview: First Exchange")

                # Filter for actual chat messages (ignore metadata if any)
                chat_only = [m for m in messages_list if isinstance(m, dict) and "content" in m]

                if chat_only:
                    # Show first User message
                    user_msg = next((m["content"] for m in chat_only if m.get("role") == "user"),
                                    "No user message found.")
                    st.markdown(f"**Q:** {user_msg[:80]}...")

                    # Show first Assistant message
                    st.divider()
                    ast_msg = next((m["content"] for m in chat_only if m.get("role") == "assistant"),
                                   "No response yet.")
                    st.markdown(f"**A:** {ast_msg[:80]}...")
                else:
                    st.info("No message history found in this session.")

            if st.button("🔄 Load & Continue", type="primary", use_container_width=True):
                st.session_state["messages"] = []
                st.session_state["session_id"] = sel_log_key
                load_selected_chat(st.session_state['current_user'], sel_log_key)
                st.rerun()

        # Clear Chat / New Session
        if st.button("New Chat", use_container_width=True):
            st.session_state["messages"] = []
            st.session_state["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.rerun()

# --- 6. Main UI & Chat Logic ---

st.image("combined_logo.jpg")
st.title("Business Planning Assistant")

if not st.session_state["authenticated"]:
    st.warning("Please login with an authorized Student ID in the sidebar.")
else:
    # Render Chat History
    for msg in st.session_state["messages"]:
        role_label = st.session_state["current_user"] if msg["role"] == "user" else "Assistant"
        with st.chat_message(msg["role"]):
            if "interaction" in msg:
                st.caption(f"Action: {msg['interaction'].replace('_', ' ')}")
            with st.container(border=True):
                st.markdown(f"**{role_label}:**")
                st.markdown(msg["content"])

    # Clarification Trigger (If user clicked "I need help")
    if st.session_state.get("trigger_clarification", False):
        with st.chat_message("assistant"):
            with st.container(border=True):
                st.markdown("**Business Planning Assistant:**")
                ai_manager = AIManager(selected_label)
                full_response = st.write_stream(
                    ai_manager.get_response_stream(st.session_state["messages"], system_instr))

        save_to_firebase(st.session_state["current_user"], selected_label, st.session_state["messages"],
                         "CLARIFICATION_RESPONSE", st.session_state["session_id"])
        st.session_state["messages"].append({"role": "assistant", "content": full_response})
        st.session_state["trigger_clarification"] = False
        st.session_state["feedback_pending"] = True
        st.rerun()

    # Standard Input
    input_ph = "Awaiting feedback..." if st.session_state["feedback_pending"] else "Ask your question here..."
    if prompt := st.chat_input(input_ph, disabled=st.session_state["feedback_pending"]):
        st.session_state["messages"].append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.container(border=True):
                st.markdown("**Business Planning Assistant:**")
                ai_manager = AIManager(selected_label)
                full_response = st.write_stream(
                    ai_manager.get_response_stream(st.session_state["messages"], system_instr))

        save_to_firebase(st.session_state["current_user"], selected_label, st.session_state["messages"],
                         "INITIAL_QUERY", st.session_state["session_id"])
        st.session_state["messages"].append({"role": "assistant", "content": full_response})
        st.session_state["feedback_pending"] = True
        st.rerun()

    # Feedback Buttons
    if st.session_state["feedback_pending"]:
        st.divider()
        st.info("Did you understand the response?")
        c1, c2 = st.columns(2)
        with c1:
            st.button("I understand!", on_click=handle_feedback, args=(True, selected_label), use_container_width=True)
        with c2:
            st.button("I need help!", on_click=handle_feedback, args=(False, selected_label), use_container_width=True)