# Author: Mithil Baria
import streamlit as st
from assistant_core import get_assistant_response

st.set_page_config(
    page_title="South Asian Culinary Assistant",
    page_icon="🍛",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* ── Global dark background ── */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background-color: #212121 !important;
        color: #ececec !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #171717 !important;
        border-right: 1px solid #2f2f2f;
    }
    [data-testid="stSidebar"] * { color: #ececec !important; }

    /* ── Hide default header/footer ── */
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Chat messages ── */
    [data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0.5rem 0 !important;
    }

    /* ── User bubble ── */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background-color: #2f2f2f !important;
        border-radius: 12px !important;
        padding: 0.75rem 1rem !important;
        margin: 0.25rem 0 !important;
    }

    /* ── Input bar ── */
    [data-testid="stChatInput"] textarea {
        background-color: #2f2f2f !important;
        color: #ececec !important;
        border: 1px solid #3f3f3f !important;
        border-radius: 12px !important;
        font-size: 1rem !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: #10a37f !important;
        box-shadow: 0 0 0 2px rgba(16,163,127,0.3) !important;
    }

    /* ── New Chat button ── */
    div[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        background-color: #2f2f2f;
        color: #ececec;
        border: 1px solid #3f3f3f;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-size: 0.9rem;
        text-align: left;
        transition: background 0.2s;
    }
    div[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #3f3f3f;
        border-color: #10a37f;
    }

    /* ── Markdown text colour ── */
    .stMarkdown, .stMarkdown p, .stMarkdown li { color: #ececec !important; }

    /* ── Scrollable chat area ── */
    .main .block-container {
        max-width: 780px;
        margin: auto;
        padding-top: 1rem;
        padding-bottom: 6rem;
    }

    /* ── Spinner ── */
    [data-testid="stSpinner"] { color: #10a37f !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🍛 Culinary Assistant")
    st.markdown("---")
    if st.button("✏️  New Chat"):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.markdown(
        "<small style='color:#666'>Powered by FAISS · Llama 3 · Qwen 0.5B</small>",
        unsafe_allow_html=True
    )

# ── Session state ─────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Welcome screen (shown when no messages) ───────────────
if not st.session_state.messages:
    st.markdown(
        """
        <div style='text-align:center; padding: 4rem 0 2rem 0;'>
            <div style='font-size:3rem;'>🍛</div>
            <h2 style='color:#ececec; font-weight:600; margin:0.5rem 0;'>South Asian Culinary Assistant</h2>
            <p style='color:#888; font-size:1rem;'>Ask me for recipes, dish suggestions, or what to cook with your ingredients.</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    cols = st.columns(2)
    suggestions = [
        "🍗  How do I make Butter Chicken?",
        "🥗  Suggest a quick vegetarian dish",
        "🌶️  Give me a spicy non-veg recipe",
        "🍚  What can I cook with rice and lentils?",
    ]
    for i, s in enumerate(suggestions):
        if cols[i % 2].button(s, use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": s.split("  ", 1)[1]})
            st.rerun()

# ── Render chat history ───────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🍛"):
        st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────
if prompt := st.chat_input("Message Culinary Assistant..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)

    chat_history = st.session_state.messages[:-1]

    with st.chat_message("assistant", avatar="🍛"):
        with st.spinner(""):
            result = get_assistant_response(prompt, chat_history)
            answer = result.get("answer", "Sorry, something went wrong.")
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
