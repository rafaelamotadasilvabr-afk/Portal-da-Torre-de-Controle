import re
import unicodedata
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

# =========================================================
# CSS SEGURO
# Não usamos DIVs abertas envolvendo charts/dataframes.
# Isso evita erro visual do Streamlit no navegador.
# =========================================================
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
        padding: 8px 6px 18px 6px;
        border-bottom: 1px solid rgba(255,255,255,.12);
        margin-bottom: 14px;
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

    .side-note {
        margin-top: 20px;
        border-top: 1px solid rgba(255,255,255,.12);
        padding-top: 14px;
        color: #b9c8dc;
        font-size: .76rem;
        line-height: 1.5;
    }

    [data-testid="stSidebar"] div[data-testid="stButton"] button {
        width: 100%;
        justify-content: flex-start;
        text-align: left;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,.08);
        background: transparent;
        color: #e5edf8;
        font-weight: 700;
        padding: 0.65rem 0.8rem;
        margin-bottom: 0.25rem;
    }

    [data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(90deg, #0b4ea7, #123b76);
        color: #ffffff;
        box-shadow: 0 8px 18px rgba(0,0,0,.14);
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

    .soft-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px 18px;
        box-shadow: 0 8px 22px rgba(15,23,42,.045);
        margin-bottom: 12px;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        overflow: hidden;
    }

    div[data-testid="stDownloadButton"] button {
        border-radius: 10px;
        border: 1px solid #cbd5e1;
        background: #ffffff;
        color: #10213d;
        font-weight: 750;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# GOOGLE SHEETS
# =========================================================
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


# =========================================================
# HELPERS
# =========================================================
def normalize_text(value):
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


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
        series.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False),
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


def filtered_rows(df, terms):
    if df is None or df.empty:
        return pd.DataFrame()

    text = df.astype(str).agg(" ".join, axis=1).apply(normalize_text)
    mask = False
    for term in terms:
        mask = mask | text.str.contains(normalize_text(term), na=False)
    return df[mask].copy()


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


def section_header(title, subtitle=None):
    st.markdown(f"### {title}")
    if subtitle:
        st.caption(subtitle)


def render_kpis(resumo):
    cols = st.columns(6)

    with cols[0]:
        card(
            "AWBs MONITORADAS",
            fmt_int(summary_value(resumo, "AWBs monitoradas", 0)),
            "Carteira única atualmente acompanhada",
            "▣",
            "#2f6fed",
            "#edf4ff",
        )

    with cols[1]:
        card(
            "ENTREGA EM ATRASO",
            fmt_int(summary_value(resumo, "Entrega em atraso", 0)),
            "Cargas com SLA vencido",
            "◷",
            "#d92d20",
            "#fff0ef",
            "#c9231a",
        )

    with cols[2]:
        card(
            "SLA DO DIA SEM ROTA",
            fmt_int(summary_value(resumo, "SLA do dia sem rota", 0)),
            "SLA hoje sem rota criada no Eu Entrego",
            "▦",
            "#d97706",
            "#fff7e8",
            "#b96804",
        )

    with cols[3]:
        card(
            "BACKLOG DA TORRE",
            fmt_int(summary_value(resumo, "Backlog da Torre", 0)),
            "Pendências ainda não finalizadas",
            "≡",
            "#6d3fd1",
            "#f4efff",
            "#5b2dbf",
        )

    with cols[4]:
        card(
            "ACAREAÇÕES EM ANDAMENTO",
            fmt_int(summary_value(resumo, "Acareações em andamento", 0)),
            "Tratativas ativas neste momento",
            "⚖",
            "#2459c4",
            "#edf4ff",
            "#16449f",
        )

    with cols[5]:
        card(
            "VALOR EM ACAREAÇÃO",
            brl(summary_value(resumo, "Valor em acareação", 0)),
            "Valor financeiro atualmente exposto",
            "$",
            "#17633a",
            "#edf9f1",
            "#14532d",
        )


def render_table(df, height=360):
    if df is None or df.empty:
        st.info("Sem dados para exibir.")
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=height,
    )


# =========================================================
# FONTE
# =========================================================
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


