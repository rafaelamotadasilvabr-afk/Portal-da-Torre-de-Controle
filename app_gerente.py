import io
import re
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Dashboard Executivo da Torre",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 1.2rem; max-width: 1450px;}
    [data-testid="stSidebar"] {border-right: 1px solid #e8edf4;}
    .dash-hero {
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 55%, #2563eb 100%);
        border-radius: 22px;
        padding: 24px 28px;
        color: white;
        box-shadow: 0 14px 40px rgba(37, 99, 235, 0.22);
        margin-bottom: 1rem;
    }
    .dash-hero h1 {
        font-size: 2rem;
        line-height: 1.1;
        margin: 0 0 6px 0;
        letter-spacing: -0.03em;
    }
    .dash-hero p {
        margin: 0;
        opacity: 0.92;
        font-size: 0.98rem;
    }
    .dash-badge {
        display: inline-block;
        background: rgba(255,255,255,0.14);
        border: 1px solid rgba(255,255,255,0.18);
        padding: 6px 10px;
        border-radius: 999px;
        margin-right: 8px;
        font-size: 0.82rem;
    }
    .section-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0f172a;
        margin: 0.15rem 0 0.6rem 0;
        letter-spacing: -0.02em;
    }
    .kpi-card {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e7edf5;
        border-radius: 18px;
        padding: 16px 16px 14px 16px;
        min-height: 118px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
    }
    .kpi-topline {
        width: 100%;
        height: 5px;
        border-radius: 999px;
        margin-bottom: 12px;
    }
    .tone-blue {background: linear-gradient(90deg, #2563eb, #60a5fa);}
    .tone-red {background: linear-gradient(90deg, #dc2626, #f87171);}
    .tone-amber {background: linear-gradient(90deg, #d97706, #fbbf24);}
    .tone-violet {background: linear-gradient(90deg, #7c3aed, #a78bfa);}
    .tone-slate {background: linear-gradient(90deg, #334155, #94a3b8);}
    .kpi-label {
        color: #475569;
        font-size: 0.86rem;
        line-height: 1.2;
        margin-bottom: 8px;
    }
    .kpi-value {
        color: #0f172a;
        font-size: 2rem;
        font-weight: 800;
        line-height: 1;
        letter-spacing: -0.03em;
        margin-bottom: 6px;
    }
    .kpi-sub {
        color: #64748b;
        font-size: 0.78rem;
        line-height: 1.25;
    }
    .panel-box {
        background: #ffffff;
        border: 1px solid #e7edf5;
        border-radius: 18px;
        padding: 16px 18px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        margin-bottom: 0.9rem;
    }
    .mini-note {
        color: #64748b;
        font-size: 0.82rem;
        margin-top: -0.2rem;
        margin-bottom: 0.55rem;
    }
    h1, h2, h3 {letter-spacing: -0.02em;}
    </style>
    """,
    unsafe_allow_html=True,
)

def extract_google_sheet_id(url: str):
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", str(url))
    return match.group(1) if match else None

@st.cache_data(ttl=300, show_spinner=False)
def load_pack_from_google_sheet(url: str):
    sheet_id = extract_google_sheet_id(url)
    if not sheet_id:
        raise ValueError("Link do Google Sheets inválido.")
    xlsx_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    response = requests.get(xlsx_url, timeout=60)
    response.raise_for_status()
    return load_pack_from_bytes(response.content)

@st.cache_data(show_spinner=False)
def load_pack_from_bytes(file_bytes: bytes):
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    return {name: pd.read_excel(xls, sheet_name=name) for name in xls.sheet_names}

def summary_value(summary_df: pd.DataFrame, metric_name: str, default=""):
    if summary_df is None or summary_df.empty:
        return default
    row = summary_df.loc[summary_df["METRICA"].astype(str) == metric_name]
    if row.empty:
        return default
    return row.iloc[0]["VALOR"]

def to_int(value):
    return int(pd.to_numeric(value, errors="coerce") or 0)

def brl(value):
    try:
        value = float(value)
    except Exception:
        value = 0.0
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def render_card(label, value, tone="tone-blue", sub=""):
    st.markdown(
        f'''
        <div class="kpi-card">
            <div class="kpi-topline {tone}"></div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

st.markdown(
    '''
    <div class="dash-hero">
        <div>
            <span class="dash-badge">Torre de Controle</span>
            <span class="dash-badge">Visão Executiva</span>
        </div>
        <h1>Dashboard Executivo da Torre</h1>
        <p>Painel gerencial separado da operação detalhada, focado em risco, SLA, backlog e ofensores.</p>
    </div>
    ''',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Fonte do dashboard")
    source_mode = st.radio(
        "Origem dos dados",
        ["Upload do pacote", "Link do Google Sheets"],
    )

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

    st.divider()
    show_queue = st.checkbox("Mostrar fila executiva", value=True)
    show_tables = st.checkbox("Mostrar tabelas-resumo", value=True)

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

analysis_date = summary_value(resumo, "Data de análise", "")
last_update = summary_value(resumo, "Atualizado em", "")

awbs_monitoradas = to_int(summary_value(resumo, "AWBs monitoradas", 0))
awbs_acao = to_int(summary_value(resumo, "AWBs com ação", 0))
acoes_imediatas = to_int(summary_value(resumo, "Ações imediatas", 0))
entrega_atraso = to_int(summary_value(resumo, "Entrega em atraso", 0))
sla_sem_rota = to_int(summary_value(resumo, "SLA do dia sem rota", 0))
backlog_torre = to_int(summary_value(resumo, "Backlog da Torre", 0))
acareacoes = to_int(summary_value(resumo, "Acareações em andamento", 0))
valor_acareacao = summary_value(resumo, "Valor em acareação", 0)

col_a, col_b = st.columns([2.2, 1.2])
with col_a:
    st.markdown('<div class="section-title">Resumo executivo</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="mini-note">Leitura rápida da operação para gestão, sem detalhe técnico nem necessidade de upload operacional.</div>',
        unsafe_allow_html=True,
    )
with col_b:
    if analysis_date or last_update:
        st.markdown(
            f'''
            <div class="panel-box">
                <div class="mini-note"><strong>Data de análise:</strong> {analysis_date}</div>
                <div class="mini-note"><strong>Atualizado em:</strong> {last_update}</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

r1 = st.columns(4)
with r1[0]:
    render_card("AWBs monitoradas", awbs_monitoradas, "tone-blue", "Total de AWBs únicas na carteira atual")
with r1[1]:
    render_card("AWBs com ação", awbs_acao, "tone-slate", "Somente prioridades crítica, alta e média")
with r1[2]:
    render_card("Ações imediatas", acoes_imediatas, "tone-red", "Prioridade máxima de atuação")
with r1[3]:
    render_card("Entrega em atraso", entrega_atraso, "tone-red", "Risco direto de SLA vencido")

r2 = st.columns(4)
with r2[0]:
    render_card("SLA do dia sem rota", sla_sem_rota, "tone-amber", "Carga do dia sem rota criada")
with r2[1]:
    render_card("Backlog da Torre", backlog_torre, "tone-violet", "Pendências ainda não finalizadas")
with r2[2]:
    render_card("Acareações em andamento", acareacoes, "tone-blue", "Tratativas ativas no momento")
with r2[3]:
    render_card("Valor em acareação", brl(valor_acareacao), "tone-amber", "Valor financeiro atualmente exposto")

st.markdown(
    '<div class="mini-note">O valor do passível a débito foi removido temporariamente do dashboard do gerente.</div>',
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2)
with col1:
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Top problemas</div>', unsafe_allow_html=True)
    if not top_problemas.empty:
        chart_df = top_problemas.set_index(top_problemas.columns[0])[[top_problemas.columns[1]]]
        st.bar_chart(chart_df)
        if show_tables:
            st.dataframe(top_problemas, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de problemas.")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Top bases / responsáveis</div>', unsafe_allow_html=True)
    if not top_bases.empty:
        chart_df = top_bases.set_index(top_bases.columns[0])[[top_bases.columns[1]]]
        st.bar_chart(chart_df)
        if show_tables:
            st.dataframe(top_bases, use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados de bases.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="panel-box">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Top clientes impactados</div>', unsafe_allow_html=True)
if not top_clientes.empty:
    chart_df = top_clientes.set_index(top_clientes.columns[0])[[top_clientes.columns[1]]]
    st.bar_chart(chart_df)
    if show_tables:
        st.dataframe(top_clientes, use_container_width=True, hide_index=True)
else:
    st.info("Sem dados de clientes.")
st.markdown('</div>', unsafe_allow_html=True)

if show_queue:
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Fila executiva</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="mini-note">Recorte resumido das principais ações para acompanhamento gerencial.</div>',
        unsafe_allow_html=True,
    )
    if not fila.empty:
        cols = [
            c for c in [
                "PRIORIDADE",
                "AWB",
                "CLIENTE",
                "SITUAÇÃO",
                "LOCALIZAÇÃO / RESPONSÁVEL",
                "PROBLEMA",
                "PRÓXIMA AÇÃO",
            ]
            if c in fila.columns
        ]
        queue_view = fila[cols] if cols else fila
        st.dataframe(queue_view, use_container_width=True, hide_index=True)
    else:
        st.info("Sem fila executiva no pacote.")
    st.markdown('</div>', unsafe_allow_html=True)
