import re
import pandas as pd
import requests
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Dashboard Executivo da Torre",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Fonte fixa opcional no próprio código.
# Preferencialmente configure pelo Streamlit Secrets:
# MANAGER_SOURCE_URL = "https://..."
DEFAULT_MANAGER_SOURCE_URL = ""

st.markdown(
    """
    <style>
    .stApp {
        background: #f5f7fb;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #06162f 0%, #082347 60%, #061a36 100%);
    }

    [data-testid="stSidebar"] * {
        color: #e5edf8;
    }

    .block-container {
        padding-top: 0.5rem;
        padding-bottom: 1.4rem;
        max-width: 1650px;
    }

    .brand-box {
        padding: 8px 6px 20px 6px;
        border-bottom: 1px solid rgba(255,255,255,.12);
        margin-bottom: 16px;
    }

    .brand-main {
        color: #ffffff;
        font-size: 3rem;
        font-weight: 950;
        font-style: italic;
        letter-spacing: -.06em;
        line-height: .9;
    }

    .brand-sub {
        color: #ffffff;
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: .42em;
        margin-top: 8px;
    }

    .nav-item {
        padding: 11px 13px;
        border-radius: 11px;
        margin-bottom: 8px;
        color: #dbeafe;
        font-size: .88rem;
    }

    .nav-active {
        background: linear-gradient(90deg, #0b4ea7, #123b76);
        font-weight: 800;
        color: #ffffff;
        box-shadow: 0 8px 18px rgba(0,0,0,.14);
    }

    .side-note {
        margin-top: 26px;
        border-top: 1px solid rgba(255,255,255,.12);
        padding-top: 16px;
        color: #b9c8dc;
        font-size: .76rem;
        line-height: 1.5;
    }

    .hero {
        background: linear-gradient(120deg, #071a37 0%, #082347 58%, #103b76 100%);
        color: white;
        border-radius: 0 0 22px 22px;
        padding: 22px 28px;
        margin: -0.5rem -0.2rem 14px -0.2rem;
        box-shadow: 0 12px 28px rgba(8,35,71,.16);
    }

    .hero h1 {
        margin: 0 0 5px 0;
        font-size: 2rem;
        letter-spacing: -0.035em;
    }

    .hero p {
        margin: 0;
        opacity: 0.92;
        font-size: 0.94rem;
    }

    .badge {
        display: inline-block;
        padding: 6px 10px;
        margin: 0 7px 10px 0;
        border-radius: 8px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.22);
        font-size: 0.74rem;
        font-weight: 750;
    }

    .section-title {
        font-size: 0.98rem;
        font-weight: 850;
        color: #10213d;
        margin: 8px 0 10px 0;
    }

    .kpi {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 15px 16px;
        min-height: 136px;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.055);
        border-top: 4px solid var(--accent);
    }

    .kpi-icon {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: var(--soft);
        color: var(--accent);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 900;
        margin-bottom: 10px;
    }

    .label {
        color: #334155;
        font-size: 0.76rem;
        font-weight: 850;
        margin-bottom: 7px;
        text-transform: uppercase;
        min-height: 30px;
    }

    .value {
        color: var(--value);
        font-size: 1.85rem;
        font-weight: 950;
        line-height: 1;
        margin-bottom: 8px;
        letter-spacing: -0.04em;
    }

    .sub {
        color: #708099;
        font-size: 0.71rem;
        line-height: 1.35;
    }

    .panel {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px 18px;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.045);
        margin-bottom: 12px;
    }

    .panel-title {
        font-size: 1.03rem;
        font-weight: 850;
        color: #10213d;
        margin-bottom: 3px;
    }

    .panel-sub {
        color: #718096;
        font-size: 0.76rem;
        margin-bottom: 12px;
    }

    .info {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 10px 13px;
        color: #52637c;
        font-size: 0.80rem;
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(15,23,42,.025);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        overflow: hidden;
    }

    div[data-testid="stButton"] button {
        border-radius: 10px;
        border: 1px solid #cbd5e1;
        background: #ffffff;
        color: #10213d;
        font-weight: 750;
        font-size: .78rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def extract_google_sheet_id(url):
    match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", str(url))
    return match.group(1) if match else None


def _google_service_account_info():
    try:
        return dict(st.secrets["gcp_service_account"])
    except Exception:
        return None


def _google_sheet_client():
    info = _google_service_account_info()
    if not info:
        return None

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


def load_source(url):
    gc = _google_sheet_client()
    if gc is None:
        raise RuntimeError(
            "Credenciais gcp_service_account não configuradas no app do gerente."
        )

    spreadsheet = gc.open_by_url(url)
    result = {}

    for sheet_name in ["RESUMO", "FILA", "TOP_PROBLEMAS", "TOP_BASES"]:
        try:
            ws = spreadsheet.worksheet(sheet_name)
            values = ws.get_all_values()

            if not values:
                result[sheet_name] = pd.DataFrame()
                continue

            headers = values[0]
            rows = values[1:]
            result[sheet_name] = pd.DataFrame(rows, columns=headers)
        except gspread.WorksheetNotFound:
            result[sheet_name] = pd.DataFrame()

    return result


def summary_value(df, metric, default=""):
    if df is None or df.empty or "METRICA" not in df.columns:
        return default
    row = df[df["METRICA"].astype(str).eq(metric)]
    return default if row.empty else row.iloc[0]["VALOR"]


def number(value):
    n = pd.to_numeric(value, errors="coerce")
    return 0 if pd.isna(n) else int(n)


def fmt_int(value):
    return f"{number(value):,}".replace(",", ".")


def brl(value):
    n = pd.to_numeric(value, errors="coerce")
    n = 0 if pd.isna(n) else float(n)
    return f"R$ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def normalize_numeric_series(series):
    return pd.to_numeric(
        series.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0)


def chart_dataframe(df):
    if df is None or df.empty or len(df.columns) < 2:
        return pd.DataFrame()

    label_col = df.columns[0]
    value_col = df.columns[-1]

    out = df[[label_col, value_col]].copy()
    out[value_col] = normalize_numeric_series(out[value_col])
    out = out[out[value_col] > 0]

    if out.empty:
        return pd.DataFrame()

    return out.sort_values(value_col, ascending=False).head(10).set_index(label_col)


def card(label, value, subtitle, icon, accent, soft, value_color=None):
    value_color = value_color or "#10213d"
    st.markdown(
        f"""
        <div class="kpi" style="--accent:{accent}; --soft:{soft}; --value:{value_color};">
            <div class="kpi-icon">{icon}</div>
            <div class="label">{label}</div>
            <div class="value">{value}</div>
            <div class="sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


try:
    SOURCE_URL = st.secrets.get("MANAGER_SOURCE_URL", "")
except Exception:
    SOURCE_URL = ""

if not SOURCE_URL:
    SOURCE_URL = DEFAULT_MANAGER_SOURCE_URL

if not SOURCE_URL:
    st.error(
        "Fonte automática ainda não configurada. "
        "Adicione MANAGER_SOURCE_URL nos Secrets do app do gerente."
    )
    st.stop()


with st.sidebar:
    st.markdown(
        """
        <div class="brand-box">
            <div class="brand-main">GDS</div>
            <div class="brand-sub">LOGÍSTICA</div>
        </div>

        <div class="nav-item nav-active">⌂ &nbsp; Visão Geral</div>
        <div class="nav-item">↗ &nbsp; Monitoramento</div>
        <div class="nav-item">▣ &nbsp; Pendências</div>
        <div class="nav-item">⚖ &nbsp; Acareações</div>
        <div class="nav-item">◔ &nbsp; Performance</div>
        <div class="nav-item">▤ &nbsp; Relatórios</div>
        <div class="nav-item">! &nbsp; Alertas</div>
        <div class="nav-item">⚙ &nbsp; Configurações</div>

        <div class="side-note">
            <b>Dashboard Gerencial</b><br>
            Atualização automática<br>
            Fonte: Base Gerencial Torre
        </div>
        """,
        unsafe_allow_html=True,
    )


refresh_col, _ = st.columns([1, 8])
with refresh_col:
    if st.button("↻ Atualizar", use_container_width=True):
        st.rerun()

try:
    pack = load_source(SOURCE_URL)
except Exception as exc:
    st.error(f"Não foi possível atualizar o dashboard: {exc}")
    st.stop()

resumo = pack.get("RESUMO", pd.DataFrame())
fila = pack.get("FILA", pd.DataFrame())
top_problemas = pack.get("TOP_PROBLEMAS", pd.DataFrame())
top_bases = pack.get("TOP_BASES", pd.DataFrame())

periodo = summary_value(resumo, "Período analisado", "")
if not periodo:
    periodo = summary_value(resumo, "Data de análise", "")

atualizado = summary_value(resumo, "Atualizado em", "")

st.markdown(
    f"""
    <div class="hero">
        <span class="badge">TORRE DE CONTROLE</span>
        <span class="badge">VISÃO EXECUTIVA</span>
        <span class="badge">PERÍODO ANALISADO: {periodo}</span>
        <span class="badge">ATUALIZADO EM: {atualizado}</span>
        <h1>Dashboard Executivo da Torre</h1>
        <p>Panorama gerencial das pendências, riscos operacionais e ações prioritárias.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="info">ⓘ AWBs monitoradas representam AWBs únicas da carteira atual, não entregas concluídas.</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="section-title">VISÃO EXECUTIVA</div>', unsafe_allow_html=True)

r1 = st.columns(6)

with r1[0]:
    card(
        "AWBs MONITORADAS",
        fmt_int(summary_value(resumo, "AWBs monitoradas", 0)),
        "Carteira única atualmente acompanhada",
        "▣",
        "#2f6fed",
        "#edf4ff",
    )

with r1[1]:
    card(
        "ENTREGA EM ATRASO",
        fmt_int(summary_value(resumo, "Entrega em atraso", 0)),
        "Cargas com SLA vencido",
        "◷",
        "#d92d20",
        "#fff0ef",
        "#c9231a",
    )

with r1[2]:
    card(
        "SLA DO DIA SEM ROTA",
        fmt_int(summary_value(resumo, "SLA do dia sem rota", 0)),
        "Cargas do dia ainda sem rota criada",
        "▦",
        "#d97706",
        "#fff7e8",
        "#b96804",
    )

with r1[3]:
    card(
        "BACKLOG DA TORRE",
        fmt_int(summary_value(resumo, "Backlog da Torre", 0)),
        "Pendências ainda não finalizadas",
        "≡",
        "#6d3fd1",
        "#f4efff",
        "#5b2dbf",
    )

with r1[4]:
    card(
        "ACAREAÇÕES EM ANDAMENTO",
        fmt_int(summary_value(resumo, "Acareações em andamento", 0)),
        "Tratativas ativas neste momento",
        "⚖",
        "#2459c4",
        "#edf4ff",
        "#16449f",
    )

with r1[5]:
    card(
        "VALOR EM ACAREAÇÃO",
        brl(summary_value(resumo, "Valor em acareação", 0)),
        "Valor financeiro atualmente exposto",
        "$",
        "#17633a",
        "#edf9f1",
        "#14532d",
    )

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

c1, c2 = st.columns([1, 1.2])

with c1:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">ONDE ESTÁ O PROBLEMA?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel-sub">Distribuição das pendências por categoria operacional.</div>',
        unsafe_allow_html=True,
    )

    chart_df = chart_dataframe(top_problemas)
    if not chart_df.empty:
        st.bar_chart(chart_df)
        st.dataframe(top_problemas, use_container_width=True, hide_index=True)
    else:
        st.info("Sem problemas priorizados.")

    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">MAIORES CONCENTRAÇÕES DE PENDÊNCIA</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel-sub">Bases ou responsáveis com maior volume de pendências em aberto.</div>',
        unsafe_allow_html=True,
    )

    chart_df = chart_dataframe(top_bases)
    if not chart_df.empty:
        st.bar_chart(chart_df)
        st.dataframe(top_bases, use_container_width=True, hide_index=True)
    else:
        st.info("Sem concentrações de pendência para exibir.")

    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown('<div class="panel-title">FILA EXECUTIVA DE ATENÇÃO</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="panel-sub">Pendências críticas e de maior impacto que exigem acompanhamento gerencial.</div>',
    unsafe_allow_html=True,
)

if not fila.empty:
    cols = [
        c for c in [
            "PRIORIDADE",
            "PROBLEMA",
            "CLIENTE",
            "LOCALIZAÇÃO / RESPONSÁVEL",
            "AWB",
            "PRÓXIMA AÇÃO",
        ]
        if c in fila.columns
    ]
    st.dataframe(
        (fila[cols] if cols else fila).head(15),
        use_container_width=True,
        hide_index=True,
        height=430,
    )
else:
    st.info("Sem ações executivas para exibir.")

st.markdown('</div>', unsafe_allow_html=True)
