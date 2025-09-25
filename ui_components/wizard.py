import streamlit as st
from typing import List

"""Componente de wizard clickable.
Uso:
    render_wizard(["Datos","Grabación","Resultados"], active_index=1, done_until=0)
"""

def render_wizard(steps: List[str], active_index: int, done_until: int = -1):
    html = ["<div class='wizard'>"]
    for idx, name in enumerate(steps):
        classes = ["wizard-step"]
        if idx == active_index:
            classes.append("active")
        elif idx <= done_until and idx < active_index:
            classes.append("done")
        html.append(f"<div class='{' '.join(classes)}'>{idx+1}. {name}</div>")
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)
