import copy
import streamlit as st

# All session state keys used across the app, with their defaults.
# Imported and called at the top of every page so keys survive navigation.
_DEFAULTS: dict = {
    "messages":         [],   # chat page: conversation history
    "suggestions":      [],   # chat page: follow-up questions
    "analysis_history": [],   # analytics page: Q&A history
}


def init_session_state() -> None:
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            # deepcopy so in-place mutations (list.append) never pollute _DEFAULTS
            st.session_state[key] = copy.deepcopy(default)
