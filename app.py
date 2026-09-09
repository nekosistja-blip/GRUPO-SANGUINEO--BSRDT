from __future__ import annotations

import html
import sqlite3
from pathlib import Path

import streamlit as st

from build_index import DB_PATH, build_index, normalize_ci

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "logo_banco_sangre.png"

st.set_page_config(
    page_title="Consulta Grupo Sanguíneo",
    page_icon="🩸",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
#MainMenu, header, footer {display:none !important;}
.block-container {max-width:720px!important;padding-top:0.2rem!important;}
.search-title{text-align:center;font-size:1.5rem;font-weight:900;margin:10px;}
div[data-testid="stFormSubmitButton"] button{width:100%;background:#ef2b4f;color:white;font-weight:900;border-radius:12px;height:3rem;}
.result-card{background:white;border:1px solid #eee;border-radius:20px;padding:28px;margin-top:20px;box-shadow:0 5px 25px rgba(0,0,0,.08);}
.donor-line{font-size:clamp(1.6rem,5vw,2.3rem);font-weight:900;margin-bottom:8px;}
.rh-label{text-align:center;font-size:clamp(3rem,9vw,4.5rem);font-weight:900;margin-top:25px;}
.blood-group{text-align:center;color:#ff0054;font-size:clamp(8rem,30vw,16rem);font-weight:950;line-height:.9;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner=False)
def prepare_database():
    return str(build_index(force=False))


def lookup_donor(ci):
    ci = normalize_ci(ci)
    if not ci:
        return None
    db = prepare_database()
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT ci, full_name, codigo, grupo FROM donor_lookup WHERE ci=? LIMIT 1",
            (ci,)
        ).fetchone()


if "resultado" not in st.session_state:
    st.session_state.resultado = None

if LOGO_PATH.exists():
    st.image(str(LOGO_PATH), width=360)

st.markdown('<div class="search-title">Consulta de Grupo Sanguíneo</div>', unsafe_allow_html=True)

with st.form("form_busqueda"):
    ci = st.text_input("Carnet", placeholder="Ingrese carnet de identidad")
    buscar = st.form_submit_button("BUSQUEDA")

if buscar:
    try:
        st.session_state.resultado = lookup_donor(ci)
    except Exception as e:
        st.error("Error al consultar la base")
        st.caption(str(e))
        st.session_state.resultado = None

resultado = st.session_state.resultado

if resultado:
    nombre = html.escape(resultado["full_name"] or "SIN NOMBRE")
    codigo = html.escape(resultado["codigo"] or "-")
    grupo = html.escape(resultado["grupo"] or "SIN DATO")

    st.markdown(f"""
    <div class="result-card">
    <div class="donor-line"><b>Donante:</b> {nombre}</div>
    <div class="donor-line"><b>Código Donante:</b> {codigo}</div>
    <div class="rh-label">Rh</div>
    <div class="blood-group">{grupo}</div>
    </div>
    """, unsafe_allow_html=True)
