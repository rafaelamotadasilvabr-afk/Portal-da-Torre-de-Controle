import io
import re
import unicodedata
from datetime import date, timedelta

import pandas as pd
import altair as alt
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


st.set_page_config(
    page_title="Dashboard Torre de Controle",
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

    .chart-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px 18px;
        box-shadow: 0 8px 22px rgba(15,23,42,.045);
        margin-top: 16px;
        margin-bottom: 12px;
    }

    .chart-title {
        color: #10213d;
        font-size: 1.04rem;
        font-weight: 900;
        margin-bottom: 3px;
    }

    .chart-sub {
        color: #64748b;
        font-size: .78rem;
        margin-bottom: 10px;
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

    for sheet_name in ["RESUMO", "FILA", "TOP_PROBLEMAS", "TOP_BASES", "EDI_RESUMO", "EDI_DETALHE", "PENDENCIA_MOVIMENTOS"]:
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


def service_level_value(resumo):
    total = number(summary_value(resumo, "AWBs monitoradas", 0))
    atraso = number(summary_value(resumo, "Entrega em atraso", 0))

    if total <= 0:
        return 0.0

    nivel = ((total - atraso) / total) * 100
    return max(0.0, min(100.0, nivel))


def service_level_label(resumo):
    return f"{service_level_value(resumo):.1f}%".replace(".", ",")


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


def excel_bytes(df, sheet_name="DADOS"):
    output = io.BytesIO()
    safe_df = df.copy() if df is not None else pd.DataFrame()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        safe_df.to_excel(writer, sheet_name=str(sheet_name)[:31], index=False)
    output.seek(0)
    return output.getvalue()


def safe_filename(name):
    text = normalize_text(name).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "dados"


def render_alert_pie_chart(alert_df):
    st.markdown(
        """
        <div class="chart-card">
            <div class="chart-title">Distribuição dos alertas gerenciais</div>
            <div class="chart-sub">Composição dos principais alertas do período filtrado.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if alert_df is None or alert_df.empty or alert_df["QTDE"].sum() <= 0:
        st.info("Sem volume suficiente para montar o gráfico de pizza no período selecionado.")
        return

    pie = (
        alt.Chart(alert_df)
        .mark_arc(innerRadius=58, outerRadius=118)
        .encode(
            theta=alt.Theta(field="QTDE", type="quantitative"),
            color=alt.Color(
                field="INDICADOR",
                type="nominal",
                title="Indicador",
                legend=alt.Legend(orient="right"),
            ),
            tooltip=[
                alt.Tooltip("INDICADOR:N", title="Indicador"),
                alt.Tooltip("QTDE:Q", title="Quantidade", format=",.0f"),
            ],
        )
        .properties(height=315)
    )

    labels = (
        alt.Chart(alert_df)
        .mark_text(radius=145, size=12, fontWeight="bold")
        .encode(
            theta=alt.Theta(field="QTDE", type="quantitative"),
            text=alt.Text("PERCENTUAL:N"),
            color=alt.value("#334155"),
        )
    )

    st.altair_chart(pie + labels, use_container_width=True)


def edi_count(df, indicador=None, base=None, cliente=None):
    if df is None or df.empty:
        return 0

    data = edi_rows(df, indicador=indicador, base=base, cliente=cliente)

    if data.empty:
        return 0

    if "AWB" in data.columns:
        awbs = data["AWB"].fillna("").astype(str).str.strip()
        awbs = awbs[awbs.ne("")]
        return int(awbs.nunique()) if not awbs.empty else int(len(data))

    return int(len(data))


def edi_rows(df, indicador=None, base=None, cliente=None):
    if df is None or df.empty:
        return pd.DataFrame()

    data = df.copy()

    if indicador and "INDICADOR" in data.columns:
        data = data[data["INDICADOR"].astype(str).eq(indicador)]

    if base and "BASE" in data.columns:
        data = data[data["BASE"].astype(str).str.upper().eq(str(base).upper())]

    if cliente and "CLIENTE" in data.columns:
        cliente_norm = normalize_text(cliente)
        data = data[
            data["CLIENTE"].astype(str).map(normalize_text).str.contains(cliente_norm, na=False)
        ]

    preferred = [
        "BASE",
        "INDICADOR",
        "CLIENTE",
        "AWB",
        "STATUS",
        "STATUS_EN",
        "BAG_CREATE",
        "JA_ENTREGUE",
        "SLA",
        "STATUS_SLA",
        "DIAS_SLA",
        "ORIGEM",
        "DESTINO",
        "OPS_STATION",
        "TRECHO",
        "VOO",
        "DATA_VOO",
        "BILL_TO",
        "FONTE",
    ]
    cols = [c for c in preferred if c in data.columns]
    return data[cols].copy() if cols else data


def render_edi_card_detail(card_key, edi_detalhe):
    mapping = {
        "edi_emb_sao12": {
            "title": "EDI — Embarque em SAO12/TRES1 SAO12",
            "subtitle": "Clientes SAO12 monitorados. Regra: pendente de embarque com SLA vencido ou SLA do dia.",
            "df": edi_rows(edi_detalhe, "PENDENTE DE EMBARQUE", "SAO12"),
            "sheet": "EMB_SAO12",
        },
        "edi_emb_tres1": {
            "title": "EDI — Embarque em SAO12/TRES1 TRES1",
            "subtitle": "Cliente TRES1: Três Corações. Para Bag Create, valida se a AWB já foi entregue antes de classificar como pendente. Regra: pendente de embarque com SLA vencido ou SLA do dia.",
            "df": edi_rows(edi_detalhe, "PENDENTE DE EMBARQUE", "TRES1"),
            "sheet": "EMB_TRES1",
        },
        "edi_des_sao12": {
            "title": "EDI — Pendente de desembarque SAO12",
            "subtitle": "Cargas onde OPSStation bate com FltDestination ou status pendente desembarque, até o SLA do dia.",
            "df": edi_rows(edi_detalhe, "PENDENTE DE DESEMBARQUE", "SAO12"),
            "sheet": "DES_SAO12",
        },
        "edi_des_tres1": {
            "title": "EDI — Pendente de desembarque TRES1",
            "subtitle": "Cargas onde OPSStation bate com FltDestination ou status pendente desembarque, até o SLA do dia.",
            "df": edi_rows(edi_detalhe, "PENDENTE DE DESEMBARQUE", "TRES1"),
            "sheet": "DES_TRES1",
        },
        "edi_entrega_sla": {
            "title": "EDI — Entrega destino / SLA",
            "subtitle": "Pendentes no destino com SLA vencido ou SLA do dia.",
            "df": edi_rows(edi_detalhe, "ENTREGA NO DESTINO PELO SLA"),
            "sheet": "ENTREGA_SLA",
        },
        "edi_missing": {
            "title": "EDI — Missing",
            "subtitle": "Cargas classificadas como missing no First Mile.",
            "df": edi_rows(edi_detalhe, "MISSING"),
            "sheet": "MISSING",
        },
        "edi_discrepancia": {
            "title": "EDI — Discrepância",
            "subtitle": "Divergências classificadas no First Mile.",
            "df": edi_rows(edi_detalhe, "DISCREPÂNCIA"),
            "sheet": "DISCREPANCIA",
        },
        "edi_resumo": {
            "title": "EDI — Resumo",
            "subtitle": "Resumo consolidado por base e indicador.",
            "df": edi_resumo if "edi_resumo" in globals() else pd.DataFrame(),
            "sheet": "RESUMO_EDI",
        },
    }

    item = mapping.get(card_key)
    if not item:
        return

    df = item["df"].copy()

    st.markdown(
        f"""
        <div class="detail-box">
            <div class="detail-title">{item["title"]}</div>
            <div class="detail-sub">{item["subtitle"]}</div>
            <span class="detail-count">{len(df)} registro(s) encontrado(s)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns([1, 5])
    with col_a:
        if st.button("Fechar detalhe", key="fechar_edi_detail", use_container_width=True):
            st.session_state["edi_detail_card"] = ""
            st.rerun()

    render_table(df, height=500)
    st.download_button(
        "Baixar Excel deste card",
        excel_bytes(df, sheet_name=item["sheet"]),
        file_name=f"{safe_filename(item['title'])}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


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
        "ACAREACAO ENTREGADOR",
        "ACAREACAO VALOR",
        "ACAREACAO STATUS",
        "ACAREACAO TIPO",
        "ACAREACAO OBSERVACAO",
    ]
    cols = [c for c in preferred if c in df.columns]
    return df[cols].copy() if cols else df.copy()


def overdue_delivery_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    problema_col = first_col(df, ["PROBLEMA"])
    if problema_col:
        problema = df[problema_col].astype(str).map(normalize_text)
        exact = df[problema.eq("ENTREGA EM ATRASO")].copy()
        if not exact.empty:
            return exact

    return filter_terms(df, ["ENTREGA EM ATRASO"])


def sla_sem_rota_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    problema_col = first_col(df, ["PROBLEMA"])
    if problema_col:
        problema = df[problema_col].astype(str).map(normalize_text)
        exact = df[problema.eq("SLA DO DIA SEM ROTA")].copy()
        if not exact.empty:
            return exact

    return filter_terms(df, ["SLA DO DIA SEM ROTA", "SLA SEM ROTA"])


def last_mile_desembarque_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    problema_col = first_col(df, ["PROBLEMA"])
    if problema_col:
        problema = df[problema_col].astype(str).map(normalize_text)
        exact = df[problema.eq("PENDENTE DE DESEMBARQUE")].copy()
        if not exact.empty:
            return exact

    return filter_terms(df, ["PENDENTE DE DESEMBARQUE", "PENDENTE DESEMBARQUE"])


def pendencia_movimento_rows(tipo):
    df = pendencia_movimentos if "pendencia_movimentos" in globals() else pd.DataFrame()

    if df is None or df.empty or "TIPO_MOVIMENTO" not in df.columns:
        return pd.DataFrame()

    mask = df["TIPO_MOVIMENTO"].astype(str).map(normalize_text).eq(normalize_text(tipo))
    out = df[mask].copy()

    preferred = [
        "TIPO_MOVIMENTO",
        "AWB",
        "DATA_EVENTO_TORRE",
        "EVENTO_TORRE",
        "STATUS_TRATATIVA",
        "ORIGEM_TORRE",
        "MOTIVO_PENDENCIA",
        "ABA_ORIGEM",
    ]
    cols = [c for c in preferred if c in out.columns]
    return out[cols].copy() if cols else out


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


def awb_col_name(df):
    return first_col(df, ["AWB"])


def date_basis_col(df):
    if df is None or df.empty:
        return None
    for col_name in ["DATA ANÁLISE", "SLA", "ÚLTIMA ROTA", "DATA EVENTO TORRE", "ÚLTIMA ALTERAÇÃO"]:
        col = first_col(df, [col_name])
        if col:
            dates = parse_date_col(df[col])
            if dates.notna().any():
                return col
    return None


def daily_awb_counts(df):
    if df is None or df.empty:
        return pd.DataFrame()

    dcol = date_basis_col(df)
    if not dcol:
        return pd.DataFrame()

    dates = parse_date_col(df[dcol])
    base = df[dates.notna()].copy()
    base["_DATA_BASE"] = dates[dates.notna()].dt.date.astype(str)

    acol = awb_col_name(base)
    if acol:
        out = base.groupby("_DATA_BASE")[acol].nunique().reset_index(name="AWBS")
    else:
        out = base.groupby("_DATA_BASE").size().reset_index(name="AWBS")

    return out.rename(columns={"_DATA_BASE": "DATA"}).sort_values("DATA")


def acareacao_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    blob = as_text_blob(df)
    mask = blob.str.contains("ACAREACAO|ACAREAÇÃO|RESSALVA", regex=True, na=False)

    status_col = first_col(df, ["ACAREACAO STATUS", "STATUS TORRE", "STATUS"])
    if status_col:
        status = df[status_col].astype(str).map(normalize_text)
        # Se existir status, prioriza aberto/em andamento, mas não esconde se a base só tiver texto geral.
        aberto = status.str.contains("EM ANDAMENTO|ABERTO|PENDENTE", regex=True, na=False)
        if aberto.any():
            mask = mask & aberto

    out = df[mask].copy()

    preferred = [
        "AWB",
        "CLIENTE",
        "ACAREACAO ENTREGADOR",
        "MOTORISTA / ENTREGADOR",
        "ACAREACAO VALOR",
        "ACAREACAO STATUS",
        "ACAREACAO TIPO",
        "ACAREACAO OBSERVACAO",
        "PROBLEMA",
        "PRÓXIMA AÇÃO",
    ]
    cols = [c for c in preferred if c in out.columns]
    return out[cols].copy() if cols else out


def acareacao_driver_summary(df):
    rows = acareacao_rows(df)
    if rows.empty:
        return pd.DataFrame()

    ent_col = first_col(rows, ["ACAREACAO ENTREGADOR", "MOTORISTA / ENTREGADOR"])
    val_col = first_col(rows, ["ACAREACAO VALOR"])
    awb_col = first_col(rows, ["AWB"])

    if not ent_col:
        rows["ENTREGADOR RESPONSÁVEL"] = "SEM ENTREGADOR INFORMADO"
        ent_col = "ENTREGADOR RESPONSÁVEL"

    rows[ent_col] = rows[ent_col].fillna("").astype(str).str.strip()
    rows[ent_col] = rows[ent_col].replace({"": "SEM ENTREGADOR INFORMADO", "nan": "SEM ENTREGADOR INFORMADO"})

    if val_col:
        rows["_VALOR_NUM"] = numeric_series(rows[val_col])
    else:
        rows["_VALOR_NUM"] = 0

    if awb_col:
        grouped = rows.groupby(ent_col, dropna=False).agg(
            AWBS=(awb_col, "nunique"),
            VALOR_TOTAL=("_VALOR_NUM", "sum"),
        ).reset_index()
    else:
        grouped = rows.groupby(ent_col, dropna=False).agg(
            AWBS=(ent_col, "size"),
            VALOR_TOTAL=("_VALOR_NUM", "sum"),
        ).reset_index()

    grouped = grouped.rename(columns={ent_col: "ENTREGADOR RESPONSÁVEL"})
    grouped["VALOR_TOTAL"] = grouped["VALOR_TOTAL"].map(lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    return grouped.sort_values("AWBS", ascending=False)


def render_card_detail(card_key, fila_filtrada, motoristas_df, retornos_df, acareacao_df, daily_df):
    title = ""
    subtitle = ""
    df = pd.DataFrame()

    if card_key == "nivel_servico":
        title = "Detalhe — Nível de serviço"
        subtitle = "Indicador gerencial estimado: AWBs monitoradas menos entregas em atraso, dividido por AWBs monitoradas. Não representa baixa final de entrega."
        df = kpis_df.copy() if "kpis_df" in globals() else pd.DataFrame()

    elif card_key == "awbs_dia":
        title = "Detalhe — Quantidade de AWB por dia"
        subtitle = "Contagem de AWBs por dia dentro do período selecionado no filtro."
        df = daily_df.copy()

    elif card_key == "awbs":
        title = "Detalhe — AWBs do período"
        subtitle = "Linhas detalhadas disponíveis na base gerencial filtrada."
        df = fila_filtrada.copy()

    elif card_key == "atraso":
        title = "Detalhe — Entrega em atraso"
        subtitle = "Cargas com atraso/SLA vencido identificadas na fila gerencial."
        df = overdue_delivery_rows(fila_filtrada)

    elif card_key == "sla_sem_rota":
        title = "Detalhe — SLA do dia sem rota"
        subtitle = "Cargas com SLA no dia analisado e sem rota criada no Eu Entrego."
        df = sla_sem_rota_rows(fila_filtrada)

    elif card_key == "lastmile_desembarque":
        title = "Detalhe — Pendente de desembarque CDSP2"
        subtitle = "Cargas CDSP2 em pendência de desembarque com SLA vencido ou SLA do dia."
        df = last_mile_desembarque_rows(fila_filtrada)

    elif card_key == "terceira":
        title = "Detalhe — 3ª tentativa de entrega"
        subtitle = "Cargas com 3 ou mais tentativas de entrega registradas."
        df = terceira_tentativa_rows(fila_filtrada)

    elif card_key == "pend_total":
        title = "Detalhe — Total na pendência"
        subtitle = "Cargas que compõem o backlog atual da Torre."
        df = pendencia_movimento_rows("TOTAL NA PENDÊNCIA")

    elif card_key == "pend_entrada_hoje":
        title = "Detalhe — Entradas na Torre hoje"
        subtitle = "Cargas que entraram na Torre na data de análise."
        df = pendencia_movimento_rows("ENTROU HOJE")

    elif card_key == "pend_saida_hoje":
        title = "Detalhe — Saíram da pendência hoje"
        subtitle = "Cargas finalizadas/encerradas na data de análise."
        df = pendencia_movimento_rows("SAIU HOJE")

    elif card_key == "retornos":
        title = "Detalhe — Retornos em aberto"
        subtitle = "Retornos/insucessos com 1 dia ou mais ainda em aberto."
        df = retornos_df.copy()

    elif card_key == "motoristas":
        title = "Detalhe — Motoristas ofensores"
        subtitle = "Ranking de motoristas/entregadores por insucessos e retornos."
        df = motoristas_df.copy()

    elif card_key == "top_pendencia":
        title = "Detalhe — Top 5 clientes com pendência"
        subtitle = "Ranking por cliente e pendência. Prioriza Pendência Corp quando houver marcação; caso contrário usa a fila de pendências."
        df = top5_pendencia_corp(fila_filtrada)

    elif card_key == "acareacao":
        title = "Detalhe — Acareações em aberto"
        subtitle = "Quantidade, valor e entregador responsável pelas acareações/ressalvas em aberto."
        df = acareacao_df.copy()

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

    if card_key == "awbs_dia" and not detail_df.empty:
        chart = detail_df.copy()
        if "DATA" in chart.columns and "AWBS" in chart.columns:
            st.bar_chart(chart.set_index("DATA")["AWBS"])
        render_table(detail_df, height=330)
        st.download_button(
            "Baixar Excel deste card",
            excel_bytes(detail_df, sheet_name="AWBS_POR_DIA"),
            file_name="card_awbs_por_dia.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        return

    if card_key == "acareacao":
        st.markdown("#### Entregadores responsáveis")
        resumo_ent = acareacao_driver_summary(fila_filtrada)
        render_table(resumo_ent, height=260)
        st.markdown("#### Detalhe por AWB")
        render_table(detail_df.head(500), height=360)
        st.download_button(
            "Baixar Excel deste card",
            excel_bytes(detail_df, sheet_name="ACAREACOES"),
            file_name="card_acareacoes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        return

    render_table(detail_df.head(500), height=430)
    st.download_button(
        "Baixar Excel deste card",
        excel_bytes(detail_df, sheet_name="DETALHE_CARD"),
        file_name=f"card_{safe_filename(title)}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )



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
    """
    Top 5 clientes com pendência.

    Regra:
    1. Tenta priorizar Pendência Corp quando houver marcação na base.
    2. Se não houver marcação explícita, usa a fila filtrada inteira.
    3. Agrupa por Cliente + Pendência/Problema.
    4. Nunca deixa vazio se existir Cliente ou Problema na fila.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    base = df.copy()
    blob = as_text_blob(base)

    # Prioriza Pendência Corp se existir na base.
    corp_mask = blob.str.contains("PENDENCIA CORP|PENDENCIA_CORP|PENDÊNCIA CORP", regex=True, na=False)
    if corp_mask.any():
        base = base[corp_mask].copy()

    cliente_col = first_col(base, ["CLIENTE", "CLIENTE PADRONIZADO", "CLIENTE_PADRONIZADO"])
    pend_col = first_col(base, ["MOTIVO PENDÊNCIA", "PROBLEMA", "SITUAÇÃO", "STATUS TORRE", "STATUS ÚLTIMA ROTA"])

    if not cliente_col and not pend_col:
        return pd.DataFrame()

    if not cliente_col:
        base["CLIENTE"] = "CLIENTE NÃO INFORMADO"
        cliente_col = "CLIENTE"

    if not pend_col:
        base["PENDÊNCIA"] = "PENDÊNCIA NÃO INFORMADA"
        pend_col = "PENDÊNCIA"

    base[cliente_col] = base[cliente_col].fillna("").astype(str).str.strip()
    base[pend_col] = base[pend_col].fillna("").astype(str).str.strip()

    base[cliente_col] = base[cliente_col].replace({"": "CLIENTE NÃO INFORMADO", "nan": "CLIENTE NÃO INFORMADO"})
    base[pend_col] = base[pend_col].replace({"": "PENDÊNCIA NÃO INFORMADA", "nan": "PENDÊNCIA NÃO INFORMADA"})

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
    grouped["% DO TOTAL"] = (
        grouped["AWBS"] / grouped["AWBS"].sum() * 100
    ).round(1).astype(str).str.replace(".", ",", regex=False) + "%"

    return grouped.sort_values("AWBS", ascending=False).head(5)


def simplified_director_report(resumo, kpis_df, motoristas_df, retornos_df, pendcorp_df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        resumo.to_excel(writer, sheet_name="RESUMO_BASE", index=False)
        kpis_df.to_excel(writer, sheet_name="RESUMO_DIRETORIA", index=False)
        motoristas_df.to_excel(writer, sheet_name="MOTORISTAS", index=False)
        retornos_df.to_excel(writer, sheet_name="RETORNOS_ABERTOS", index=False)
        pendcorp_df.to_excel(writer, sheet_name="TOP5_PEND_CORP", index=False)
        # Quando disponíveis no escopo, adiciona abas gerenciais novas.
        if "acareacao_df" in globals():
            acareacao_df.to_excel(writer, sheet_name="ACAREACOES", index=False)
        if "daily_df" in globals():
            daily_df.to_excel(writer, sheet_name="AWBS_POR_DIA", index=False)
        if "alert_distribution_df" in globals():
            alert_distribution_df.to_excel(writer, sheet_name="DISTR_ALERTAS", index=False)

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
        ("edi", "✈  EDI"),
        ("acareacao", "⚖  Acareações"),
        ("pendcorp", "▣  Top clientes pendência"),
        ("relatorio", "▤  Download diretoria"),
        ("config", "⚙  Configurações"),
    ]

    if "menu_gerente" not in st.session_state:
        st.session_state["menu_gerente"] = "visao"

    if "detail_card" not in st.session_state:
        st.session_state["detail_card"] = ""

    if "edi_detail_card" not in st.session_state:
        st.session_state["edi_detail_card"] = ""

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
            st.session_state["edi_detail_card"] = ""
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
edi_resumo = pack.get("EDI_RESUMO", pd.DataFrame())
edi_detalhe = pack.get("EDI_DETALHE", pd.DataFrame())
pendencia_movimentos = pack.get("PENDENCIA_MOVIMENTOS", pd.DataFrame())

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
        <h1>Dashboard Torre de Controle</h1>
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
        f'<div class="info">ⓘ Cards críticos usam o RESUMO sincronizado pelo operacional. O filtro de data atua nos detalhes abertos, rankings e tabelas. {filtro_msg}.</div>',
        unsafe_allow_html=True,
    )

motoristas_df = driver_offenders(fila_filtrada)
retornos_df = open_returns(fila_filtrada)
pendcorp_df = top5_pendencia_corp(fila_filtrada)
acareacao_df = acareacao_rows(fila_filtrada)
daily_df = daily_awb_counts(fila_filtrada)

resumo_entrega_atraso = number(summary_value(resumo, "Entrega em atraso", len(overdue_delivery_rows(fila_filtrada))))
resumo_sla_sem_rota = number(summary_value(resumo, "SLA do dia sem rota", len(sla_sem_rota_rows(fila_filtrada))))
resumo_lm_desembarque = number(summary_value(resumo, "CDSP2 pendente desembarque", len(last_mile_desembarque_rows(fila_filtrada))))
resumo_terceira_tentativa = number(summary_value(resumo, "3ª tentativa de entrega", len(terceira_tentativa_rows(fila_filtrada))))
resumo_acareacao_qtd = number(summary_value(resumo, "Acareações em andamento", len(acareacao_df)))
resumo_total_pendencia = number(summary_value(resumo, "Total na pendência", summary_value(resumo, "Backlog da Torre", len(pendencia_movimento_rows("TOTAL NA PENDÊNCIA")))))
resumo_entraram_pendencia_hoje = number(
    summary_value(
        resumo,
        "Entradas na Torre hoje",
        summary_value(
            resumo,
            "Entraram na pendência hoje",
            len(pendencia_movimento_rows("ENTROU HOJE")),
        ),
    )
)
resumo_sairam_pendencia_hoje = number(summary_value(resumo, "Saíram da pendência hoje", len(pendencia_movimento_rows("SAIU HOJE"))))

alert_distribution_df = pd.DataFrame(
    [
        {"INDICADOR": "Entrega em atraso", "QTDE": resumo_entrega_atraso},
        {"INDICADOR": "SLA do dia sem rota", "QTDE": resumo_sla_sem_rota},
        {"INDICADOR": "Pendente desembarque CDSP2", "QTDE": resumo_lm_desembarque},
        {"INDICADOR": "3ª tentativa", "QTDE": resumo_terceira_tentativa},
        {"INDICADOR": "Retornos em aberto", "QTDE": len(retornos_df)},
        {"INDICADOR": "Acareações em aberto", "QTDE": resumo_acareacao_qtd},
    ]
)
alert_distribution_df = alert_distribution_df[alert_distribution_df["QTDE"] > 0].copy()
if not alert_distribution_df.empty:
    _total_alertas = alert_distribution_df["QTDE"].sum()
    alert_distribution_df["PERCENTUAL"] = (
        alert_distribution_df["QTDE"] / _total_alertas * 100
    ).round(1).astype(str).str.replace(".", ",", regex=False) + "%"

awb_periodo_qtd = 0
if not fila_filtrada.empty:
    _awb_col_periodo = first_col(fila_filtrada, ["AWB"])
    awb_periodo_qtd = int(fila_filtrada[_awb_col_periodo].nunique()) if _awb_col_periodo else int(len(fila_filtrada))

kpis_df = pd.DataFrame(
    [
        {"INDICADOR": "AWBs monitoradas", "VALOR": number(summary_value(resumo, "AWBs monitoradas", 0))},
        {"INDICADOR": "Entrega em atraso", "VALOR": resumo_entrega_atraso},
        {"INDICADOR": "SLA do dia sem rota", "VALOR": resumo_sla_sem_rota},
        {"INDICADOR": "CDSP2 pendente desembarque", "VALOR": resumo_lm_desembarque},
        {"INDICADOR": "3ª tentativa de entrega", "VALOR": resumo_terceira_tentativa},
        {"INDICADOR": "Retornos em aberto 1 dia ou +", "VALOR": len(retornos_df)},
        {"INDICADOR": "Motoristas ofensores", "VALOR": len(motoristas_df)},
        {"INDICADOR": "Top clientes com pendência", "VALOR": len(pendcorp_df)},
        {"INDICADOR": "Total na pendência", "VALOR": resumo_total_pendencia},
        {"INDICADOR": "Entradas na Torre hoje", "VALOR": resumo_entraram_pendencia_hoje},
        {"INDICADOR": "Saíram da pendência hoje", "VALOR": resumo_sairam_pendencia_hoje},
        {"INDICADOR": "Acareações em aberto", "VALOR": resumo_acareacao_qtd},
        {"INDICADOR": "Valor em acareação", "VALOR": summary_value(resumo, "Valor em acareação", 0)},
    ]
)


# =========================================================
# PÁGINAS
# =========================================================
menu = st.session_state["menu_gerente"]

if menu == "visao":
    st.markdown('<div class="section-title">Resumo gerencial</div>', unsafe_allow_html=True)

    st.caption(
        "Clique em Abrir para ver somente o detalhe do indicador selecionado. O filtro de data atualiza os cards calculados pela fila."
    )

    if st.button("Abrir EDI / First Mile", key="abrir_edi_home", use_container_width=False):
        st.session_state["menu_gerente"] = "edi"
        st.session_state["detail_card"] = ""
        st.rerun()

    acareacao_qtd = resumo_acareacao_qtd
    acareacao_valor = brl(summary_value(resumo, "Valor em acareação", 0))

    cards_linha1 = [
        ("Entrega em atraso", fmt_int(resumo_entrega_atraso), "Mesmo número do relatório gerencial", "◷", "#d92d20", "#fff0ef", "atraso"),
        ("SLA do dia sem rota", fmt_int(resumo_sla_sem_rota), "Mesmo critério do Radar Last Mile", "▦", "#d97706", "#fff7e8", "sla_sem_rota"),
        ("Pendente desembarque CDSP2", fmt_int(resumo_lm_desembarque), "Até SLA do dia", "⇣", "#0f766e", "#f0fdfa", "lastmile_desembarque"),
        ("3ª tentativa de entrega", fmt_int(resumo_terceira_tentativa), "Resumo operacional sincronizado", "3ª", "#c2410c", "#fff7ed", "terceira"),
    ]

    cards_linha2 = [
        ("Total na pendência", fmt_int(resumo_total_pendencia), "Backlog atual da Torre", "Σ", "#334155", "#f8fafc", "pend_total"),
        ("Entraram hoje", fmt_int(resumo_entraram_pendencia_hoje), "Entradas na Torre hoje", "+", "#2563eb", "#eff6ff", "pend_entrada_hoje"),
        ("Saíram hoje", fmt_int(resumo_sairam_pendencia_hoje), "Saíram da pendência no dia", "✓", "#0f766e", "#f0fdfa", "pend_saida_hoje"),
        ("Retornos em aberto", fmt_int(len(retornos_df)), "Retornos com 1 dia ou mais", "↩", "#7c3aed", "#f5f3ff", "retornos"),
    ]

    cards_linha3 = [
        ("Motoristas ofensores", fmt_int(len(motoristas_df)), "Insucessos e retornos", "☑", "#0f766e", "#f0fdfa", "motoristas"),
        ("Acareações em aberto", fmt_int(acareacao_qtd), f"Valor em aberto: {acareacao_valor}", "⚖", "#9333ea", "#faf5ff", "acareacao"),
        ("Top clientes pendência", fmt_int(len(pendcorp_df)), "Top 5 por cliente e pendência", "▣", "#2563eb", "#eff6ff", "top_pendencia"),
    ]

    for cards in [cards_linha1, cards_linha2, cards_linha3]:
        cols = st.columns(len(cards))
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

    render_alert_pie_chart(alert_distribution_df)

    if detail:
        render_card_detail(detail, fila_filtrada, motoristas_df, retornos_df, acareacao_df, daily_df)


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


elif menu == "edi":
    st.markdown("### EDI — First Mile")
    st.caption(
        "Cards expansivos. Regra: embarque só entra se OPSStation for SAO12/TRES1; Bag Create é validado contra entrega; desembarque entra quando OPSStation bate com FltDestination. Clique em Abrir para ver o detalhe e baixar Excel."
    )

    st.info(
        "SAO12: Riachuelo, Della Via, Stone, Tania Bulhões, Inbrands, ATS e Neodent. "
        "TRES1: Três Corações."
    )

    edi_cards_l1 = [
        ("Emb. SAO12", fmt_int(edi_count(edi_detalhe, "PENDENTE DE EMBARQUE", "SAO12")), "Até SLA do dia", "S12", "#2563eb", "#eff6ff", "edi_emb_sao12"),
        ("Emb. TRES1", fmt_int(edi_count(edi_detalhe, "PENDENTE DE EMBARQUE", "TRES1")), "Até SLA do dia", "T1", "#1d4ed8", "#eff6ff", "edi_emb_tres1"),
        ("Desemb. SAO12", fmt_int(edi_count(edi_detalhe, "PENDENTE DE DESEMBARQUE", "SAO12")), "Até SLA do dia", "⇣", "#0f766e", "#f0fdfa", "edi_des_sao12"),
        ("Desemb. TRES1", fmt_int(edi_count(edi_detalhe, "PENDENTE DE DESEMBARQUE", "TRES1")), "Até SLA do dia", "⇣", "#0f766e", "#f0fdfa", "edi_des_tres1"),
    ]

    edi_cards_l2 = [
        ("Entrega destino / SLA", fmt_int(edi_count(edi_detalhe, "ENTREGA NO DESTINO PELO SLA")), "SLA vencido ou SLA do dia", "SLA", "#d97706", "#fff7e8", "edi_entrega_sla"),
        ("Missing", fmt_int(edi_count(edi_detalhe, "MISSING")), "Cargas missing", "!", "#d92d20", "#fff0ef", "edi_missing"),
        ("Discrepância", fmt_int(edi_count(edi_detalhe, "DISCREPÂNCIA")), "Divergências First Mile", "≠", "#7c3aed", "#f5f3ff", "edi_discrepancia"),
        ("Resumo EDI", fmt_int(len(edi_resumo)), "Resumo por base/indicador", "Σ", "#334155", "#f8fafc", "edi_resumo"),
    ]

    for cards in [edi_cards_l1, edi_cards_l2]:
        cols = st.columns(len(cards))
        for idx, item in enumerate(cards):
            label, value, sub, icon, accent, soft, key = item
            with cols[idx]:
                kpi_card(label, value, sub, icon, accent, soft)
                button_label = "Aberto" if st.session_state.get("edi_detail_card") == key else "Abrir"
                if st.button(button_label, key=f"abrir_{key}", use_container_width=True):
                    if st.session_state.get("edi_detail_card") == key:
                        st.session_state["edi_detail_card"] = ""
                    else:
                        st.session_state["edi_detail_card"] = key
                    st.rerun()

    detail = st.session_state.get("edi_detail_card", "")
    if detail:
        render_edi_card_detail(detail, edi_detalhe)


elif menu == "acareacao":
    st.markdown("### Acareações em aberto")
    st.caption("Quantidade, valor e entregador responsável.")

    c1, c2 = st.columns(2)
    with c1:
        kpi_card(
            "ACAREAÇÕES EM ABERTO",
            fmt_int(number(summary_value(resumo, "Acareações em andamento", len(acareacao_df)))),
            "Quantidade de tratativas em aberto",
            "⚖",
            "#9333ea",
            "#faf5ff",
        )

    with c2:
        kpi_card(
            "VALOR EM ACAREAÇÃO",
            brl(summary_value(resumo, "Valor em acareação", 0)),
            "Valor financeiro em aberto",
            "$",
            "#17633a",
            "#edf9f1",
            "#14532d",
        )

    st.divider()
    st.markdown("#### Entregadores responsáveis")
    render_table(acareacao_driver_summary(fila_filtrada), height=300)

    st.divider()
    st.markdown("#### Detalhe por AWB")
    render_table(acareacao_df, height=520)


elif menu == "pendcorp":
    st.markdown("### Top 5 clientes com pendência")
    st.caption("Agrupamento por cliente e pendência. Prioriza Pendência Corp quando existir.")
    render_table(pendcorp_df, height=360)

    st.divider()
    st.markdown("### Base de pendências analisada")
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
    t1, t2, t3, t4 = st.tabs(["Motoristas", "Retornos", "Pendência Corp", "EDI"])
    with t1:
        render_table(motoristas_df, height=360)
    with t2:
        render_table(retornos_df, height=360)
    with t3:
        render_table(pendcorp_df, height=260)
    with t4:
        render_table(edi_resumo, height=300)


elif menu == "config":
    st.markdown("### Configurações")
    st.success("Dashboard carregado com sucesso.")
    st.write("Fonte configurada:", SOURCE_URL)

    status_df = pd.DataFrame(
        [
            {"Aba": "RESUMO", "Linhas": len(resumo)},
            {"Aba": "FILA", "Linhas": len(fila)},
            {"Aba": "EDI_RESUMO", "Linhas": len(edi_resumo)},
            {"Aba": "EDI_DETALHE", "Linhas": len(edi_detalhe)},
            {"Aba": "PENDENCIA_MOVIMENTOS", "Linhas": len(pendencia_movimentos)},
            {"Filtro aplicado": filtro_msg, "Linhas após filtro": len(fila_filtrada)},
            {"Filtro aplicado": "AWBs por dia", "Linhas após filtro": len(daily_df)},
            {"Filtro aplicado": "Acareações em aberto", "Linhas após filtro": len(acareacao_df)},
        ]
    )
    render_table(status_df, height=220)

    st.info("Secrets necessários: MANAGER_SOURCE_URL e [gcp_service_account].")
