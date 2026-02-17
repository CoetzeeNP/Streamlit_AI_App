import streamlit as st
from datetime import datetime
from ai_strategy import AIManager
from database import save_to_firebase, update_previous_feedback
from streamlit_cookies_controller import CookieController

# Setup & Configuration
st.set_page_config(layout="wide", page_title="AI-frikaans Assistant")
#controller = CookieController()

# Custom CSS
st.markdown("""
    <style>
    div[data-testid="stColumn"]:nth-of-type(1) button { background-color: #28a745 !important; color: white !important; }
    div[data-testid="stColumn"]:nth-of-type(2) button { background-color: #dc3545 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

AI_CONFIG = {
    "active_model": "gemini-3-pro-preview",
    "system_instruction": "You are an Afrikaans assistant. You must make sure you are not using Dutch or German in your responses. Structure your responses so they are easily readable. You must always explain the concept in both English and Afrikaans. Make use of STOMPI regarding sentence structure."
}

# State Initialization
if "session_id" not in st.session_state:
    st.session_state["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")
if "messages" not in st.session_state: st.session_state["messages"] = []
if "feedback_pending" not in st.session_state: st.session_state["feedback_pending"] = False
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "current_user" not in st.session_state: st.session_state["current_user"] = None

# Persistence & Auth
AUTHORIZED_IDS = st.secrets["AUTHORIZED_STUDENT_LIST"]
#cached_uid = controller.get('student_auth_id')

#if cached_uid and not st.session_state["authenticated"]:
#    if cached_uid in AUTHORIZED_IDS:
#        st.session_state.update({"authenticated": True, "current_user": cached_uid})

# # Helper Functions
# @st.cache_data(ttl=1800)
# def get_cached_history_keys(user_id):
#     db_ref = get_firebase_connection()
#     return db_ref.child("logs").child(str(user_id).replace(".", "_")).get(shallow=True)
#
# # Updated Helper for Previews
# @st.cache_data(ttl=1800)
# def get_cached_preview(user_id, session_key):
#     try:
#         db_ref = get_firebase_connection()
#         clean_uid = str(user_id).replace(".", "_")
#         # Fetches just the first message (index 0) to keep it lightweight
#         return db_ref.child("logs").child(clean_uid).child(session_key).child("transcript").child("0").get()
#     except Exception:
#         return None

# Unified function to get AI response, stream to UI, and log to DB.
# Consolidated to prevent duplicate messages and redundant reruns.
def generate_ai_response(interaction_type):

    with st.chat_message("assistant"):
        with st.container(border=True):
            st.markdown("**AI-frikaans Assistant:**")
            ai_manager = AIManager(AI_CONFIG["active_model"])

            full_res = ""
            actual_model = AI_CONFIG["active_model"]  # Default starting point
            placeholder = st.empty()

            # The generator yields (token, model_label)
            # This handles the failover internally
            for chunk, model_label in ai_manager.get_response_stream(
                    st.session_state["messages"],
                    AI_CONFIG["system_instruction"]
            ):
                full_res += chunk
                actual_model = model_label  # Updates if failover occurs
                placeholder.markdown(full_res + "▌")

            placeholder.markdown(full_res)  # Remove trailing cursor

    st.session_state["messages"].append({"role": "assistant", "content": full_res})

    st.session_state["last_model_used"] = actual_model

    st.session_state["feedback_pending"] = True

    save_to_firebase(
        st.session_state["current_user"],
        actual_model,
        st.session_state["messages"],
        interaction_type,
        st.session_state["session_id"]
    )
    st.rerun()


# def trigger_load_chat(user_id, session_key):
#     if st.session_state.get("session_id") == session_key:
#         return  # Do nothing, it's already loaded
#
#     load_selected_chat(user_id, session_key)
#     st.session_state["session_id"] = session_key
#     st.session_state["feedback_pending"] = False  # Reset UI state


# Handles the states when users click either the "I understand" or "I need more help"
def handle_feedback(understood: bool):
    # Set this immediately to block concurrent clicks
    st.session_state["processing_feedback"] = True
    st.session_state["feedback_pending"] = False

    with st.spinner("Logging feedback..."):
        user_id = st.session_state["current_user"]
        session_id = st.session_state["session_id"]
        model_to_log = st.session_state.get("last_model_used", AI_CONFIG["active_model"])

        if understood:
            save_to_firebase(user_id, model_to_log, st.session_state["messages"],
                             "GENERATED_RESPONSE", session_id, feedback_value=True)
        else:
            clarification_text = "I don't understand the previous explanation. Please break it down further."
            st.session_state["messages"].append({"role": "user", "content": clarification_text})
            update_previous_feedback(user_id, session_id, st.session_state["messages"], False)
            save_to_firebase(user_id, model_to_log, st.session_state["messages"],
                             "CLARIFICATION_REQUEST", session_id, feedback_value=None)
            st.session_state["trigger_clarification"] = True

    # Reset lock and force UI refresh
    st.session_state["processing_feedback"] = False

###########################
###        Sidebar      ###
###########################
with st.sidebar:
    st.image("icdf.png")
    if not st.session_state["authenticated"]:
        st.info("Enter your username and password below!")
        u_pass = st.text_input("Enter Username",)
        u_id = st.text_input("Enter Password", type="password")
        if st.button("Login", use_container_width=True) and u_id in AUTHORIZED_IDS:
            #controller.set('student_auth_id', u_id)
            st.session_state.update({"authenticated": True, "current_user": u_id})
            st.rerun()
    else:
        st.write(f"**Logged in as:** {st.session_state['current_user']}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Logout", use_container_width=True):
                st.cache_data.clear()
                st.session_state.clear()
                st.rerun()
        with col2:
            st.link_button("Feedback",
                           "https://forms.office.com/Pages/ResponsePage.aspx?id=...",
                           use_container_width=True)

        st.divider()
        # st.subheader("Chat History")
        # all_logs = get_cached_history_keys(st.session_state['current_user'])
        #
        # if all_logs:
        #     # Create a mapping of Pretty Date -> DB Key
        #     display_options = {}
        #     for k in sorted(all_logs.keys(), reverse=True):
        #         try:
        #             dt_obj = datetime.strptime(k, "%Y%m%d_%H%M%S")
        #             clean_date = dt_obj.strftime("%b %d, %Y - %I:%M %p")
        #         except:
        #             clean_date = k
        #         display_options[clean_date] = k
        #
        #     sel_display = st.selectbox("Select a previous session:", options=list(display_options.keys()))
        #     sel_key = display_options[sel_display]
        #
        #     # Re-added Preview Logic
        #     preview_msg = get_cached_preview(st.session_state['current_user'], sel_key)
        #
        #     with st.expander("🔍 Preview Session"):
        #         if preview_msg:
        #             role = "User" if preview_msg.get("role") == "user" else "Assistant"
        #             content = preview_msg.get("content", "No content available")
        #             st.markdown(f"**{role}:** {content[:100]}...")
        #         else:
        #             st.info("No preview available.")
        #
        #     if st.button("🔄 Load & Continue", type="primary", use_container_width=True,
        #                  on_click=trigger_load_chat,
        #                  args=(st.session_state['current_user'], sel_key)):
        #         st.rerun()

        if st.button("New Chat", use_container_width=True):
            st.session_state.update(
                {"messages": [], "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"), "feedback_pending": False})
            st.rerun()
###########################
###        Sidebar      ###
###########################


###########################
###        Main      ###
###########################
st.image("combined_logo.jpg")
st.title("AIfrikaans Assistant")

if not st.session_state["authenticated"]:
    st.warning("Please login via the sidebar.")
    st.info("Welcome to the AIfrikaans Assistant Streamlit App!\n You are welcome to ask all your afrikaans related questions here. \n\n"
            "All your prompts and generated responses are recorded while using the app. You will be asked for feedback after each questions. If you answer using the \"I dont understand button\", the large language model will try nad be more detailed in its explanation to try assist you learn!"
            "\n\nPlease remember that large language models are not perfect and are prone to hallucinations or representing false information as fact quite convincingly")
    st.stop()

# 1. Display Chat History
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        with st.container(border=True):
            label = st.session_state["current_user"] if msg["role"] == "user" else "Assistant"
            st.markdown(f"**{label}:**\n\n{msg['content']}")

if st.session_state.get("trigger_clarification"):
    st.session_state["trigger_clarification"] = False
    # This explicitly logs the NEXT AI message as a CLARIFICATION_RESPONSE
    generate_ai_response("CLARIFICATION_RESPONSE")

# 3. Chat Input
input_msg = "Please provide feedback..." if st.session_state["feedback_pending"] else "Ask about your business plan..."
if prompt := st.chat_input(input_msg, disabled=st.session_state["feedback_pending"]):
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # Immediately log the user's manual input
    save_to_firebase(
        st.session_state["current_user"],
        AI_CONFIG["active_model"],
        st.session_state["messages"],
        "USER_PROMPT",
        st.session_state["session_id"]
    )
    st.rerun()

# Feedback UI
if st.session_state["feedback_pending"]:
    st.divider()
    st.info("Did you understand the explanation?")

    is_disabled = st.session_state.get("processing_feedback", False)

    # Use the length of messages to create a unique ID for this specific feedback instance
    msg_count = len(st.session_state["messages"])

    c1, c2 = st.columns(2)
    c1.button(
        "I understand!",
        on_click=handle_feedback,
        args=(True,),
        use_container_width=True,
        disabled=is_disabled,
        key=f"btn_yes_{msg_count}"  # Unique key prevents state carry-over
    )
    c2.button(
        "I need more help!",
        on_click=handle_feedback,
        args=(False,),
        use_container_width=True,
        disabled=is_disabled,
        key=f"btn_no_{msg_count}"  # Unique key prevents state carry-over
    )


# Generate Standard Response
# This only fires if the last message is from a user and it wasn't a clarification trigger
if (
    st.session_state["messages"]
    and st.session_state["messages"][-1]["role"] == "user"
    and not st.session_state["feedback_pending"]
    and not st.session_state.get("trigger_clarification") # Add this check
):
    generate_ai_response("GENERATED_RESPONSE")
###########################
###        Main      ###
###########################