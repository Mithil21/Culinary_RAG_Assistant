# Author: Mithil Baria

import os
import time
import re
import streamlit as st
import torch
from assistant_core import get_assistant_response

# Fix torch watcher issue
torch.classes.__path__ = []

# Page config
st.set_page_config(
    page_title="Culinary Assistant",
    page_icon="🍛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- CSS --------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600&family=DM+Sans:wght@300;400;500&display=swap');

/* ── Reset & Base ── */
*, *::before, *::after { box-sizing: border-box; }

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background-color: #141414 !important;
    color: #E8E3DC !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 300;
}

#MainMenu, footer, header { visibility: hidden !important; }

.main .block-container {
    max-width: 780px;
    margin: 0 auto;
    padding-top: 2.5rem;
    padding-bottom: 9rem;
}

/* ══════════════════════════════
   SIDEBAR
══════════════════════════════ */
[data-testid="stSidebar"] {
    background-color: #0e0e0e !important;
    border-right: 1px solid #1e1e1e !important;
}

[data-testid="stSidebar"] * {
    color: #E8E3DC !important;
}

/* Brand header in sidebar */
[data-testid="stSidebar"] h3 {
    font-family: 'Playfair Display', serif !important;
    font-size: 1.1rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.08em !important;
    color: #C9A96E !important;
    text-transform: uppercase;
    padding: 0.5rem 0 !important;
}

/* New Chat button */
div[data-testid="stSidebar"] .stButton:first-of-type > button {
    width: 100% !important;
    background: transparent !important;
    border: 1px solid #2a2a2a !important;
    color: #9a9490 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 400 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    padding: 0.55rem 1rem !important;
    border-radius: 6px !important;
    transition: all 0.2s ease !important;
    justify-content: center !important;
    margin-bottom: 0.25rem !important;
}
div[data-testid="stSidebar"] .stButton:first-of-type > button:hover {
    border-color: #C9A96E !important;
    color: #C9A96E !important;
    background: rgba(201, 169, 110, 0.05) !important;
}

/* Sidebar chat list buttons */
div[data-testid="stSidebar"] .stButton > button {
    width: 100% !important;
    background: transparent !important;
    border: none !important;
    color: #7a756e !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.83rem !important;
    font-weight: 300 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 0.45rem 0.75rem !important;
    border-radius: 6px !important;
    transition: all 0.18s ease !important;
    letter-spacing: 0.01em !important;
}
div[data-testid="stSidebar"] .stButton > button:hover {
    background: #181818 !important;
    color: #E8E3DC !important;
}

/* ══════════════════════════════
   CHAT MESSAGES
══════════════════════════════ */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 0.75rem 0 !important;
}

/* User bubble — right aligned */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    display: flex;
    flex-direction: row-reverse;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
    background: #1e1e1e !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 18px 4px 18px 18px !important;
    padding: 0.8rem 1.15rem !important;
    margin-left: auto !important;
    max-width: 78% !important;
    font-size: 0.92rem !important;
    line-height: 1.6 !important;
    color: #E8E3DC !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageAvatarUser"] {
    display: none !important;
}

/* Assistant message */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stChatMessageContent"] {
    padding: 0.4rem 0 !important;
    max-width: 92% !important;
    font-size: 0.93rem !important;
    line-height: 1.75 !important;
    color: #D4CFC8 !important;
}

/* ── Assistant avatar — golden dot ── */
[data-testid="stChatMessageAvatarAssistant"] {
    background: #1a1a1a !important;
    border: 1px solid #C9A96E !important;
    border-radius: 50% !important;
    width: 32px !important;
    height: 32px !important;
    font-size: 14px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-shrink: 0 !important;
}

/* ── Markdown inside messages ── */
[data-testid="stChatMessageContent"] p {
    margin-bottom: 0.55rem !important;
}
[data-testid="stChatMessageContent"] strong {
    color: #E8E3DC !important;
    font-weight: 500 !important;
}
[data-testid="stChatMessageContent"] code {
    background: #1e1e1e !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 4px !important;
    padding: 0.1em 0.4em !important;
    font-size: 0.85em !important;
    color: #C9A96E !important;
}
[data-testid="stChatMessageContent"] ul,
[data-testid="stChatMessageContent"] ol {
    padding-left: 1.3rem !important;
}
[data-testid="stChatMessageContent"] li {
    margin-bottom: 0.25rem !important;
}

