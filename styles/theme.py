import streamlit as st
from pathlib import Path

def inject_base_css():
    """Inyecta el CSS base desde styles/base.css."""
    css_path = Path(__file__).resolve().parent / 'base.css'
    try:
        css = css_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
