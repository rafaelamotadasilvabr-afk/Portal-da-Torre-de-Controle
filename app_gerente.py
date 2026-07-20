import io
import re
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Dashboard do Gerente", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 1.2rem;}
div[data-testid="metric-container"] {
    background: linear-gradient(180deg, #ffffff 0%, #f6f8fb 100%);
    border: 1px solid #e6eaf2;
    padding: 16px 18px;
    border-radius: 16px;
    box-shadow: 0 6px 18px rgba(20, 35, 90, 0.06);
}
h1, h2, h3 {letter-spacing: -0.02em;}
</style>
""", unsafe_allow_html=True)

def extract_google_sheet_id(url):
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", str(url))
    return match.group(1) if match else None

@st.cache_data(ttl=300, show_spinner=False)
def load_pack_from_google_sheet(url):
    sheet_id = extract_google_sheet_id(url)
    if not sheet_id:
        raise ValueError("Link do Google Sheets inválido.")
    xlsx_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    response = requests.get(xlsx_url, timeout=60)
    response.raise_for_status()
    return load_pack_from_bytes(response.content)

@st.cache_data(show_spinner=False)
def load_pack_from_bytes(file_bytes):
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    return {name: pd.read_excel(xls, sheet_name=name) for name in xls.sheet_names}

def summary_value(summary_df, metric_name, default=""):
    if summary_df is None or summary_df.empty:
        return default
    row = summary_df.loc[summary_df["METRICA"].astype(str) == metric_name]
    if row.empty:
        return default
    return row.iloc[0]["VALOR"]

def brl(value):
    try:
        value = float(value)
    except Exception:
        value = 0.0
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.title("Dashboard do Gerente")
st.caption("Tela executiva separada da operação detalhada.")

with st.sidebar:
    st.header("Fonte do dashboard")
    source_mode = st.radio("Fonte", ["Upload do pacote", "Link do Google Sheets"])
    uploaded = None
    gs_link = ""
    if source_mode == "Upload do pacote":
        uploaded = st.file_uploader(
            "Pacote do dashboard do gerente",
            type=["xlsx"],
            help="Use o arquivo exportado pelo app operacional.",
        )
    else:
        gs_link = st.text_input(
            "Link do Google Sheets",
            value="",
            help="Cole aqui a planilha gerencial quando ela estiver publicada em um link próprio.",
        )

if source_mode == "Upload do pacote" and not uploaded:
    st.info("Envie o pacote do gerente para abrir o dashboard.")
    st.stop()

if source_mode == "Link do Google Sheets" and not gs_link.strip():
    st.info("Informe o link do Google Sheets do dashboard gerencial.")
    st.stop()

try:
    if source_mode == "Upload do pacote":
        pack = load_pack_from_bytes(uploaded.getvalue())
    else:
        pack = load_pack_from_google_sheet(gs_link)
except Exception as exc:
    st.error(f"Não foi possível abrir o pacote do gerente: {exc}")
    st.stop()

resumo = pack.get("RESUMO", pd.DataFrame())
fila = pack.get("FILA", pd.DataFrame())
top_problemas = pack.get("TOP_PROBLEMAS", pd.DataFrame())
top_bases = pack.get("TOP_BASES", pd.DataFrame())
top_clientes = pack.get("TOP_CLIENTES", pd.DataFrame())

last_update = summary_value(resumo, "Atualizado em", "")
analysis_date = summary_value(resumo, "Data de análise", "")

h1, h2 = st.columns([2, 1])
with h1:
    st.subheader("Resumo executivo")
with h2:
    if analysis_date or last_update:
        st.caption(f"Data de análise: {analysis_date}\nAtualizado em: {last_update}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("AWBs monitoradas", int(pd.to_numeric(summary_value(resumo, "AWBs monitoradas", 0), errors="coerce") or 0))
c2.metric("AWBs com ação", int(pd.to_numeric(summary_value(resumo, "AWBs com ação", 0), errors="coerce") or 0))
c3.metric("Ações imediatas", int(pd.to_numeric(summary_value(resumo, "Ações imediatas", 0), errors="coerce") or 0))
c4.metric("Entrega em atraso", int(pd.to_numeric(summary_value(resumo, "Entrega em atraso", 0), errors="coerce") or 0))

c5, c6, c7, c8 = st.columns(4)
c5.metric("SLA do dia sem rota", int(pd.to_numeric(summary_value(resumo, "SLA do dia sem rota", 0), errors="coerce") or 0))
c6.metric("Backlog da Torre", int(pd.to_numeric(summary_value(resumo, "Backlog da Torre", 0), errors="coerce") or 0))
c7.metric("Acareações em andamento", int(pd.to_numeric(summary_value(resumo, "Acareações em andamento", 0), errors="coerce") or 0))
c8.metric("Valor em acareação", brl(summary_value(resumo, "Valor em acareação", 0)))

col1, col2 = st.columns(2)
with col1:
    st.subheader("Top problemas")
    if not top_problemas.empty:
        st.bar_chart(top_problemas.set_index(top_problemas.columns[0])[top_problemas.columns[1]])
        st.dataframe(top_problemas, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de problemas.")

with col2:
    st.subheader("Top bases / responsáveis")
    if not top_bases.empty:
        st.bar_chart(top_bases.set_index(top_bases.columns[0])[top_bases.columns[1]])
        st.dataframe(top_bases, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de bases.")

st.subheader("Top clientes impactados")
if not top_clientes.empty:
    st.bar_chart(top_clientes.set_index(top_clientes.columns[0])[top_clientes.columns[1]])
    st.dataframe(top_clientes, use_container_width=True, hide_index=True)
else:
    st.info("Sem dados de clientes.")

with st.expander("Ver fila executiva"):
    if not fila.empty:
        cols = [c for c in ["PRIORIDADE", "AWB", "CLIENTE", "SITUAÇÃO", "LOCALIZAÇÃO / RESPONSÁVEL", "PROBLEMA", "PRÓXIMA AÇÃO"] if c in fila.columns]
        st.dataframe(fila[cols] if cols else fila, use_container_width=True, hide_index=True)
    else:
        st.info("Sem fila executiva no pacote.")
