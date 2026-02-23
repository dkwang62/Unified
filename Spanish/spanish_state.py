# spanish_state.py (v7.0 - Streamlit Cloud Compatible)
# Session-only state (no file I/O)

from __future__ import annotations
import streamlit as st

PAGE_CONFIG = {"layout": "wide", "page_title": "Spanish Verb Lab", "page_icon": "🇪🇸"}


def ensure_state() -> None:
    """Initialize session state (browser session only)"""
    st.session_state.setdefault("mode", "grid")   # grid | detail
    st.session_state.setdefault("preview", None)  # currently previewed infinitive
    st.session_state.setdefault("selected", None) # currently opened infinitive (detail)
    
    # User data is initialized in spanish_core.init_user_data_in_session()
    # Called from app.py to avoid circular imports


def click_tile(infinitive: str) -> None:
    """
    Grid behavior:
    - click once -> preview in sidebar
    - click same again -> open detail
    """
    prev = st.session_state.get("preview")
    
    # If clicking the SAME tile that is already previewed -> Go to Detail
    if prev == infinitive and st.session_state.get("mode") == "grid":
        st.session_state["selected"] = infinitive
        st.session_state["mode"] = "detail"
    
    # If clicking a DIFFERENT tile -> Set Preview
    else:
        st.session_state["preview"] = infinitive
        st.session_state["selected"] = None
        st.session_state["mode"] = "grid"
        # Visual feedback
        st.toast(f"Previewing **{infinitive}**. Click again to open details.", icon="👀")


def back_to_grid() -> None:
    st.session_state["mode"] = "grid"
    st.session_state["selected"] = None