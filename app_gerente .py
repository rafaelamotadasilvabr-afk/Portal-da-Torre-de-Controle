import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Dashboard Executivo da Torre",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_MANAGER_SOURCE_URL = ""

st.markdown("""
<style>
.stApp { background: #f5f7fb; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #06162f 0%, #082347 65%, #061a36 100%);
}

[data-testid="stSidebar"] * { color: #e5edf8; }

.block-container {
    padding-top: 0.4rem;
    padding-bottom: 1.4rem;
    max-width: 1680px;
}

.brand {
    padding: 8px 4px 20px 4px;
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
}

.exec-header {
    background: linear-gradient(120deg, #071a37 0%, #082347 60%, #103b76 100%);
    color: #ffffff;
    border-radius: 0 0 20px 20px;
    padding: 22px 28px 20px 28px;
    margin: -0.4rem -0.2rem 12px -0.2rem;
    box-shadow: 0 12px 28px rgba(8,35,71,.16);
}

.pill {
    display: inline-block;
    padding: 6px 10px;
    margin: 0 7px 10px 0;
    border: 1px solid rgba(255,255,255,.22);
    background: rgba(255,255,255,.08);
    color: #ffffff;
    border-radius: 8px;
    font-size: .74rem;
    font-weight: 750;
}

.exec-header h1 {
    margin: 0 0 5px 0;
    font-size: 2rem;
    letter-spacing: -.035em;
}

.exec-header p {
    margin: 0;
    color: #dbeafe;
    font-size: .94rem;
}

.info-strip {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 10px 13px;
    color: #52637c;
    font-size: .80rem;
    margin-bottom: 12px;
}

.section-title {
    color: #10213d;
    font-size: .95rem;
    font-weight: 850;
    margin: 6px 0 10px 0;
}

.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 15px;
    padding: 14px;
    min-height: 138px;
    box-shadow: 0 8px 20px rgba(15,23,42,.05);
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

.kpi-label {
    color: #334155;
    font-size: .76rem;
    font-weight: 850;
    text-transform: uppercase;
    min-height: 30px;
}

.kpi-value {
    color: var(--value);
    font-size: 1.85rem;
    font-weight: 950;
    letter-spacing: -.04em;
    margin: 6px 0;
}

.kpi-sub {
    color: #708099;
    font-size: .70rem;
    line-height: 1.35;
}

.panel {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 8px 22px rgba(15,23,42,.045);
    margin-bottom: 12px;
}

.panel-title {
    color: #10213d;
    font-size: 1.02rem;
    font-weight: 850;
    margin-bottom: 3px;
}

.panel-sub {
    color: #718096;
    font-size: .76rem;
    margin-bottom: 12px;
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
}
</style>
""", unsafe_allow_html=True)


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
        raise RuntimeError("Credenciais gcp_service_account não configuradas no app do gerente.")

    spreadsheet = gc.open_by_url(url)
    result = {}

    for sheet_name in ["RESUMO", "FILA", "TOP_PROBLEMAS", "TOP_BASES"]:
        try:
            ws = spreadsheet.worksheet(sheet_name)
            values = ws.get_all_values()

            if not values:
                result[sheet_name] = pd.DataFrame()
                continue

            result[sheet_name] = pd.DataFrame(values[1:], columns=values[0])
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


