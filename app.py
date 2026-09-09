import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Sistema de Consulta de Donantes",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
#MainMenu, header, footer {visibility: hidden !important; display: none !important;}
[data-testid="stHeader"] {visibility: hidden !important; display: none !important; height: 0 !important;}
[data-testid="stToolbar"] {visibility: hidden !important; display: none !important;}
[data-testid="stDecoration"] {visibility: hidden !important; display: none !important;}
[data-testid="stStatusWidget"] {visibility: hidden !important; display: none !important;}
[data-testid="collapsedControl"] {visibility: hidden !important; display: none !important;}
section[data-testid="stSidebar"] {display: none !important;}
button[kind="header"], button[title*="Share"], button[title*="share"] {display:none !important;}
a[title*="Share"], a[title*="share"] {display:none !important;}
div[data-testid="stActionButtonIcon"], div[data-testid="stAppToolbar"] {display:none !important;}
[data-testid="stAppViewContainer"] > .main {padding-top: 0rem !important;}
.block-container {padding-top: 1rem !important;}
</style>
""", unsafe_allow_html=True)

df = pd.read_excel('GRUPO SANGRE.xlsx', sheet_name=None)
vamDonante = df['vamDonante'].copy()
vamScreeni = df['vamScreeni'].copy()

vamDonante['vdonDocIde'] = vamDonante['vdonDocIde'].astype(str).str.strip()
vamDonante['vdonCodDon'] = vamDonante['vdonCodDon'].astype(str).str.strip()
vamScreeni['vdonCodDon'] = vamScreeni['vdonCodDon'].astype(str).str.strip()

def normalizar_etiqueta(valor):
    if pd.isna(valor):
        return ""
    txt = str(valor).strip()
    if txt.endswith(".0"):
        txt = txt[:-2]
    txt = "".join(ch for ch in txt if ch.isdigit())
    if not txt:
        return ""
    return txt.zfill(16)

def obtener_puesto(vscrNroEti):
    etiqueta = normalizar_etiqueta(vscrNroEti)
    prefijo = etiqueta[:3]
    if prefijo == "001":
        return "PUESTO FIJO", "green"
    if prefijo == "002":
        return "PUESTO MOVIL", "orange"
    return "", ""

def es_rechazado(vscrLabMed):
    if pd.isna(vscrLabMed):
        return False
    return str(vscrLabMed).strip().upper() == "R"

def convertir_grupo(c):
    try:
        c = int(c)
    except Exception:
        return "Desconocido"
    grupos = {
        1: "A+", 2: "B+", 3: "AB+", 4: "O+",
        5: "A-", 6: "B-", 7: "AB-", 8: "O-",
        9: " ", 10: " ", 11: "IN+", 12: "B+"
    }
    return grupos.get(c, "Desconocido")

def buscar(cedula):
    cedula = str(cedula).strip()
    d = vamDonante[vamDonante['vdonDocIde'] == cedula]
    if d.empty:
        return None, None
    info = d.iloc[0]
    cod = str(info['vdonCodDon']).strip()
    donaciones = vamScreeni[vamScreeni['vdonCodDon'].astype(str).str.strip() == cod].copy()
    return info, donaciones

st.title('🩸 Sistema de Consulta de Donantes')

cedula = st.text_input('📘 Ingresa Cédula de Identidad:')

if st.button('🔎 Buscar'):
    info, donaciones = buscar(cedula)

    if info is None:
        st.error('No se encontró el donante.')
    else:
        st.subheader('👤 Datos del Donante')
        st.write(f"**Código:** {info['vdonCodDon']}")
        st.write(f"**Nombre:** {info['vdonNombre']} {info['vdonPatern']} {info['vdonMatern']}")
        st.write(f"**Dirección:** {info['vdonDirecc']}")
        st.write(f"**Celular:** {info['vdonTelCel']}")

        if donaciones is not None and not donaciones.empty:
            st.subheader('🩺 Historial de Donaciones')

            for _, fila in donaciones.iterrows():
                puesto, color = obtener_puesto(fila.get('vscrNroEti'))
                rechazado = es_rechazado(fila.get('vscrLabMed'))

                st.markdown(
                    """
                    <div style="
                        border:1px solid #e6e6e6;
                        border-radius:12px;
                        padding:14px;
                        margin-bottom:12px;
                        background:#ffffff;
                        box-shadow:0 1px 3px rgba(0,0,0,0.05);
                    ">
                    """,
                    unsafe_allow_html=True
                )

                st.write(f"📅 Fecha: {fila.get('vscrFechas', '')}")
                st.write(f"🩸 Grupo sanguíneo: {convertir_grupo(fila.get('vscrGrsCon'))}")
                st.write(f"💬 Comentario: {fila.get('vscrComent', '')}")

                if rechazado:
                    st.markdown('<div style="color:red; font-weight:700;">RECHAZADO</div>', unsafe_allow_html=True)

                if puesto:
                    st.markdown(
                        f'<div style="color:{color}; font-weight:700; margin-top:4px;">{puesto}</div>',
                        unsafe_allow_html=True
                    )

                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("Este donante no tiene donaciones registradas.")
