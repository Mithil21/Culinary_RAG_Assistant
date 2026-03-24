import streamlit as st
import sys
import os

# All files (assistant_core.py, faiss_index/) live in the same folder as this script
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

st.set_page_config(
    page_title="South Asian Culinary Assistant",
    page_icon="🍛",
    layout="centered",
)

st.title("🍛 South Asian Culinary Assistant")
st.caption("Powered by LangGraph · FAISS · Qwen2.5-0.5B")

# ── Load the LangGraph app once per session ──────────────────────────────────
@st.cache_resource(show_spinner="Loading AI models (first run may take ~60s)…")
def load_assistant():
    from assistant_core import get_assistant_response
    return get_assistant_response

get_response = load_assistant()

# ── Session state for chat history ───────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "langgraph_history" not in st.session_state:
    st.session_state.langgraph_history = []

# ── Sidebar controls ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🗑️ New Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.langgraph_history = []
        st.rerun()
    st.markdown("---")
    st.markdown("**About**")
    st.markdown(
        "This assistant specialises in **South Asian cuisine** only. "
        "Ask for recipes, ingredients, or dish suggestions!"
    )

# ── Render existing chat messages ────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask me about a South Asian dish…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            result = get_response(prompt, st.session_state.langgraph_history)
        answer = result.get("answer", "Sorry, I encountered an error.")
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.langgraph_history.append({"role": "user",      "content": prompt})
    st.session_state.langgraph_history.append({"role": "assistant", "content": answer})