/* ══════════════════════════════
   ACTION BUTTONS (Retry / Edit)
══════════════════════════════ */
[data-testid="stHorizontalBlock"] .stButton > button {
    background: transparent !important;
    border: 1px solid #222222 !important;
    color: #4a4540 !important;
    border-radius: 5px !important;
    padding: 0.18rem 0.55rem !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.74rem !important;
    font-weight: 400 !important;
    letter-spacing: 0.03em !important;
    min-height: 0 !important;
    height: auto !important;
    transition: all 0.2s ease !important;
}
[data-testid="stHorizontalBlock"] .stButton > button:hover {
    background: #1a1a1a !important;
    border-color: #3a3530 !important;
    color: #9a9085 !important;
}

/* ══════════════════════════════
   CHAT INPUT
══════════════════════════════ */
[data-testid="stChatInput"] {
    background: linear-gradient(to top, #141414 80%, transparent) !important;
    padding-bottom: 2rem !important;
}
[data-testid="stChatInput"] textarea {
    background: #1a1a1a !important;
    color: #E8E3DC !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 22px !important;
    padding: 0.9rem 1.3rem !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.93rem !important;
    font-weight: 300 !important;
    transition: border-color 0.2s ease !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: #3d3830 !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #C9A96E !important;
    box-shadow: 0 0 0 2px rgba(201, 169, 110, 0.1) !important;
    outline: none !important;
}
[data-testid="stChatInput"] button {
    background: #C9A96E !important;
    border: none !important;
    border-radius: 50% !important;
    color: #141414 !important;
    transition: opacity 0.2s ease !important;
}
[data-testid="stChatInput"] button:hover {
    opacity: 0.85 !important;
}

/* ══════════════════════════════
   SPINNER
══════════════════════════════ */
[data-testid="stSpinner"] { color: #C9A96E !important; }
[data-testid="stSpinner"] > div {
    border-top-color: #C9A96E !important;
}

/* ══════════════════════════════
   PIPELINE DATA EXPANDER
══════════════════════════════ */
div[data-testid="stExpander"] {
    background: #111111 !important;
    border: 1px solid #1e1e1e !important;
    border-radius: 10px !important;
    margin-top: 0.6rem !important;
    overflow: hidden !important;
}
div[data-testid="stExpander"] summary {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.76rem !important;
    font-weight: 400 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: #5a5550 !important;
    padding: 0.6rem 0.9rem !important;
    transition: color 0.2s ease !important;
}
div[data-testid="stExpander"] summary:hover {
    color: #C9A96E !important;
}
div[data-testid="stExpander"] summary svg {
    color: #5a5550 !important;
}

/* ── Intent badge ── */
.intent-badge {
    display: inline-block;
    background: rgba(201, 169, 110, 0.1);
    border: 1px solid rgba(201, 169, 110, 0.25);
    color: #C9A96E;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    margin-bottom: 1rem;
}

/* ── Pipeline section headers ── */
.pipeline-section {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #3d3830;
    margin: 1rem 0 0.4rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid #1e1e1e;
}
.pipeline-section:first-of-type { margin-top: 0.25rem; }

/* ── Chunk cards ── */
.chunk-card {
    background: #161616;
    border: 1px solid #1e1e1e;
    border-left: 2px solid #C9A96E;
    border-radius: 6px;
    padding: 0.65rem 0.9rem;
    margin-bottom: 0.4rem;
    font-size: 0.8rem;
    color: #9a9490;
    line-height: 1.6;
    font-family: 'DM Sans', sans-serif;
    font-weight: 300;
}
.chunk-label {
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #C9A96E;
    opacity: 0.6;
    margin-bottom: 0.3rem;
}

/* ── Slot pills ── */
.slot-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin-top: 0.2rem;
}
.slot-pill {
    background: #181818;
    border: 1px solid #252525;
    border-radius: 4px;
    padding: 0.15rem 0.55rem;
    font-size: 0.74rem;
    color: #7a7570;
    font-family: 'DM Sans', sans-serif;
}
.slot-key {
    color: #4a4540;
    margin-right: 0.2rem;
}
.slot-val { color: #9a9490; }

/* ── Dish chips ── */
.dish-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin-top: 0.2rem;
}
.dish-chip {
    background: rgba(201, 169, 110, 0.07);
    border: 1px solid rgba(201, 169, 110, 0.18);
    border-radius: 4px;
    padding: 0.15rem 0.55rem;
    font-size: 0.75rem;
    color: #C9A96E;
    font-family: 'DM Sans', sans-serif;
    font-weight: 400;
}

/* ── Edit box ── */
[data-testid="stTextInput"] input {
    background: #1a1a1a !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 10px !important;
    color: #E8E3DC !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    padding: 0.65rem 1rem !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #C9A96E !important;
    box-shadow: 0 0 0 2px rgba(201, 169, 110, 0.1) !important;
}

/* ── Save / Cancel buttons in edit ── */
.stButton > button {
    font-family: 'DM Sans', sans-serif !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #222; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #2e2e2e; }
</style>
""", unsafe_allow_html=True)

# -------------------- SESSION STATE --------------------
if "chats" not in st.session_state:
    st.session_state.chats = [{"messages": [], "title": "New Chat"}]
    st.session_state.current_chat = 0

def current_chat():
    return st.session_state.chats[st.session_state.current_chat]

def current_messages():
    return current_chat()["messages"]

# -------------------- HELPER: RENDER PIPELINE DATA --------------------
def render_pipeline(metadata: dict):
    """Render intent, slots, dishes, and raw chunks in a beautiful expander."""
    if not metadata:
        return

    intent         = metadata.get("Intent", "")
    selected_dishes = metadata.get("Selected Dishes", [])
    extracted_slots = metadata.get("Extracted Slots", {})
    raw_chunks      = metadata.get("Raw Chunks", {})

    # Nothing worth showing
    if not any([intent, selected_dishes, extracted_slots, raw_chunks]):
        return

    with st.expander("⬡  Pipeline trace", expanded=False):

        # Intent badge
        if intent and intent != "Unknown":
            st.markdown(f'<div class="intent-badge">{intent}</div>', unsafe_allow_html=True)

        # Selected dishes
        if selected_dishes:
            st.markdown('<div class="pipeline-section">Matched dishes</div>', unsafe_allow_html=True)
            chips_html = "".join(f'<span class="dish-chip">{d}</span>' for d in selected_dishes)
            st.markdown(f'<div class="dish-chips">{chips_html}</div>', unsafe_allow_html=True)

        # Extracted slots
        if extracted_slots:
            st.markdown('<div class="pipeline-section">Extracted slots</div>', unsafe_allow_html=True)
            pills_html = "".join(
                f'<span class="slot-pill"><span class="slot-key">{k}:</span>'
                f'<span class="slot-val">{v}</span></span>'
                for k, v in extracted_slots.items() if v
            )
            st.markdown(f'<div class="slot-grid">{pills_html}</div>', unsafe_allow_html=True)

        # Raw chunks
        if raw_chunks:
            st.markdown('<div class="pipeline-section">Retrieved chunks</div>', unsafe_allow_html=True)

            # raw_chunks can be a dict {dish: [chunk_text, ...]} or a list
            if isinstance(raw_chunks, dict):
                for dish_name, chunks in raw_chunks.items():
                    if not chunks:
                        continue
                    chunk_list = chunks if isinstance(chunks, list) else [chunks]
                    for idx, chunk in enumerate(chunk_list):
                        label = f"{dish_name} · {idx + 1}" if len(chunk_list) > 1 else dish_name
                        text  = chunk if isinstance(chunk, str) else str(chunk)
                        st.markdown(
                            f'<div class="chunk-card">'
                            f'<div class="chunk-label">{label}</div>'
                            f'{text}'
                            f'</div>',
                            unsafe_allow_html=True
                        )
            elif isinstance(raw_chunks, list):
                for idx, chunk in enumerate(raw_chunks):
                    text = chunk if isinstance(chunk, str) else str(chunk)
                    st.markdown(
                        f'<div class="chunk-card">'
                        f'<div class="chunk-label">Chunk {idx + 1}</div>'
                        f'{text}'
                        f'</div>',
                        unsafe_allow_html=True
                    )

# -------------------- SIDEBAR --------------------
with st.sidebar:
    st.markdown("<h3 style='text-align:center; margin-top:0;'>🍛 Culinary Assistant</h3>", unsafe_allow_html=True)

    if st.button("➕  New Chat"):
        if len(current_messages()) > 0:
            st.session_state.chats.append({"messages": [], "title": "New Chat"})
            st.session_state.current_chat = len(st.session_state.chats) - 1
            st.rerun()

    st.markdown("<hr style='margin: 0.6rem 0; border-color: #1e1e1e;'/>", unsafe_allow_html=True)

    for i, chat in enumerate(st.session_state.chats):
        title = chat["title"]
        label = f"{'● ' if i == st.session_state.current_chat else '  '}{title}"
        if st.button(label, key=f"sidebar_btn_{i}"):
            st.session_state.current_chat = i
            st.rerun()

# -------------------- RENDER CHAT --------------------
for i, msg in enumerate(current_messages()):
    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🍛"):
        st.markdown(msg["content"])

        # Re-render stored pipeline data
        if msg.get("metadata"):
            render_pipeline(msg["metadata"])

        if msg["role"] == "assistant":
            col1, col2, _ = st.columns([1, 1, 6])
            with col1:
                if st.button("🔁 Retry", key=f"retry_{i}"):
                    st.session_state.retry_index = i
                    st.rerun()
            with col2:
                if st.button("✏️ Edit", key=f"edit_{i}"):
                    st.session_state.edit_index = i
                    st.rerun()

# -------------------- INPUT --------------------
prompt = st.chat_input("Message Culinary Assistant...")

# -------------------- EDIT MESSAGE LOGIC --------------------
if "edit_index" in st.session_state:
    idx = st.session_state.edit_index
    msg = current_messages()[idx - 1]

    with st.container():
        st.markdown("### Edit your message:")
        new_text = st.text_input("Message", value=msg["content"], label_visibility="collapsed")

        col1, col2 = st.columns([1, 8])
        with col1:
            if st.button("Save"):
                msg["content"] = new_text
                del st.session_state.edit_index
                st.rerun()
        with col2:
            if st.button("Cancel"):
                del st.session_state.edit_index
                st.rerun()

# -------------------- HANDLE RETRY --------------------
if "retry_index" in st.session_state:
    idx = st.session_state.retry_index
    user_msg = current_messages()[idx - 1]["content"]
    current_messages().pop(idx)
    prompt = user_msg
    del st.session_state.retry_index

# -------------------- PROCESS MESSAGE --------------------
if prompt:
    current_messages().append({"role": "user", "content": prompt})

    if current_chat()["title"] == "New Chat":
        current_chat()["title"] = prompt[:22] + "..." if len(prompt) > 22 else prompt

    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🍛"):
        with st.spinner("Cooking up an answer..."):
            result = get_assistant_response(prompt, current_messages()[:-1])
            answer = result.get("answer", "I'm sorry, something went wrong.")

            metadata = {
                "Intent": result.get("intent", "Unknown"),
                "Selected Dishes": result.get("selected_dishes", []),
                "Extracted Slots": result.get("extracted", {}),
                "Raw Chunks": result.get("chunks_used", {})
            }

        # Streaming effect
        placeholder = st.empty()
        streamed_text = ""
        tokens = re.split(r'(\s+)', answer)

        for token in tokens:
            streamed_text += token
            placeholder.markdown(streamed_text + "▌")
            time.sleep(0.01)

        placeholder.markdown(streamed_text)

        # Show pipeline trace below the answer
        render_pipeline(metadata)

    current_messages().append({
        "role": "assistant",
        "content": answer,
        "metadata": metadata
    })