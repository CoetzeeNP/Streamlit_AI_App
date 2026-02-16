import streamlit as st
import time
from datetime import datetime
from ai_strategy import AIManager
from database import save_to_firebase, get_firebase_connection, load_selected_chat, update_previous_feedback
from streamlit_cookies_controller import CookieController
from streamlit_autorefresh import st_autorefresh

# 1. Setup & Configuration
st.set_page_config(layout="wide", page_title="Business Planning Assistant")
controller = CookieController()

# Heartbeat: This silently reruns the app every 2 minutes.
# This ensures 'last_seen' is updated in Firebase even if the user is idle.
if st.session_state.get("authenticated"):
    st_autorefresh(interval=120000, key="heartbeat_refresh")

# Custom CSS
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

# 2. State Initialization
if "session_id" not in st.session_state:
    st.session_state["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")
if "messages" not in st.session_state: st.session_state["messages"] = []
if "feedback_pending" not in st.session_state: st.session_state["feedback_pending"] = False
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "current_user" not in st.session_state: st.session_state["current_user"] = None

# Persistence & Auth
AUTHORIZED_IDS = st.secrets["AUTHORIZED_STUDENT_LIST"]
db_ref = get_firebase_connection()

# Check cookies for existing auth
cached_uid = controller.get('student_auth_id')
if cached_uid and not st.session_state["authenticated"]:
    if cached_uid in AUTHORIZED_IDS:
        st.session_state.update({"authenticated": True, "current_user": cached_uid})


# 3. Helper Functions
@st.cache_data(ttl=1800)
def get_cached_history_keys(user_id):
    return db_ref.child("logs").child(str(user_id).replace(".", "_")).get(shallow=True)


@st.cache_data(ttl=1800)
def get_cached_preview(user_id, session_key):
    try:
        clean_uid = str(user_id).replace(".", "_")
        return db_ref.child("logs").child(clean_uid).child(session_key).child("transcript").child("0").get()
    except Exception:
        return None


def generate_ai_response(interaction_type):
    with st.chat_message("assistant"):
        with st.container(border=True):
            st.markdown("**Business Planning Assistant:**")
            ai_manager = AIManager(AI_CONFIG["active_model"])
            full_res, actual_model = "", AI_CONFIG["active_model"]
            placeholder = st.empty()

            for chunk, model_label in ai_manager.get_response_stream(st.session_state["messages"],
                                                                     AI_CONFIG["system_instruction"]):
                full_res += chunk
                actual_model = model_label
                placeholder.markdown(full_res + "▌")
            placeholder.markdown(full_res)

    st.session_state["messages"].append({"role": "assistant", "content": full_res})
    st.session_state["last_model_used"] = actual_model
    st.session_state["feedback_pending"] = True

    save_to_firebase(st.session_state["current_user"], actual_model, st.session_state["messages"], interaction_type,
                     st.session_state["session_id"])
    st.rerun()


def handle_feedback(understood: bool):
    user_id, session_id = st.session_state["current_user"], st.session_state["session_id"]
    model_to_log = st.session_state.get("last_model_used", AI_CONFIG["active_model"])

    if understood:
        save_to_firebase(user_id, model_to_log, st.session_state["messages"], "GENERATED_RESPONSE", session_id,
                         feedback_value=True)
        st.session_state["feedback_pending"] = False
    else:
        clarification = "I don't understand the previous explanation. Please break it down further."
        st.session_state["messages"].append({"role": "user", "content": clarification})
        update_previous_feedback(user_id, session_id, st.session_state["messages"], False)
        st.session_state["trigger_clarification"] = True
        st.session_state["feedback_pending"] = False