# =========================================================
# SIDEBAR FUNCIONAL
# =========================================================
with st.sidebar:
    st.markdown(
        """
        <div class="brand-box">
            <div class="brand-main">GDS</div>
            <div class="brand-sub">LOGÍSTICA</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    menu_items = [
        ("visao", "⌂  Visão Geral"),
        ("monitoramento", "↗  Monitoramento"),
        ("pendencias", "▣  Pendências"),
        ("acareacoes", "⚖  Acareações"),
        ("performance", "◔  Performance"),
        ("relatorios", "▤  Relatórios"),
        ("alertas", "!  Alertas"),
        ("configuracoes", "⚙  Configurações"),
    ]

    if "menu_gerente" not in st.session_state:
        st.session_state["menu_gerente"] = "visao"

    for key, label in menu_items:
        active = st.session_state["menu_gerente"] == key
        if st.button(
            label,
            key=f"menu_btn_{key}",
            use_container_width=True,
            type="primary" if active else "secondary",
        ):
            st.session_state["menu_gerente"] = key
            st.rerun()

    st.markdown(
        """
        <div class="side-note">
            <b>Dashboard Gerencial</b><br>
            Menu funcional<br>
            Fonte: Base Gerencial Torre
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# CARREGAMENTO
# =========================================================
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

menu = st.session_state["menu_gerente"]


# =========================================================
# HEADER
# =========================================================
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


# =========================================================
# PÁGINAS
# =========================================================
if menu == "visao":
    st.markdown('<div class="section-title">VISÃO EXECUTIVA</div>', unsafe_allow_html=True)
    render_kpis(resumo)
    st.divider()

    c1, c2 = st.columns([1, 1.2])

    with c1:
        section_header(
            "Onde está o problema?",
            "Distribuição das pendências por categoria operacional.",
        )
        chart_df = chart_dataframe(top_problemas)
        if not chart_df.empty:
            st.bar_chart(chart_df)
        render_table(top_problemas, height=260)

    with c2:
        section_header(
            "Maiores concentrações de pendência",
            "Bases ou responsáveis com maior volume de pendências em aberto.",
        )
        chart_df = chart_dataframe(top_bases)
        if not chart_df.empty:
            st.bar_chart(chart_df)
        render_table(top_bases, height=260)

    st.divider()
    section_header(
        "Fila executiva de atenção",
        "Pendências críticas e de maior impacto que exigem acompanhamento gerencial.",
    )
    preferred_cols = [
        "PRIORIDADE",
        "PROBLEMA",
        "CLIENTE",
        "LOCALIZAÇÃO / RESPONSÁVEL",
        "AWB",
        "PRÓXIMA AÇÃO",
    ]
    cols = [c for c in preferred_cols if c in fila.columns]
    render_table((fila[cols] if cols else fila).head(15) if not fila.empty else fila, height=430)


elif menu == "monitoramento":
    section_header(
        "Monitoramento",
        "Visão operacional resumida dos principais indicadores do painel.",
    )
    render_kpis(resumo)
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        section_header("Distribuição por problema")
        chart_df = chart_dataframe(top_problemas)
        if not chart_df.empty:
            st.bar_chart(chart_df)
        render_table(top_problemas, height=300)

    with c2:
        section_header("Concentração por base/responsável")
        chart_df = chart_dataframe(top_bases)
        if not chart_df.empty:
            st.bar_chart(chart_df)
        render_table(top_bases, height=300)


elif menu == "pendencias":
    section_header(
        "Pendências",
        "Fila e categorias de pendências para acompanhamento gerencial.",
    )

    c1, c2 = st.columns(2)
    with c1:
        section_header("Onde está o problema?")
        chart_df = chart_dataframe(top_problemas)
        if not chart_df.empty:
            st.bar_chart(chart_df)
        render_table(top_problemas, height=320)

    with c2:
        section_header("Maiores concentrações de pendência")
        chart_df = chart_dataframe(top_bases)
        if not chart_df.empty:
            st.bar_chart(chart_df)
        render_table(top_bases, height=320)

    st.divider()
    section_header("Fila de pendências")
    render_table(fila, height=500)


elif menu == "acareacoes":
    section_header(
        "Acareações",
        "Resumo financeiro e operacional das acareações em andamento.",
    )

    c1, c2 = st.columns(2)
    with c1:
        card(
            "ACAREAÇÕES EM ANDAMENTO",
            fmt_int(summary_value(resumo, "Acareações em andamento", 0)),
            "Tratativas ativas neste momento",
            "⚖",
            "#2459c4",
            "#edf4ff",
            "#16449f",
        )

    with c2:
        card(
            "VALOR EM ACAREAÇÃO",
            brl(summary_value(resumo, "Valor em acareação", 0)),
            "Valor financeiro atualmente exposto",
            "$",
            "#17633a",
            "#edf9f1",
            "#14532d",
        )

    st.divider()
    section_header("Itens relacionados a acareação")
    acareacao_df = filtered_rows(fila, ["ACAREACAO", "ACAREAÇÃO", "RESSALVA"])
    render_table(acareacao_df if not acareacao_df.empty else fila.head(0), height=500)


elif menu == "performance":
    section_header(
        "Performance",
        "Indicadores para leitura executiva da operação.",
    )
    render_kpis(resumo)
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        section_header("Problemas priorizados")
        chart_df = chart_dataframe(top_problemas)
        if not chart_df.empty:
            st.bar_chart(chart_df)

    with c2:
        section_header("Bases/responsáveis com maior concentração")
        chart_df = chart_dataframe(top_bases)
        if not chart_df.empty:
            st.bar_chart(chart_df)


elif menu == "relatorios":
    section_header(
        "Relatórios",
        "Consulta e exportação dos dados sincronizados para o dashboard gerencial.",
    )

    tabs = st.tabs(["Resumo", "Fila", "Top problemas", "Top bases"])

    with tabs[0]:
        render_table(resumo, height=400)
        st.download_button(
            "Baixar RESUMO.csv",
            resumo.to_csv(index=False).encode("utf-8-sig"),
            file_name="resumo_gerencial.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with tabs[1]:
        render_table(fila, height=500)
        st.download_button(
            "Baixar FILA.csv",
            fila.to_csv(index=False).encode("utf-8-sig"),
            file_name="fila_executiva.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with tabs[2]:
        render_table(top_problemas, height=400)
        st.download_button(
            "Baixar TOP_PROBLEMAS.csv",
            top_problemas.to_csv(index=False).encode("utf-8-sig"),
            file_name="top_problemas.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with tabs[3]:
        render_table(top_bases, height=400)
        st.download_button(
            "Baixar TOP_BASES.csv",
            top_bases.to_csv(index=False).encode("utf-8-sig"),
            file_name="top_bases.csv",
            mime="text/csv",
            use_container_width=True,
        )


elif menu == "alertas":
    section_header(
        "Alertas",
        "Itens críticos e de alta prioridade para ação gerencial.",
    )

    a1, a2, a3 = st.columns(3)
    with a1:
        card(
            "3ª TENTATIVA DE ENTREGA",
            fmt_int(summary_value(resumo, "3ª tentativa de entrega", 0)),
            "Cargas com 3 ou mais tentativas registradas",
            "3ª",
            "#d92d20",
            "#fff0ef",
            "#c9231a",
        )
    with a2:
        card(
            "ENTREGA EM ATRASO",
            fmt_int(summary_value(resumo, "Entrega em atraso", 0)),
            "Cargas com SLA vencido",
            "◷",
            "#d92d20",
            "#fff0ef",
            "#c9231a",
        )
    with a3:
        card(
            "SLA DO DIA SEM ROTA",
            fmt_int(summary_value(resumo, "SLA do dia sem rota", 0)),
            "SLA hoje sem rota criada no Eu Entrego",
            "▦",
            "#d97706",
            "#fff7e8",
            "#b96804",
        )

    st.divider()
    st.markdown("#### 3ª tentativa de entrega")
    terceira = filtered_rows(fila, ["3A TENTATIVA", "3ª TENTATIVA", "TERCEIRA TENTATIVA"])
    render_table(terceira if not terceira.empty else fila.head(0), height=300)

    st.divider()
    st.markdown("#### Demais alertas críticos")
    alertas = filtered_rows(fila, ["CRITICA", "CRÍTICA", "ALTA", "ATRASO", "SLA"])
    render_table(alertas if not alertas.empty else fila.head(0), height=420)


elif menu == "configuracoes":
    section_header(
        "Configurações",
        "Status técnico da fonte de dados e conexão do dashboard.",
    )

    st.success("Dashboard carregado com sucesso.")
    st.write("Fonte configurada:", SOURCE_URL)
    st.write("Abas lidas da base gerencial:")

    status_df = pd.DataFrame(
        [
            {"Aba": "RESUMO", "Linhas": len(resumo)},
            {"Aba": "FILA", "Linhas": len(fila)},
            {"Aba": "TOP_PROBLEMAS", "Linhas": len(top_problemas)},
            {"Aba": "TOP_BASES", "Linhas": len(top_bases)},
        ]
    )
    render_table(status_df, height=240)

    st.info(
        "Os Secrets necessários continuam sendo MANAGER_SOURCE_URL e [gcp_service_account]."
    )
