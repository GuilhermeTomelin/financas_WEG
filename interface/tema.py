from pathlib import Path
import streamlit as st


def aplicar():
    st.html("<style>" + Path(__file__).with_name("estilos.css").read_text(encoding="utf-8") + "</style>")