###########################
###        Sidebar      ###
###########################
with st.sidebar:
    st.image("icdf.png")

    if not st.session_state["authenticated"]:
        u_id = st.text_input("Enter Student ID", type="password")
        if u_id:
            clean_id = str(u_id).replace(".", "_")
            session_data = db_ref.child("active_sessions").child(clean_id).get()
            current_ts = time.time()

            # 1. Determine Lock Status
            is_locked = False
            if session_data and isinstance(session_data, dict):
                # If last seen was less than 3 mins ago, it's technically "active"
                if (current_ts - session_data.get("last_seen", 0)) < 180:
                    is_locked = True

            # 2. Determine Button Label and Color
            btn_label = "Login"
            btn_help = "Standard login"
            if is_locked:
                st.warning("This ID is currently active elsewhere.")
                btn_label = "Force Login (Override Active Session)"
                btn_help = "Use this if your previous session crashed or you closed the tab."

            # 3. Single Button Action
            if st.button(btn_label, use_container_width=True, help=btn_help):
                if u_id in AUTHORIZED_IDS:
                    # Update/Overwrite the lock in Firebase
                    db_ref.child("active_sessions").child(clean_id).set({
                        "last_seen": time.time(),
                        "session_id": st.session_state["session_id"]
                    })
                    controller.set('student_auth_id', u_id)
                    st.session_state.update({"authenticated": True, "current_user": u_id})
                    st.rerun()
                else:
                    st.error("Invalid Student ID.")

        st.divider()
        st.subheader("Chat History")
        all_logs = get_cached_history_keys(st.session_state['current_user'])
        if all_logs:
            display_options = {datetime.strptime(k, "%Y%m%d_%H%M%S").strftime("%b %d, %Y - %I:%M %p"): k for k in
                               sorted(all_logs.keys(), reverse=True)}
            sel_key = display_options[st.selectbox("Select session:", options=list(display_options.keys()))]

            preview_msg = get_cached_preview(st.session_state['current_user'], sel_key)
            with st.expander("🔍 Preview"):
                if preview_msg: st.markdown(
                    f"**{preview_msg.get('role').title()}:** {preview_msg.get('content', '')[:100]}...")

            if st.button("🔄 Load & Continue", type="primary", use_container_width=True):
                load_selected_chat(st.session_state['current_user'], sel_key)
                st.session_state.update({"session_id": sel_key, "feedback_pending": False})
                st.rerun()

        if st.button("New Chat", use_container_width=True):
            st.session_state.update(
                {"messages": [], "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"), "feedback_pending": False})
            st.rerun()

###########################
###        Main         ###
###########################
st.image("combined_logo.jpg")
st.title("Business Planning Assistant")

if not st.session_state["authenticated"]:
    st.warning("Please login via the sidebar.")
    st.stop()

# SECURITY: Hijack check
clean_id = str(st.session_state['current_user']).replace(".", "_")
current_lock = db_ref.child("active_sessions").child(clean_id).get()
if current_lock and current_lock.get("session_id") != st.session_state["session_id"]:
    st.warning("Active session detected on another device. This session is now locked.")
    st.session_state.clear()
    st.stop()

# 1. Display Chat History
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        with st.container(border=True):
            st.markdown(
                f"**{st.session_state['current_user'] if msg['role'] == 'user' else 'Assistant'}:**\n\n{msg['content']}")

if st.session_state.get("trigger_clarification"):
    st.session_state["trigger_clarification"] = False
    generate_ai_response("CLARIFICATION_RESPONSE")

# 3. Chat Input
input_msg = "Please provide feedback..." if st.session_state["feedback_pending"] else "Ask about your business plan..."
if prompt := st.chat_input(input_msg, disabled=st.session_state["feedback_pending"]):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    save_to_firebase(st.session_state["current_user"], AI_CONFIG["active_model"], st.session_state["messages"],
                     "USER_PROMPT", st.session_state["session_id"])
    st.rerun()

# Feedback UI
if st.session_state["feedback_pending"]:
    st.divider()
    st.info("Did you understand the explanation?")
    c1, c2 = st.columns(2)
    c1.button("I understand!", on_click=handle_feedback, args=(True,), use_container_width=True)
    c2.button("I need more help!", on_click=handle_feedback, args=(False,), use_container_width=True)

# AI Response Trigger
if st.session_state["messages"] and st.session_state["messages"][-1]["role"] == "user" and not st.session_state[
    "feedback_pending"] and not st.session_state.get("trigger_clarification"):
    generate_ai_response("GENERATED_RESPONSE")