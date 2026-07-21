import io
import re
import unicodedata
from datetime import date, timedelta

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
# CSS — LAYOUT CLARO
# =========================================================
st.markdown(
    """
    <style>
    .stApp {
        background: #f6f8fb;
        color: #0f172a;
    }

    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e2e8f0;
    }

    [data-testid="stSidebar"] * {
        color: #0f172a;
    }

    .block-container {
        padding-top: 0.65rem;
        padding-bottom: 1.5rem;
        max-width: 1650px;
    }

    .brand-box {
        padding: 8px 6px 18px 6px;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 14px;
    }

    .brand-main {
        color: #0a2146;
        font-size: 3rem;
        font-weight: 950;
        font-style: italic;
        letter-spacing: -.06em;
        line-height: .9;
    }

    .brand-sub {
        color: #0a2146;
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: .42em;
        margin-top: 8px;
    }

    [data-testid="stSidebar"] div[data-testid="stButton"] button {
        width: 100%;
        justify-content: flex-start;
        text-align: left;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        background: #ffffff;
        color: #0f172a;
        font-weight: 700;
        padding: 0.65rem 0.8rem;
        margin-bottom: 0.25rem;
    }

    [data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
        background: #e8f1ff;
        color: #0b4ea7;
        border-color: #b8d4ff;
        box-shadow: 0 8px 18px rgba(37, 99, 235, .08);
    }

    .side-note {
        margin-top: 20px;
        border-top: 1px solid #e2e8f0;
        padding-top: 14px;
        color: #64748b;
        font-size: .76rem;
        line-height: 1.5;
    }

    .hero {
        background: linear-gradient(120deg, #ffffff 0%, #f2f7ff 62%, #e8f1ff 100%);
        color: #0f172a;
        border: 1px solid #dbe7fb;
        border-radius: 20px;
        padding: 22px 26px;
        margin-bottom: 14px;
        box-shadow: 0 10px 24px rgba(15, 23, 42, .045);
    }

    .hero h1 {
        margin: 0 0 5px 0;
        font-size: 2rem;
        letter-spacing: -0.035em;
    }

    .hero p {
        margin: 0;
        color: #475569;
        font-size: 0.94rem;
    }

    .badge {
        display: inline-block;
        padding: 6px 10px;
        margin: 0 7px 10px 0;
        border-radius: 8px;
        background: #ffffff;
        border: 1px solid #cbdffb;
        color: #0b4ea7;
        font-size: 0.74rem;
        font-weight: 750;
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

    .section-title {
        font-size: 1.05rem;
        font-weight: 850;
        color: #10213d;
        margin: 10px 0 4px 0;
    }

    .small-muted {
        color: #64748b;
        font-size: .80rem;
        margin-bottom: 10px;
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

    div[data-testid="stButton"] button {
        border-radius: 10px;
        font-weight: 750;
    }

    .detail-box {
        background: #ffffff;
        border: 1px solid #dbe7fb;
        border-left: 5px solid #2563eb;
        border-radius: 16px;
        padding: 16px 18px;
        margin-top: 14px;
        margin-bottom: 14px;
        box-shadow: 0 8px 22px rgba(15,23,42,.045);
    }

    .detail-title {
        color: #10213d;
        font-size: 1.06rem;
        font-weight: 900;
        margin-bottom: 3px;
    }

    .detail-sub {
        color: #64748b;
        font-size: .78rem;
        margin-bottom: 10px;
    }

    .detail-count {
        display: inline-block;
        padding: 4px 9px;
        border-radius: 999px;
        background: #eff6ff;
        color: #0b4ea7;
        font-size: .74rem;
        font-weight: 850;
        margin-bottom: 8px;
    }

    .filter-caption {
        color: #475569;
        font-size: .76rem;
        font-weight: 800;
        margin-bottom: 4px;
        text-align: right;
    }

    .filter-note-compact {
        color: #64748b;
        font-size: .72rem;
        text-align: right;
        margin-top: -6px;
        margin-bottom: 8px;
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


def first_col(df, names):
    if df is None or df.empty:
        return None
    norm_map = {normalize_text(c): c for c in df.columns}
    for name in names:
        key = normalize_text(name)
        if key in norm_map:
            return norm_map[key]
    return None


def parse_date_col(series):
    return pd.to_datetime(series, errors="coerce", dayfirst=True)


def numeric_series(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0)


def as_text_blob(df):
    if df is None or df.empty:
        return pd.Series(dtype=str)
    return df.astype(str).agg(" ".join, axis=1).map(normalize_text)


def filter_terms(df, terms):
    if df is None or df.empty:
        return pd.DataFrame()
    blob = as_text_blob(df)
    mask = pd.Series(False, index=df.index)
    for term in terms:
        mask = mask | blob.str.contains(normalize_text(term), na=False)
    return df[mask].copy()


def apply_date_filter(df, date_range):
    if df is None or df.empty:
        return df, "sem dados"

    if not isinstance(date_range, (list, tuple)) or len(date_range) != 2:
        return df, "sem período definido"

    start, end = date_range
    if start is None or end is None:
        return df, "sem período definido"

    date_candidates = [
        "DATA ANÁLISE",
        "SLA",
        "ÚLTIMA ROTA",
        "DATA EVENTO TORRE",
        "ÚLTIMA ALTERAÇÃO",
    ]

    for col_name in date_candidates:
        col = first_col(df, [col_name])
        if col:
            dates = parse_date_col(df[col])
            if dates.notna().any():
                start_ts = pd.Timestamp(start)
                end_ts = pd.Timestamp(end)
                mask = dates.dt.normalize().between(start_ts.normalize(), end_ts.normalize())
                return df[mask].copy(), f"Filtro aplicado por {col}"

    return df, "sem coluna de data disponível na fila"


def kpi_card(label, value, subtitle, icon, accent, soft, value_color=None):
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


def render_table(df, height=340):
    if df is None or df.empty:
        st.info("Sem dados para exibir.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def detail_columns(df):
    if df is None or df.empty:
        return df

    preferred = [
        "PRIORIDADE",
        "AWB",
        "CLIENTE",
        "PROBLEMA",
        "SLA",
        "DIAS EM ATRASO",
        "MOTORISTA / ENTREGADOR",
        "STATUS ÚLTIMA ROTA",
        "MOTIVO ÚLTIMA ROTA",
        "ÚLTIMA ROTA",
        "DIAS DESDE ÚLTIMA ROTA",
        "QT TENTATIVAS",
        "LOCALIZAÇÃO / RESPONSÁVEL",
        "PRÓXIMA AÇÃO",
        "MOTIVO PENDÊNCIA",
        "STATUS TORRE",
        "ABA TORRE",
    ]
    cols = [c for c in preferred if c in df.columns]
    return df[cols].copy() if cols else df.copy()


def overdue_delivery_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    atraso_col = first_col(df, ["DIAS EM ATRASO"])
    if atraso_col:
        dias = numeric_series(df[atraso_col])
        atraso_df = df[dias > 0].copy()
        if not atraso_df.empty:
            return atraso_df

    return filter_terms(df, ["ENTREGA EM ATRASO", "ATRASO", "SLA VENCIDO"])


def sla_sem_rota_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return filter_terms(df, ["SLA DO DIA SEM ROTA", "SLA SEM ROTA", "SEM ROTA"])


def terceira_tentativa_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    tent_col = first_col(df, ["QT TENTATIVAS", "QT_TENTATIVAS_INSUCESSO"])
    if tent_col:
        tent = numeric_series(df[tent_col])
        tentativa_df = df[tent >= 3].copy()
        if not tentativa_df.empty:
            return tentativa_df

    return filter_terms(df, ["3A TENTATIVA", "3ª TENTATIVA", "TERCEIRA TENTATIVA"])


def render_card_detail(card_key, fila_filtrada, motoristas_df, retornos_df):
    title = ""
    subtitle = ""
    df = pd.DataFrame()

    if card_key == "awbs":
        title = "Detalhe — AWBs monitoradas"
        subtitle = "Linhas detalhadas disponíveis na base gerencial sincronizada."
        df = fila_filtrada.copy()

    elif card_key == "atraso":
        title = "Detalhe — Entrega em atraso"
        subtitle = "Cargas com atraso/SLA vencido identificadas na fila gerencial."
        df = overdue_delivery_rows(fila_filtrada)

    elif card_key == "sla_sem_rota":
        title = "Detalhe — SLA do dia sem rota"
        subtitle = "Cargas com SLA no dia analisado e sem rota criada no Eu Entrego."
        df = sla_sem_rota_rows(fila_filtrada)

    elif card_key == "terceira":
        title = "Detalhe — 3ª tentativa de entrega"
        subtitle = "Cargas com 3 ou mais tentativas de entrega registradas."
        df = terceira_tentativa_rows(fila_filtrada)

    elif card_key == "retornos":
        title = "Detalhe — Retornos em aberto"
        subtitle = "Retornos/insucessos com 1 dia ou mais ainda em aberto."
        df = retornos_df.copy()

    elif card_key == "motoristas":
        title = "Detalhe — Motoristas ofensores"
        subtitle = "Ranking de motoristas/entregadores por insucessos e retornos."
        df = motoristas_df.copy()

    else:
        return

    detail_df = detail_columns(df)

    st.markdown(
        f"""
        <div class="detail-box">
            <div class="detail-title">{title}</div>
            <div class="detail-sub">{subtitle}</div>
            <span class="detail-count">{len(detail_df)} registro(s) encontrado(s)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns([1, 5])
    with col_a:
        if st.button("Fechar detalhe", use_container_width=True):
            st.session_state["detail_card"] = ""
            st.rerun()

    render_table(detail_df.head(500), height=430)


def driver_offenders(df):
    if df is None or df.empty:
        return pd.DataFrame()

    driver_col = first_col(df, ["MOTORISTA / ENTREGADOR", "ULTIMO_ENTREGADOR", "ENTREGADOR", "MOTORISTA"])
    if not driver_col:
        return pd.DataFrame()

    blob = as_text_blob(df)
    insucesso_mask = blob.str.contains("INSUCESSO", na=False)
    retorno_mask = blob.str.contains("RETORNO|DEVOLVIDO", regex=True, na=False)
    base = df[insucesso_mask | retorno_mask].copy()

    if base.empty:
        return pd.DataFrame()

    base["_MOTORISTA"] = base[driver_col].fillna("").astype(str).str.strip()
    base["_MOTORISTA"] = base["_MOTORISTA"].replace({"": "SEM MOTORISTA INFORMADO"})

    base["_INSUCESSO"] = as_text_blob(base).str.contains("INSUCESSO", na=False).astype(int)
    base["_RETORNO"] = as_text_blob(base).str.contains("RETORNO|DEVOLVIDO", regex=True, na=False).astype(int)

    awb_col = first_col(base, ["AWB"])
    if awb_col:
        grouped = (
            base.groupby("_MOTORISTA", dropna=False)
            .agg(
                AWBS=(awb_col, "nunique"),
                INSUCESSOS=("_INSUCESSO", "sum"),
                RETORNOS=("_RETORNO", "sum"),
            )
            .reset_index()
        )
    else:
        grouped = (
            base.groupby("_MOTORISTA", dropna=False)
            .agg(
                AWBS=("_MOTORISTA", "size"),
                INSUCESSOS=("_INSUCESSO", "sum"),
                RETORNOS=("_RETORNO", "sum"),
            )
            .reset_index()
        )

    grouped = grouped.rename(columns={"_MOTORISTA": "MOTORISTA / ENTREGADOR"})
    grouped["TOTAL OCORRÊNCIAS"] = grouped["INSUCESSOS"] + grouped["RETORNOS"]
    return grouped.sort_values(["TOTAL OCORRÊNCIAS", "AWBS"], ascending=False).head(15)


def open_returns(df):
    if df is None or df.empty:
        return pd.DataFrame()

    blob = as_text_blob(df)
    mask = blob.str.contains("RETORNO|DEVOLVIDO|INSUCESSO", regex=True, na=False)

    retorno_col = first_col(df, ["RETORNO CONFIRMADO"])
    if retorno_col:
        confirmed = df[retorno_col].astype(str).map(normalize_text).isin(["TRUE", "SIM", "1", "VERDADEIRO"])
        mask = mask & ~confirmed

    dias_col = first_col(df, ["DIAS DESDE ÚLTIMA ROTA", "DIAS EM ATRASO"])
    if dias_col:
        dias = numeric_series(df[dias_col])
        mask = mask & dias.ge(1)

    out = df[mask].copy()

    preferred = [
        "AWB",
        "CLIENTE",
        "MOTORISTA / ENTREGADOR",
        "STATUS ÚLTIMA ROTA",
        "MOTIVO ÚLTIMA ROTA",
        "ÚLTIMA ROTA",
        "DIAS DESDE ÚLTIMA ROTA",
        "PROBLEMA",
        "PRÓXIMA AÇÃO",
    ]
    cols = [c for c in preferred if c in out.columns]
    return out[cols] if cols else out


def top5_pendencia_corp(df):
    if df is None or df.empty:
        return pd.DataFrame()

    blob = as_text_blob(df)
    corp_mask = blob.str.contains("PENDENCIA CORP|PENDENCIA_CORP|PENDÊNCIA CORP", regex=True, na=False)

    base = df[corp_mask].copy()
    if base.empty:
        base = filter_terms(df, ["PENDENCIA", "PENDÊNCIA"]).copy()

    if base.empty:
        return pd.DataFrame()

    cliente_col = first_col(base, ["CLIENTE"])
    pend_col = first_col(base, ["MOTIVO PENDÊNCIA", "PROBLEMA", "SITUAÇÃO", "STATUS TORRE"])

    if not cliente_col:
        cliente_col = base.columns[0]
    if not pend_col:
        pend_col = base.columns[-1]

    awb_col = first_col(base, ["AWB"])

    if awb_col:
        grouped = (
            base.groupby([cliente_col, pend_col], dropna=False)[awb_col]
            .nunique()
            .reset_index(name="AWBS")
        )
    else:
        grouped = (
            base.groupby([cliente_col, pend_col], dropna=False)
            .size()
            .reset_index(name="AWBS")
        )

    grouped = grouped.rename(columns={cliente_col: "CLIENTE", pend_col: "PENDÊNCIA"})
    return grouped.sort_values("AWBS", ascending=False).head(5)


def simplified_director_report(resumo, kpis_df, motoristas_df, retornos_df, pendcorp_df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        resumo.to_excel(writer, sheet_name="RESUMO_BASE", index=False)
        kpis_df.to_excel(writer, sheet_name="RESUMO_DIRETORIA", index=False)
        motoristas_df.to_excel(writer, sheet_name="MOTORISTAS", index=False)
        retornos_df.to_excel(writer, sheet_name="RETORNOS_ABERTOS", index=False)
        pendcorp_df.to_excel(writer, sheet_name="TOP5_PEND_CORP", index=False)

    buffer.seek(0)
    return buffer.getvalue()


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
        ("motoristas", "☑  Motoristas ofensores"),
        ("retornos", "↩  Retornos em aberto"),
        ("pendcorp", "▣  Pendência Corp"),
        ("relatorio", "▤  Download diretoria"),
        ("config", "⚙  Configurações"),
    ]

    if "menu_gerente" not in st.session_state:
        st.session_state["menu_gerente"] = "visao"

    if "detail_card" not in st.session_state:
        st.session_state["detail_card"] = ""

    for key, label in menu_items:
        active = st.session_state["menu_gerente"] == key
        if st.button(
            label,
            key=f"menu_btn_{key}",
            use_container_width=True,
            type="primary" if active else "secondary",
        ):
            st.session_state["menu_gerente"] = key
            st.session_state["detail_card"] = ""
            st.rerun()

    st.markdown(
        """
        <div class="side-note">
            <b>Dashboard Gerencial</b><br>
            Layout claro<br>
            Menu funcional
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
        <p>Visão gerencial de SLA, retornos, motoristas ofensores e pendências corporativas.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# FILTRO DE DATA — COMPACTO NO CANTO DIREITO
# =========================================================
today = date.today()
default_start = today - timedelta(days=7)

top_info_col, top_filter_col = st.columns([4.5, 1.35])

with top_filter_col:
    st.markdown('<div class="filter-caption">Filtro de data</div>', unsafe_allow_html=True)
    date_range = st.date_input(
        "Filtro de data",
        value=(default_start, today),
        format="DD/MM/YYYY",
        label_visibility="collapsed",
    )
    st.markdown(
        '<div class="filter-note-compact">Aplica nos detalhes do relatório</div>',
        unsafe_allow_html=True,
    )

fila_filtrada, filtro_msg = apply_date_filter(fila, date_range)

with top_info_col:
    st.markdown(
        f'<div class="info">ⓘ {filtro_msg}. AWBs monitoradas representam AWBs únicas da carteira atual, não entregas concluídas.</div>',
        unsafe_allow_html=True,
    )

motoristas_df = driver_offenders(fila_filtrada)
retornos_df = open_returns(fila_filtrada)
pendcorp_df = top5_pendencia_corp(fila_filtrada)

kpis_df = pd.DataFrame(
    [
        {"INDICADOR": "AWBs monitoradas", "VALOR": number(summary_value(resumo, "AWBs monitoradas", 0))},
        {"INDICADOR": "Entrega em atraso", "VALOR": number(summary_value(resumo, "Entrega em atraso", 0))},
        {"INDICADOR": "SLA do dia sem rota", "VALOR": number(summary_value(resumo, "SLA do dia sem rota", 0))},
        {"INDICADOR": "3ª tentativa de entrega", "VALOR": number(summary_value(resumo, "3ª tentativa de entrega", 0))},
        {"INDICADOR": "Retornos em aberto 1 dia ou +", "VALOR": len(retornos_df)},
        {"INDICADOR": "Motoristas ofensores", "VALOR": len(motoristas_df)},
        {"INDICADOR": "Top Pendência Corp analisado", "VALOR": len(pendcorp_df)},
        {"INDICADOR": "Acareações em andamento", "VALOR": number(summary_value(resumo, "Acareações em andamento", 0))},
        {"INDICADOR": "Valor em acareação", "VALOR": summary_value(resumo, "Valor em acareação", 0)},
    ]
)


# =========================================================
# PÁGINAS
# =========================================================
menu = st.session_state["menu_gerente"]

if menu == "visao":
    st.markdown('<div class="section-title">Resumo gerencial</div>', unsafe_allow_html=True)

    cards = [
        ("AWBs monitoradas", fmt_int(summary_value(resumo, "AWBs monitoradas", 0)), "Carteira única acompanhada", "▣", "#2f6fed", "#edf4ff", "awbs"),
        ("Entrega em atraso", fmt_int(summary_value(resumo, "Entrega em atraso", 0)), "Cargas com SLA vencido", "◷", "#d92d20", "#fff0ef", "atraso"),
        ("SLA do dia sem rota", fmt_int(summary_value(resumo, "SLA do dia sem rota", 0)), "SLA hoje sem rota no Eu Entrego", "▦", "#d97706", "#fff7e8", "sla_sem_rota"),
        ("3ª tentativa de entrega", fmt_int(summary_value(resumo, "3ª tentativa de entrega", 0)), "Cargas com 3 ou mais tentativas", "3ª", "#c2410c", "#fff7ed", "terceira"),
        ("Retornos em aberto", fmt_int(len(retornos_df)), "Retornos com 1 dia ou mais", "↩", "#7c3aed", "#f5f3ff", "retornos"),
        ("Motoristas ofensores", fmt_int(len(motoristas_df)), "In Sucessos e retornos", "☑", "#0f766e", "#f0fdfa", "motoristas"),
    ]

    cols = st.columns(6)
    for idx, item in enumerate(cards):
        label, value, sub, icon, accent, soft, key = item
        with cols[idx]:
            kpi_card(label, value, sub, icon, accent, soft)
            button_label = "Aberto" if st.session_state.get("detail_card") == key else "Abrir"
            if st.button(button_label, key=f"abrir_{key}", use_container_width=True):
                if st.session_state.get("detail_card") == key:
                    st.session_state["detail_card"] = ""
                else:
                    st.session_state["detail_card"] = key
                st.rerun()

    detail = st.session_state.get("detail_card", "")

    if detail:
        render_card_detail(detail, fila_filtrada, motoristas_df, retornos_df)

    st.divider()
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Controle de motoristas ofensores")
        st.caption("Baseado em ocorrências de insucesso e retornos.")
        render_table(motoristas_df, height=360)

    with c2:
        st.markdown("### Retornos em aberto — 1 dia ou +")
        st.caption("Cargas com retorno/insucesso/devolvido ainda não confirmado e com 1 dia ou mais.")
        render_table(retornos_df.head(15), height=360)

    st.divider()
    st.markdown("### Top 5 ofensores — Pendência Corp")
    st.caption("Agrupamento por cliente e pendência.")
    render_table(pendcorp_df, height=260)


elif menu == "motoristas":
    st.markdown("### Controle de motoristas ofensores")
    st.caption("Ranking de entregadores/motoristas com maior concentração de insucessos e retornos.")
    render_table(motoristas_df, height=520)

    st.download_button(
        "Baixar motoristas ofensores.csv",
        motoristas_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="motoristas_ofensores.csv",
        mime="text/csv",
        use_container_width=True,
    )


elif menu == "retornos":
    st.markdown("### Retornos em aberto — 1 dia ou +")
    st.caption("Pendências com status de retorno, devolvido ou insucesso, ainda sem confirmação de retorno.")
    render_table(retornos_df, height=560)

    st.download_button(
        "Baixar retornos em aberto.csv",
        retornos_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="retornos_em_aberto.csv",
        mime="text/csv",
        use_container_width=True,
    )


elif menu == "pendcorp":
    st.markdown("### Top 5 ofensores — Pendência Corp")
    st.caption("Agrupamento por cliente e tipo/motivo da pendência.")
    render_table(pendcorp_df, height=360)

    st.divider()
    st.markdown("### Base filtrada de Pendência Corp")
    pendcorp_base = filter_terms(fila_filtrada, ["PENDENCIA CORP", "PENDÊNCIA CORP", "PENDENCIA_CORP"])
    if pendcorp_base.empty:
        pendcorp_base = filter_terms(fila_filtrada, ["PENDENCIA", "PENDÊNCIA"])
    render_table(pendcorp_base.head(500), height=520)


elif menu == "relatorio":
    st.markdown("### Download para diretoria — simplificado")
    st.caption("Arquivo resumido com os indicadores principais, motoristas ofensores, retornos em aberto e Top 5 Pendência Corp.")

    c1, c2 = st.columns(2)

    with c1:
        render_table(kpis_df, height=360)

    with c2:
        st.download_button(
            "Baixar relatório diretoria.xlsx",
            simplified_director_report(resumo, kpis_df, motoristas_df, retornos_df, pendcorp_df),
            file_name="relatorio_diretoria_torre.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.divider()
    st.markdown("### Prévia do conteúdo")
    t1, t2, t3 = st.tabs(["Motoristas", "Retornos", "Pendência Corp"])
    with t1:
        render_table(motoristas_df, height=360)
    with t2:
        render_table(retornos_df, height=360)
    with t3:
        render_table(pendcorp_df, height=260)


elif menu == "config":
    st.markdown("### Configurações")
    st.success("Dashboard carregado com sucesso.")
    st.write("Fonte configurada:", SOURCE_URL)

    status_df = pd.DataFrame(
        [
            {"Aba": "RESUMO", "Linhas": len(resumo)},
            {"Aba": "FILA", "Linhas": len(fila)},
            {"Filtro aplicado": filtro_msg, "Linhas após filtro": len(fila_filtrada)},
        ]
    )
    render_table(status_df, height=220)

    st.info("Secrets necessários: MANAGER_SOURCE_URL e [gcp_service_account].")
