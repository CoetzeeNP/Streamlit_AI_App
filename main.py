import streamlit as st
from datetime import datetime
from ai_strategy import AIManager
from database import save_to_supabase, get_supabase_client

st.set_page_config(layout="wide", page_title="AI-frikaans Assistant")

# Custom CSS
st.markdown("""
    <style>
    div[data-testid="stColumn"]:nth-of-type(1) button { background-color: #28a745 !important; color: white !important; }
    div[data-testid="stColumn"]:nth-of-type(2) button { background-color: #dc3545 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

AI_CONFIG = {
    "active_model": "ChatGPT 5.2",
    "system_instruction": "You are an Afrikaans assistant. You must make sure you are not using Dutch or German in your responses. Use html to help manage your responses format. You must always explain the concept in Afrikaans unless requested by the user. Make use of STOMPI regarding sentence structure."
}

# =========================
# STATE INITIALIZATION
# =========================
if "session_id" not in st.session_state:
    st.session_state["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")

defaults = {
    "messages": [],
    "feedback_pending": False,
    "authenticated": False,
    "current_user": None,
    "awaiting_clarification": False,
    "is_generating": False
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# =========================
# AI RESPONSE FUNCTION
# =========================
def generate_ai_response(interaction_type):
    st.session_state["is_generating"] = True
    st.session_state["feedback_pending"] = False

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        actual_model = AI_CONFIG["active_model"]
        ai_manager = AIManager(AI_CONFIG["active_model"])

        with st.spinner("Besig om te dink..."):
            for chunk, model_label in ai_manager.get_response_stream(
                    st.session_state["messages"],
                    AI_CONFIG["system_instruction"]
            ):
                full_res += chunk
                actual_model = model_label
                placeholder.markdown(full_res, unsafe_allow_html=True)

    st.session_state["messages"].append({"role": "assistant", "content": full_res})
    st.session_state["last_model_used"] = actual_model
    st.session_state["feedback_pending"] = True
    st.session_state["is_generating"] = False

    last_row_id = save_to_supabase(
        st.session_state["current_user"],
        actual_model,
        st.session_state["messages"],
        interaction_type,
        st.session_state["session_id"]
    )

    st.session_state["last_log_id"] = last_row_id
    st.rerun()


# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.image("icdf.png")

    if not st.session_state["authenticated"]:
        st.info("Enter your username and password below!")

        username = st.text_input("Enter Username").strip()
        password = st.text_input("Enter Password", type="password").strip()

        if st.button("Login", use_container_width=True):
            if username in st.secrets.get("credentials", {}) and st.secrets["credentials"][username] == password:
                st.session_state.update({"authenticated": True, "current_user": username})
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    else:
        st.write(f"Logged in as: {st.session_state['current_user']}")

        col1, col2 = st.columns(2)
        if col1.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        col2.link_button("Feedback", "https://forms.office.com/r/zCqVE7mGzu", use_container_width=True)

        st.divider()

        if st.button("New Chat", use_container_width=True):
            st.session_state.update({
                "messages": [],
                "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "feedback_pending": False,
                "awaiting_clarification": False
            })
            st.rerun()


# =========================
# MAIN UI
# =========================
st.image("combined_logo.jpg")
st.title("AI-frikaans Assistant")

if not st.session_state["authenticated"]:
    st.warning("Please login via the sidebar.")
    st.info(
        "Welcome to the AIfrikaans Assistant Streamlit App!\n You are welcome to ask all your afrikaans related questions here. \n\n"

        "All your prompts and generated responses are recorded while using the app. You will be asked for feedback after each questions. "

        "If you click the \"I need more help\" button, the large language model will try and be more detailed in its explanation to try assist you learn!"
        
        "If you need to translate the response into English click on the \"Translate to English\" button"
        
        "If you need assistance from a tutor click on the \"Ask Tutor\" button"
        
        "Do not insert any personal or self-identifying information into the model!"

        "\n\nPlease remember that large language models are not perfect and are prone to hallucinations or representing false information as fact quite convincingly")

    st.stop()


# =========================
# HANDLE FEEDBACK UPDATE
# =========================
if "pending_feedback_value" in st.session_state:
    understood = st.session_state.pop("pending_feedback_value")
    log_id = st.session_state.get("last_log_id")

    if log_id:
        supabase = get_supabase_client()
        supabase.table("chat_logs").update({"user_understood": understood}).eq("id", log_id).execute()


# =========================
# DISPLAY CHAT HISTORY
# =========================
for msg in st.session_state["messages"]:
    role_label = "Assistant" if msg["role"] == "assistant" else st.session_state["current_user"]
    with st.chat_message(msg["role"]):
        st.write(f"**{role_label}:**")
        st.markdown(msg["content"], unsafe_allow_html=True)


# =========================
# CHAT INPUT (UPDATED)
# =========================
if st.session_state.get("awaiting_clarification"):
    input_msg = "Ask your follow-up question..."
elif st.session_state["feedback_pending"]:
    input_msg = "Please provide feedback..."
else:
    input_msg = "Ask your afrikaans question here"

# =========================
# DYNAMIC INPUT MESSAGE
# =========================
if st.session_state.get("awaiting_tutor_request"):
    input_msg = "What would you like to ask the tutor?"
elif st.session_state.get("awaiting_clarification"):
    input_msg = "What would you like me to explain further?"
else:
    input_msg = "Type your message here..."


prompt = st.chat_input(
    input_msg,
    disabled=st.session_state["feedback_pending"]
    and not st.session_state.get("awaiting_clarification")
    and not st.session_state.get("awaiting_tutor_request")
)

if prompt:
    interaction_type = "USER_PROMPT"

    # =========================
    # 👨‍🏫 TUTOR REQUEST FLOW (FIRST)
    # =========================
    if st.session_state.get("awaiting_tutor_request"):
        interaction_type = "TUTOR_REQUEST"
        st.session_state["awaiting_tutor_request"] = False

        log_id = st.session_state.get("last_log_id")

        if log_id:
            supabase = get_supabase_client()
            supabase.table("chat_logs").update({
                "ask_tutor": True,
                "user_understood": False,
                "tutor_request_text": prompt
            }).eq("id", log_id).execute()

        # 1. Add the user's request to the session
        st.session_state["messages"].append({
            "role": "user",
            "content": prompt
        })

        # 2. Add the confirmation assistant message
        confirmation_msg = "Jou versoek is gestuur. Roep asseblief nou jou tutor vir verdere hulp."
        st.session_state["messages"].append({
            "role": "assistant",
            "content": confirmation_msg
        })

        # 3. Save the final state to Supabase
        save_to_supabase(
            st.session_state["current_user"],
            AI_CONFIG["active_model"],
            st.session_state["messages"],
            interaction_type,
            st.session_state["session_id"]
        )

        # 4. Rerun to show messages and STOP the script (prevents AI generation)
        st.rerun()

    # =========================
    # 📚 CLARIFICATION FLOW
    # =========================
    elif st.session_state.get("awaiting_clarification"):
        interaction_type = "CLARIFICATION_REQUEST"
        st.session_state["awaiting_clarification"] = False

        if not prompt.strip():
            prompt = "Please explain the previous response in more detail."

    # =========================
    # NORMAL FLOW
    # =========================
    st.session_state["messages"].append({
        "role": "user",
        "content": prompt
    })

    save_to_supabase(
        st.session_state["current_user"],
        AI_CONFIG["active_model"],
        st.session_state["messages"],
        interaction_type,
        st.session_state["session_id"]
    )

    st.rerun()

# =========================
# FEEDBACK BUTTONS
# =========================
if (
    st.session_state["messages"]
    and st.session_state["messages"][-1]["role"] == "assistant"
    and st.session_state["feedback_pending"]
    and not st.session_state["is_generating"]
):
    st.info("Please provide feedback or request help!")

    c1, c2, c3, c4 = st.columns(4)

    # ✅ UNDERSTOOD
    if c1.button("I understand!", use_container_width=True):
        log_id = st.session_state.get("last_log_id")

        if log_id:
            supabase = get_supabase_client()
            supabase.table("chat_logs").update({
                "user_understood": True
            }).eq("id", log_id).execute()

        st.session_state["feedback_pending"] = False
        st.rerun()

    # ❌ NEED HELP
    if c2.button("I need more help!", use_container_width=True):
        log_id = st.session_state.get("last_log_id")

        if log_id:
            supabase = get_supabase_client()
            supabase.table("chat_logs").update({
                "user_understood": False
            }).eq("id", log_id).execute()

        st.session_state["awaiting_clarification"] = True
        st.session_state["feedback_pending"] = False
        st.rerun()

    # 🌍 TRANSLATE
    if c3.button("Translate to English", use_container_width=True):
        log_id = st.session_state.get("last_log_id")

        if log_id:
            supabase = get_supabase_client()
            supabase.table("chat_logs").update({
                "translation_requested": True
            }).eq("id", log_id).execute()

        st.session_state["messages"].append({
            "role": "user",
            "content": "Please translate your previous response into English."
        })

        save_to_supabase(
            st.session_state["current_user"],
            st.session_state.get("last_model_used"),
            st.session_state["messages"],
            "TRANSLATE_REQUEST",
            st.session_state["session_id"]
        )

        st.session_state["feedback_pending"] = False
        st.rerun()

    # 👨‍🏫 ASK TUTOR BUTTON ONLY (no prompt logic here!)
    if c4.button("Ask Tutor", use_container_width=True):
        st.session_state["awaiting_tutor_request"] = True
        st.session_state["feedback_pending"] = False
        st.rerun()

# =========================
# GENERATE RESPONSE
# =========================
if (
    st.session_state["messages"]
    and st.session_state["messages"][-1]["role"] == "user"
    and not st.session_state["feedback_pending"]
):
    generate_ai_response("GENERATED_RESPONSE")