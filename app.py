import streamlit as st
import pandas as pd

st.set_page_config(page_title="Consulta Grupo Sanguíneo", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""<style>
#MainMenu, header, footer {display:none;}
.block-container {padding-top:0.5rem !important;}
</style>""", unsafe_allow_html=True)

@st.cache_data
def cargar():
    df=pd.read_excel("GRUPO SANGRE.xlsx", sheet_name=None)
    don=df["vamDonante"].copy()
    scr=df["vamScreeni"].copy()
    don["vdonDocIde"]=don["vdonDocIde"].astype(str).str.strip()
    don["vdonCodDon"]=don["vdonCodDon"].astype(str).str.strip()
    scr["vdonCodDon"]=scr["vdonCodDon"].astype(str).str.strip()
    return don,scr

def grupo(x):
    try: x=int(x)
    except: return "SIN DATO"
    return {1:"A+",2:"B+",3:"AB+",4:"O+",5:"A-",6:"B-",7:"AB-",8:"O-"}.get(x,"SIN DATO")

don,scr=cargar()

st.title("🩸 Consulta de Grupo Sanguíneo")
ci=st.text_input("Carnet de identidad")

if st.button("BUSQUEDA"):
    r=don[don.vdonDocIde==str(ci).strip()]
    if r.empty:
        st.error("No se encontró el donante")
    else:
        d=r.iloc[0]
        nombre=f"{d.vdonNombre} {d.vdonPatern} {d.vdonMatern}"
        cod=str(d.vdonCodDon)
        hist=scr[scr.vdonCodDon==cod]
        grupos=hist.vscrGrsCon.apply(grupo) if not hist.empty else pd.Series(dtype=str)
        final=grupos.mode().iloc[0] if len(grupos.mode()) else "SIN DATO"
        st.subheader("DONANTE")
        st.markdown(f"## {nombre}")
        st.write("Código Donante:", cod)
        st.markdown("# Rh")
        st.markdown(f"# 🩸 {final}")
