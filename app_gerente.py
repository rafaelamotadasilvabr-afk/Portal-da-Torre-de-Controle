import io
import re
import pandas as pd
import requests
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Dashboard Executivo da Torre",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Fonte fixa opcional no próprio código.
# Preferencialmente configure pelo Streamlit Secrets:
# MANAGER_SOURCE_URL = "https://..."
DEFAULT_MANAGER_SOURCE_URL = ""

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 0.8rem;
        padding-bottom: 1.2rem;
        max-width: 1550px;
    }
    .hero {
        background: linear-gradient(135deg, #081b3b 0%, #0e3976 48%, #1d5fd1 100%);
        color: white;
        border-radius: 22px;
        padding: 22px 26px;
        margin-bottom: 14px;
        box-shadow: 0 14px 36px rgba(15, 45, 100, 0.22);
    }
    .hero h1 {
        margin: 0 0 4px 0;
        font-size: 2rem;
        letter-spacing: -0.035em;
    }
    .hero p {
        margin: 0;
        opacity: 0.90;
        font-size: 0.95rem;
    }
    .badge {
        display: inline-block;
        padding: 6px 10px;
        margin: 0 7px 8px 0;
        border-radius: 999px;
        background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.2);
        font-size: 0.78rem;
        font-weight: 600;
    }
    .section-title {
        font-size: 1rem;
        font-weight: 800;
        color: #10213d;
        margin: 8px 0 8px 0;
    }
    .kpi {
        background: #ffffff;
        border: 1px solid #e7ecf3;
        border-radius: 18px;
        padding: 15px 16px;
        min-height: 118px;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.055);
    }
    .line {
        height: 5px;
        border-radius: 999px;
        margin-bottom: 12px;
    }
    .blue {background: linear-gradient(90deg,#2563eb,#60a5fa);}
    .red {background: linear-gradient(90deg,#dc2626,#fb7185);}
    .amber {background: linear-gradient(90deg,#d97706,#fbbf24);}
    .violet {background: linear-gradient(90deg,#7c3aed,#c084fc);}
    .slate {background: linear-gradient(90deg,#334155,#94a3b8);}
    .label {
        color: #526078;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 7px;
    }
    .value {
        color: #10213d;
        font-size: 1.95rem;
        font-weight: 850;
        line-height: 1;
        margin-bottom: 7px;
        letter-spacing: -0.03em;
    }
    .sub {
        color: #7a879a;
        font-size: 0.75rem;
        line-height: 1.25;
    }
    .panel {
        background: #ffffff;
        border: 1px solid #e7ecf3;
        border-radius: 18px;
        padding: 15px 17px;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.045);
        margin-bottom: 12px;
    }
    .info {
        background: #f7f9fc;
        border: 1px solid #e6ebf2;
        border-radius: 13px;
        padding: 10px 13px;
        color: #56657c;
        font-size: 0.82rem;
        margin-bottom: 12px;
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


def brl(value):
    n = pd.to_numeric(value, errors="coerce")
    n = 0 if pd.isna(n) else float(n)
    return f"R$ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def card(label, value, tone, subtitle):
    st.markdown(
        f"""
        <div class="kpi">
            <div class="line {tone}"></div>
            <div class="label">{label}</div>
            <div class="value">{value}</div>
            <div class="sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Lê automaticamente a fonte configurada uma única vez.
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

refresh_col, _ = st.columns([1, 6])
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
    '<div class="info">AWBs monitoradas representam AWBs únicas da carteira atual, não entregas concluídas.</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="section-title">VISÃO EXECUTIVA</div>', unsafe_allow_html=True)

r1 = st.columns(4)
with r1[0]:
    card(
        "AWBs MONITORADAS",
        number(summary_value(resumo, "AWBs monitoradas", 0)),
        "blue",
        "Carteira única atualmente acompanhada",
    )
with r1[1]:
    card(
        "AWBs COM AÇÃO",
        number(summary_value(resumo, "AWBs com ação", 0)),
        "slate",
        "Registros que exigem atuação operacional",
    )
with r1[2]:
    card(
        "AÇÕES IMEDIATAS",
        number(summary_value(resumo, "Ações imediatas", 0)),
        "red",
        "Prioridade máxima de atuação",
    )
with r1[3]:
    card(
        "ENTREGA EM ATRASO",
        number(summary_value(resumo, "Entrega em atraso", 0)),
        "red",
        "Cargas com SLA vencido",
    )

r2 = st.columns(4)
with r2[0]:
    card(
        "SLA DO DIA SEM ROTA",
        number(summary_value(resumo, "SLA do dia sem rota", 0)),
        "amber",
        "Cargas do dia ainda sem rota criada",
    )
with r2[1]:
    card(
        "BACKLOG DA TORRE",
        number(summary_value(resumo, "Backlog da Torre", 0)),
        "violet",
        "Pendências ainda não finalizadas",
    )
with r2[2]:
    card(
        "ACAREAÇÕES EM ANDAMENTO",
        number(summary_value(resumo, "Acareações em andamento", 0)),
        "blue",
        "Tratativas ativas neste momento",
    )
with r2[3]:
    card(
        "VALOR EM ACAREAÇÃO",
        brl(summary_value(resumo, "Valor em acareação", 0)),
        "amber",
        "Valor financeiro atualmente exposto",
    )

c1, c2 = st.columns(2)

with c1:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">ONDE ESTÁ O PROBLEMA?</div>', unsafe_allow_html=True)
    if not top_problemas.empty:
        value_col = top_problemas.columns[-1]
        label_col = top_problemas.columns[0]
        st.bar_chart(top_problemas.set_index(label_col)[[value_col]])
        st.dataframe(top_problemas, use_container_width=True, hide_index=True)
    else:
        st.info("Sem problemas priorizados.")
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">PRINCIPAIS OFENSORES</div>', unsafe_allow_html=True)
    if not top_bases.empty:
        value_col = top_bases.columns[-1]
        label_col = top_bases.columns[0]
        st.bar_chart(top_bases.set_index(label_col)[[value_col]])
        st.dataframe(top_bases, use_container_width=True, hide_index=True)
    else:
        st.info("Sem ofensores priorizados.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown('<div class="section-title">FILA EXECUTIVA DE ATENÇÃO</div>', unsafe_allow_html=True)

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
        fila[cols] if cols else fila,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Sem ações executivas para exibir.")

st.markdown('</div>', unsafe_allow_html=True)
