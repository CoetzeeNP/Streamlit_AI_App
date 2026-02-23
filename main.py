import streamlit as st
from datetime import datetime
from ai_strategy import AIManager
from database import save_to_firebase, update_previous_feedback

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


#if cached_uid and not st.session_state["authenticated"]:
#    if cached_uid in AUTHORIZED_IDS:
#        st.session_state.update({"authenticated": True, "current_user": cached_uid})


# Unified function to get AI response, stream to UI, and log to DB.
def generate_ai_response(interaction_type):
    st.session_state["is_generating"] = True
    st.session_state["feedback_pending"] = False

    with st.chat_message("assistant"):
        with st.container(border=True):
            st.markdown("**AI-frikaans Assistant:**")
            ai_manager = AIManager(AI_CONFIG["active_model"])

            full_res = ""
            actual_model = AI_CONFIG["active_model"]
            placeholder = st.empty()

            # Add the Streamlit spinner right here
            with st.spinner("Dink aan jou vraag..."):  # "Thinking..." in Afrikaans
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

###########################
###        Sidebar      ###
###########################
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

with st.sidebar:
    st.image("icdf.png")

    if not st.session_state["authenticated"]:
        st.info("Enter your username and password below!")

        # Added .strip() to prevent invisible spaces from breaking the login
        username = st.text_input("Enter Username").strip()
        password = st.text_input("Enter Password", type="password").strip()

        if st.button("Login", use_container_width=True):
            # Using .get() prevents a crash if the credentials block isn't found
            if username in st.secrets.get("credentials", {}) and st.secrets["credentials"][username] == password:
                st.session_state.update({"authenticated": True, "current_user": username})
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    else:
        st.write(f"Logged in as: {st.session_state['current_user']}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Logout", use_container_width=True):
                st.cache_data.clear()
                st.session_state.clear()
                st.rerun()
        with col2:
            st.link_button("Feedback", "https://forms.office.com/Pages/ResponsePage.aspx?id=...",
                           use_container_width=True)

        st.divider()

        if st.button("New Chat", use_container_width=True):
            st.session_state.update({
                "messages": [],
                "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "feedback_pending": False
            })
            st.rerun()
###########################
###        Sidebar      ###
###########################


###########################
###        Main         ###
###########################
st.image("combined_logo.jpg")
st.title("AI-frikaans Assistant")

if not st.session_state["authenticated"]:
    st.warning("Please login via the sidebar.")
    st.info("Welcome to the AIfrikaans Assistant Streamlit App!\n You are welcome to ask all your afrikaans related questions here. \n\n"
            "All your prompts and generated responses are recorded while using the app. You will be asked for feedback after each questions. If you answer using the \"I dont understand button\", the large language model will try nad be more detailed in its explanation to try assist you learn!"
            "\n\nPlease remember that large language models are not perfect and are prone to hallucinations or representing false information as fact quite convincingly"
            "\n\nPlease remember that AI are prone to mistakes and hallucinations!")
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
input_msg = "Please provide feedback..." if st.session_state["feedback_pending"] else "Ask your afrikaans question here"
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
# 5. Feedback UI — only shown when a response is complete and not currently generating
if (
    st.session_state["messages"]
    and st.session_state["messages"][-1]["role"] == "assistant"
    and st.session_state["feedback_pending"]
    and not st.session_state.get("is_generating", False)
):
    st.info("Please provide feedback on the generated response!")
    with st.form("feedback_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns(2)

        understood = c1.form_submit_button("I understand!", use_container_width=True)
        not_understood = c2.form_submit_button("I need more help!", use_container_width=True)

        if understood:
            st.session_state["feedback_pending"] = False
            st.session_state["pending_feedback_value"] = True
            st.rerun()

        if not_understood:
            st.session_state["feedback_pending"] = False
            st.session_state["pending_feedback_value"] = False
            st.rerun()

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