def kpi_card(label, value, subtitle, icon, accent, soft, value_color=None):
    value_color = value_color or "#10213d"
    st.markdown(
        f"""
        <div class="kpi-card" style="--accent:{accent};--soft:{soft};--value:{value_color};">
            <div class="kpi-icon">{icon}</div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def numeric_chart_df(df):
    if df is None or df.empty or len(df.columns) < 2:
        return pd.DataFrame()

    label_col = df.columns[0]
    value_col = df.columns[-1]

    out = df[[label_col, value_col]].copy()
    out[value_col] = pd.to_numeric(
        out[value_col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0)

    out = out[out[value_col] > 0]
    if out.empty:
        return pd.DataFrame()

    return out.sort_values(value_col, ascending=False).head(10).set_index(label_col)


try:
    SOURCE_URL = st.secrets.get("MANAGER_SOURCE_URL", "")
except Exception:
    SOURCE_URL = ""

if not SOURCE_URL:
    SOURCE_URL = DEFAULT_MANAGER_SOURCE_URL

if not SOURCE_URL:
    st.error("Fonte automática não configurada. Adicione MANAGER_SOURCE_URL nos Secrets.")
    st.stop()


with st.sidebar:
    st.markdown(
        """
        <div class="brand">
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
    <div class="exec-header">
        <span class="pill">TORRE DE CONTROLE</span>
        <span class="pill">VISÃO EXECUTIVA</span>
        <span class="pill">PERÍODO ANALISADO: {periodo}</span>
        <span class="pill">ATUALIZADO EM: {atualizado}</span>
        <h1>Dashboard Executivo da Torre</h1>
        <p>Panorama gerencial das pendências, riscos operacionais e ações prioritárias.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="info-strip">ⓘ AWBs monitoradas representam AWBs únicas da carteira atual, não entregas concluídas.</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="section-title">VISÃO EXECUTIVA</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    kpi_card("AWBs Monitoradas", fmt_int(summary_value(resumo, "AWBs monitoradas", 0)), "Carteira única atualmente acompanhada", "▣", "#2f6fed", "#edf4ff")
with k2:
    kpi_card("Entrega em atraso", fmt_int(summary_value(resumo, "Entrega em atraso", 0)), "Cargas com SLA vencido", "◷", "#d92d20", "#fff0ef", "#c9231a")
with k3:
    kpi_card("SLA do dia sem rota", fmt_int(summary_value(resumo, "SLA do dia sem rota", 0)), "Cargas do dia ainda sem rota criada", "▦", "#d97706", "#fff7e8", "#b96804")
with k4:
    kpi_card("Backlog da Torre", fmt_int(summary_value(resumo, "Backlog da Torre", 0)), "Pendências ainda não finalizadas", "≡", "#6d3fd1", "#f4efff", "#5b2dbf")
with k5:
    kpi_card("Acareações em andamento", fmt_int(summary_value(resumo, "Acareações em andamento", 0)), "Tratativas ativas neste momento", "⚖", "#2459c4", "#edf4ff", "#16449f")
with k6:
    kpi_card("Valor em acareação", brl(summary_value(resumo, "Valor em acareação", 0)), "Valor financeiro atualmente exposto", "$", "#17633a", "#edf9f1", "#14532d")

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

c1, c2 = st.columns([1, 1.2])

with c1:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Onde está o problema?</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-sub">Distribuição das pendências por categoria operacional.</div>', unsafe_allow_html=True)
    chart = numeric_chart_df(top_problemas)
    if not chart.empty:
        st.bar_chart(chart)
        st.dataframe(top_problemas, use_container_width=True, hide_index=True)
    else:
        st.info("Sem problemas priorizados.")
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Maiores concentrações de pendência</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-sub">Bases ou responsáveis com maior volume de pendências em aberto.</div>', unsafe_allow_html=True)
    chart = numeric_chart_df(top_bases)
    if not chart.empty:
        st.bar_chart(chart)
        st.dataframe(top_bases, use_container_width=True, hide_index=True)
    else:
        st.info("Sem concentrações de pendência para exibir.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown('<div class="panel-title">Fila executiva de atenção</div>', unsafe_allow_html=True)
st.markdown('<div class="panel-sub">Pendências críticas e de maior impacto que exigem acompanhamento gerencial.</div>', unsafe_allow_html=True)

if not fila.empty:
    preferred_cols = [
        "PRIORIDADE",
        "PROBLEMA",
        "CLIENTE",
        "LOCALIZAÇÃO / RESPONSÁVEL",
        "AWB",
        "PRÓXIMA AÇÃO",
    ]
    cols = [c for c in preferred_cols if c in fila.columns]
    queue = fila[cols].copy() if cols else fila.copy()
    st.dataframe(queue.head(15), use_container_width=True, hide_index=True, height=430)
else:
    st.info("Sem ações executivas para exibir.")

st.markdown('</div>', unsafe_allow_html=True)
