from __future__ import annotations

import base64
import html
import sqlite3
from pathlib import Path

import streamlit as st

from build_index import build_index, normalize_ci

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "logo_banco_sangre.png"

st.set_page_config(
    page_title="Consulta de Grupo Sanguíneo",
    page_icon="🩸",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    #MainMenu, header, footer {visibility: hidden !important; display: none !important;}
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stStatusWidget"], [data-testid="collapsedControl"],
    section[data-testid="stSidebar"], div[data-testid="stAppToolbar"] {
        visibility: hidden !important;
        display: none !important;
    }
    .stApp {
        background: #f7f7f7;
    }
    .block-container {
        max-width: 840px !important;
        padding-top: 0.35rem !important;
        padding-bottom: 1.4rem !important;
        padding-left: 1.1rem !important;
        padding-right: 1.1rem !important;
    }
    .brand-wrap {
        text-align: center;
        margin-top: 0 !important;
        margin-bottom: 0.6rem;
    }
    .brand-wrap img {
        width: min(100%, 620px);
        height: auto;
        display: inline-block;
    }
    .search-title {
        text-align: center;
        font-size: clamp(1.5rem, 3vw, 2rem);
        font-weight: 900;
        color: #20273a;
        margin: 0.15rem 0 0.95rem 0;
    }
    .search-box {
        background: #ffffff;
        border-radius: 18px;
        border: 1px solid #dedede;
        padding: 0.9rem 0.9rem 0.4rem 0.9rem;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.04);
        margin-bottom: 1rem;
    }
    .search-box label {
        font-size: 0.98rem !important;
        font-weight: 700 !important;
        color: #3b3b3b !important;
    }
    div[data-testid="stTextInput"] input {
        font-size: 1.2rem !important;
        min-height: 3.35rem !important;
        border-radius: 14px !important;
        background: #f1f2f6 !important;
    }
    div[data-testid="stFormSubmitButton"] button {
        width: 100% !important;
        min-height: 3.2rem !important;
        border-radius: 14px !important;
        border: none !important;
        background: #ef2b4f !important;
        color: white !important;
        font-size: 1.08rem !important;
        font-weight: 900 !important;
        letter-spacing: 0.02em;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background: #d91f43 !important;
        color: white !important;
    }
    .result-card {
        background: #ffffff;
        border-radius: 24px;
        padding: 26px 28px 28px 28px;
        margin-top: 0.2rem;
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.06);
        border: 1px solid #ebebeb;
    }
    .donor-line {
        color: #20273a;
        font-size: clamp(1.75rem, 4.9vw, 2.35rem);
        font-weight: 900;
        line-height: 1.18;
        margin-bottom: 0.8rem;
        overflow-wrap: anywhere;
    }
    .donor-label {
        font-weight: 900;
    }
    .code-line {
        color: #20273a;
        font-size: clamp(1.5rem, 4vw, 2rem);
        font-weight: 850;
        line-height: 1.18;
        margin-bottom: 0.2rem;
        overflow-wrap: anywhere;
    }
    .rh-label {
        text-align: center;
        color: #232632;
        font-size: clamp(3.1rem, 8vw, 4.4rem);
        line-height: 1;
        font-weight: 900;
        margin-top: 2rem;
        margin-bottom: 0.25rem;
    }
    .blood-group {
        text-align: center;
        color: #ff0054;
        font-size: clamp(9rem, 26vw, 16rem);
        line-height: 0.9;
        font-weight: 950;
        letter-spacing: -0.06em;
        margin: 0.05rem 0 0.1rem 0;
        white-space: nowrap;
    }
    .blood-group.no-data {
        font-size: clamp(3.4rem, 10vw, 5.8rem);
        letter-spacing: -0.02em;
        line-height: 1;
        margin-top: 1rem;
    }
    .msg-card {
        background: #ffffff;
        border: 1px solid #ececec;
        border-radius: 18px;
        padding: 1rem 1.15rem;
        color: #505767;
        font-size: 1.02rem;
        margin-top: 0.35rem;
        box-shadow: 0 6px 20px rgba(0,0,0,0.04);
    }
    @media (max-width: 640px) {
        .block-container {
            padding-top: 0.15rem !important;
            padding-left: 0.7rem !important;
            padding-right: 0.7rem !important;
            padding-bottom: 1rem !important;
        }
        .brand-wrap {
            margin-bottom: 0.25rem;
        }
        .brand-wrap img {
            width: min(100%, 360px);
        }
        .search-title {
            margin-top: 0.05rem;
            margin-bottom: 0.7rem;
        }
        .search-box {
            border-radius: 16px;
            padding: 0.7rem 0.7rem 0.25rem 0.7rem;
            margin-bottom: 0.8rem;
        }
        .result-card {
            border-radius: 20px;
            padding: 18px 16px 22px 16px;
        }
        .donor-line {
            font-size: clamp(1.55rem, 7.3vw, 2rem);
            margin-bottom: 0.6rem;
        }
        .code-line {
            font-size: clamp(1.3rem, 6vw, 1.7rem);
        }
        .rh-label {
            font-size: clamp(2.7rem, 11vw, 3.6rem);
            margin-top: 1.45rem;
        }
        .blood-group {
            font-size: clamp(8rem, 32vw, 11rem);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def prepare_database() -> str:
    """Verifica el índice una sola vez por proceso y lo reconstruye si cambiaron los Excel."""
    return str(build_index(force=False))


def lookup_donor(ci: str):
    normalized = normalize_ci(ci)
    if not normalized:
        return None
    db_path = prepare_database()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT ci, full_name, codigo, grupo
            FROM donor_lookup
            WHERE ci = ?
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()


def logo_html() -> str:
    if not LOGO_PATH.exists():
        return ""
    b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f'<div class="brand-wrap"><img src="data:image/png;base64,{b64}" alt="Banco de Sangre"></div>'


if "donor_result" not in st.session_state:
    st.session_state.donor_result = None
if "lookup_message" not in st.session_state:
    st.session_state.lookup_message = ""
if "lookup_error" not in st.session_state:
    st.session_state.lookup_error = False

st.markdown(logo_html(), unsafe_allow_html=True)
st.markdown('<div class="search-title">Consulta de Grupo Sanguíneo</div>', unsafe_allow_html=True)

st.markdown('<div class="search-box">', unsafe_allow_html=True)
with st.form("consulta_ci", clear_on_submit=False):
    ci_input = st.text_input(
        "Carnet",
        placeholder="Ingrese el carnet de identidad",
    )
    submitted = st.form_submit_button("BUSQUEDA")
st.markdown('</div>', unsafe_allow_html=True)

if submitted:
    if not normalize_ci(ci_input):
        st.session_state.donor_result = None
        st.session_state.lookup_message = "Ingrese un carnet de identidad."
        st.session_state.lookup_error = True
    else:
        try:
            donor = lookup_donor(ci_input)
            if donor is None:
                st.session_state.donor_result = None
                st.session_state.lookup_message = "No se encontró el donante en ninguno de los dos sistemas."
                st.session_state.lookup_error = True
            else:
                st.session_state.donor_result = donor
                st.session_state.lookup_message = ""
                st.session_state.lookup_error = False
        except Exception as exc:
            st.session_state.donor_result = None
            st.session_state.lookup_message = f"No se pudo preparar la base de consulta. {exc}"
            st.session_state.lookup_error = True

if st.session_state.lookup_message:
    st.markdown(
        f'<div class="msg-card">{html.escape(st.session_state.lookup_message)}</div>',
        unsafe_allow_html=True,
    )

if st.session_state.donor_result is not None:
    donor = st.session_state.donor_result
    full_name = html.escape((donor["full_name"] or "").strip() or "SIN NOMBRE")
    donor_code = html.escape((donor["codigo"] or "").strip() or "—")
    blood_group = html.escape((donor["grupo"] or "").strip())
    group_class = "blood-group" if blood_group else "blood-group no-data"
    group_text = blood_group or "SIN DATO"

    st.markdown(
        f"""
        <div class="result-card">
            <div class="donor-line"><span class="donor-label">Donante:</span> {full_name}</div>
            <div class="code-line"><span class="donor-label">Código Donante:</span> {donor_code}</div>
            <div class="rh-label">Rh</div>
            <div class="{group_class}">{group_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
