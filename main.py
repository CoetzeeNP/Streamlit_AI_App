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


# Unified function to get AI response, stream to UI, and log to DB.
def generate_ai_response(interaction_type):
    st.rerun()
    st.session_state["is_generating"] = True
    st.session_state["feedback_pending"] = False

    with st.chat_message("assistant"):
        with st.container(border=True):
            st.markdown("**AI-frikaans Assistant:**")
            ai_manager = AIManager(AI_CONFIG["active_model"])

            full_res = ""
            actual_model = AI_CONFIG["active_model"]
            placeholder = st.empty()

            for chunk, model_label in ai_manager.get_response_stream(
                    st.session_state["messages"],
                    AI_CONFIG["system_instruction"]
            ):
                full_res += chunk
                actual_model = model_label
                placeholder.markdown(full_res + "▌")

            placeholder.markdown(full_res)
    st.session_state["messages"].append({"role": "assistant", "content": full_res})
    st.session_state["last_model_used"] = actual_model
    st.session_state["feedback_pending"] = True
    st.session_state["is_generating"] = False

    save_to_firebase(
        st.session_state["current_user"],
        actual_model,
        st.session_state["messages"],
        interaction_type,
        st.session_state["session_id"]
    )
    st.rerun()


# Callback: ONLY sets a flag — no heavy logic, no st.rerun().
# Streamlit automatically reruns the full script after any on_click callback,
# so the main body below will pick up "pending_feedback_value" and do the work.
def handle_feedback(understood: bool):
    st.session_state["feedback_pending"] = False
    st.session_state["pending_feedback_value"] = understood


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

        if st.button("New Chat", use_container_width=True):
            st.session_state.update(
                {"messages": [], "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"), "feedback_pending": False})
            st.rerun()
###########################
###        Sidebar      ###
###########################


###########################
###        Main         ###
###########################
st.image("combined_logo.jpg")
st.title("AIfrikaans Assistant")

if not st.session_state["authenticated"]:
    st.warning("Please login via the sidebar.")
    st.info("Welcome to the AIfrikaans Assistant Streamlit App!\n You are welcome to ask all your afrikaans related questions here. \n\n"
            "All your prompts and generated responses are recorded while using the app. You will be asked for feedback after each questions. If you answer using the \"I dont understand button\", the large language model will try nad be more detailed in its explanation to try assist you learn!"
            "\n\nPlease remember that large language models are not perfect and are prone to hallucinations or representing false information as fact quite convincingly")
    st.stop()

# 1. Process pending feedback FIRST (before rendering anything else).
#    This block runs during the automatic rerun that follows the on_click callback.
#    At this point feedback_pending is already False (set in handle_feedback),
#    so the feedback buttons will not render this cycle — no duplicate UI.
if "pending_feedback_value" in st.session_state:
    understood = st.session_state.pop("pending_feedback_value")  # consume the flag

    user_id = st.session_state["current_user"]
    session_id = st.session_state["session_id"]
    model_to_log = st.session_state.get("last_model_used", AI_CONFIG["active_model"])

    if understood:
        save_to_firebase(
            user_id, model_to_log, st.session_state["messages"],
            "GENERATED_RESPONSE", session_id, feedback_value=True
        )
    else:
        clarification_text = "I don't understand the previous explanation. Please break it down further."
        st.session_state["messages"].append({"role": "user", "content": clarification_text})
        update_previous_feedback(user_id, session_id, st.session_state["messages"], False)
        save_to_firebase(
            user_id, model_to_log, st.session_state["messages"],
            "CLARIFICATION_REQUEST", session_id, feedback_value=None
        )

        st.session_state["trigger_clarification"] = True

# 2. Display Chat History
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        with st.container(border=True):
            label = st.session_state["current_user"] if msg["role"] == "user" else "Assistant"
            st.markdown(f"**{label}:**\n\n{msg['content']}")

# 3. Trigger clarification AI response if flagged
if st.session_state.get("trigger_clarification"):
    st.session_state["trigger_clarification"] = False
    generate_ai_response("CLARIFICATION_RESPONSE")

# 4. Chat Input
input_msg = "Please provide feedback..." if st.session_state["feedback_pending"] else "Ask about your business plan..."
if prompt := st.chat_input(input_msg, disabled=st.session_state["feedback_pending"]):
    st.session_state["messages"].append({"role": "user", "content": prompt})

    save_to_firebase(
        st.session_state["current_user"],
        AI_CONFIG["active_model"],
        st.session_state["messages"],
        "USER_PROMPT",
        st.session_state["session_id"]
    )
    st.rerun()

# 5. Feedback UI — only shown when a response is complete and not currently generating
if (
        st.session_state["messages"]
        and st.session_state["messages"][-1]["role"] == "assistant"
        and st.session_state["feedback_pending"]
        and not st.session_state.get("is_generating", False)
):
    st.divider()
    st.info("Did you understand the explanation?")

    msg_count = len(st.session_state["messages"])
    c1, c2 = st.columns(2)

    c1.button(
        "I understand!",
        on_click=handle_feedback,
        args=(True,),
        use_container_width=True,
        key=f"btn_yes_{msg_count}"
    )
    c2.button(
        "I need more help!",
        on_click=handle_feedback,
        args=(False,),
        use_container_width=True,
        key=f"btn_no_{msg_count}"
    )


# 6. Generate Standard Response
if (
    st.session_state["messages"]
    and st.session_state["messages"][-1]["role"] == "user"
    and not st.session_state["feedback_pending"]
    and not st.session_state.get("trigger_clarification")
):
    generate_ai_response("GENERATED_RESPONSE")
###########################
###        Main         ###
###########################