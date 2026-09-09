from __future__ import annotations

import html
import sqlite3
from pathlib import Path

import streamlit as st

from build_index import DB_PATH, build_index, normalize_ci

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
    .block-container {
        max-width: 720px !important;
        padding-top: 1.2rem !important;
        padding-bottom: 2rem !important;
    }
    .brand-wrap {
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .search-title {
        text-align: center;
        font-size: 1.45rem;
        font-weight: 800;
        color: #111111;
        margin: 0.25rem 0 0.8rem 0;
    }
    div[data-testid="stTextInput"] input {
        font-size: 1.12rem !important;
        min-height: 3.15rem !important;
        border-radius: 12px !important;
    }
    div[data-testid="stFormSubmitButton"] button {
        width: 100% !important;
        min-height: 3.05rem !important;
        border-radius: 12px !important;
        border: none !important;
        background: #ef2b4f !important;
        color: white !important;
        font-size: 1.08rem !important;
        font-weight: 800 !important;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background: #d91f43 !important;
        color: white !important;
    }
    .result-card {
        background: #ffffff;
        border-radius: 20px;
        padding: 28px 30px 30px 30px;
        margin-top: 1.35rem;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
        border: 1px solid #eeeeee;
    }
    .donor-line {
        color: #111111;
        font-size: 1.55rem;
        font-weight: 800;
        line-height: 1.28;
        margin-bottom: 0.45rem;
        overflow-wrap: anywhere;
    }
    .donor-label {
        font-weight: 900;
    }
    .rh-label {
        text-align: center;
        color: #111111;
        font-size: 3.35rem;
        line-height: 1;
        font-weight: 900;
        margin-top: 2.2rem;
        margin-bottom: 0.1rem;
    }
    .blood-group {
        text-align: center;
        color: #ff0054;
        font-size: clamp(7.5rem, 27vw, 13rem);
        line-height: 0.9;
        font-weight: 950;
        letter-spacing: -0.06em;
        margin: 0.2rem 0 0.15rem 0;
        white-space: nowrap;
    }
    .blood-group.no-data {
        font-size: clamp(3.2rem, 12vw, 5.2rem);
        letter-spacing: -0.02em;
        line-height: 1;
        margin-top: 1.2rem;
    }
    .notice {
        text-align: center;
        margin-top: 1rem;
        color: #666666;
        font-size: 0.9rem;
    }
    @media (max-width: 560px) {
        .block-container {padding-left: 1rem !important; padding-right: 1rem !important;}
        .result-card {padding: 22px 20px 26px 20px;}
        .donor-line {font-size: 1.28rem;}
        .rh-label {font-size: 2.75rem; margin-top: 1.7rem;}
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


if LOGO_PATH.exists():
    st.image(str(LOGO_PATH), use_column_width=True)

st.markdown('<div class="search-title">Consulta de Grupo Sanguíneo</div>', unsafe_allow_html=True)

with st.form("consulta_ci", clear_on_submit=False):
    ci_input = st.text_input(
        "Carnet de identidad",
        placeholder="Ingrese el carnet de identidad",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("BUSCAR")

if submitted:
    if not normalize_ci(ci_input):
        st.warning("Ingrese un carnet de identidad.")
    else:
        lookup_failed = False
        try:
            donor = lookup_donor(ci_input)
        except Exception as exc:
            st.error("No se pudo preparar la base de consulta.")
            st.caption(str(exc))
            donor = None
            lookup_failed = True

        if donor is None and not lookup_failed:
            st.error("No se encontró el donante en ninguno de los dos sistemas.")
        elif donor is not None:
            full_name = html.escape((donor["full_name"] or "").strip() or "SIN NOMBRE")
            donor_code = html.escape((donor["codigo"] or "").strip() or "—")
            blood_group = html.escape((donor["grupo"] or "").strip())
            group_class = "blood-group" if blood_group else "blood-group no-data"
            group_text = blood_group or "SIN DATO"

            st.markdown(
                f"""
                <div class="result-card">
                    <div class="donor-line"><span class="donor-label">Donante:</span> {full_name}</div>
                    <div class="donor-line"><span class="donor-label">Código Donante:</span> {donor_code}</div>
                    <div class="rh-label">Rh</div>
                    <div class="{group_class}">{group_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
