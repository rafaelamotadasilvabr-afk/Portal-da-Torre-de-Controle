import html
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
# CSS - LAYOUT EXECUTIVO GDS
# =========================================================
st.markdown(
    """
    <style>
    :root {
        --navy-950:#06162f;
        --navy-900:#082347;
        --navy-800:#103b76;
        --blue:#2f6fed;
        --red:#d92d20;
        --amber:#d97706;
        --purple:#6d3fd1;
        --green:#17633a;
        --ink:#10213d;
        --muted:#66758c;
        --line:#e2e8f0;
        --panel:#ffffff;
        --bg:#f5f7fb;
    }

    .stApp {
        background: var(--bg);
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    .block-container {
        padding-top: .35rem;
        padding-bottom: 1.4rem;
        max-width: 1680px;
    }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background:
          radial-gradient(circle at 50% 0%, rgba(47,111,237,.24), transparent 30%),
          linear-gradient(180deg, #06162f 0%, #082347 58%, #061a36 100%);
        border-right: 1px solid rgba(255,255,255,.08);
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: .9rem;
    }

    .brand-box {
        padding: 8px 8px 20px;
        border-bottom: 1px solid rgba(255,255,255,.10);
        margin-bottom: 16px;
        text-align: left;
    }

    .brand-gds {
        color: white;
        font-size: 2.95rem;
        line-height: .9;
        font-weight: 950;
        letter-spacing: -.06em;
        font-style: italic;
    }

    .brand-log {
        color: white;
        font-size: .82rem;
        letter-spacing: .42em;
        font-weight: 800;
        margin-left: 4px;
        margin-top: 7px;
    }

    .nav-stack {
        display:flex;
        flex-direction:column;
        gap:7px;
    }

    .nav-item {
        display:flex;
        align-items:center;
        gap:11px;
        padding:11px 13px;
        color:#dce8f8;
        border-radius:11px;
        font-size:.88rem;
        border:1px solid transparent;
    }

    .nav-item.active {
        background:linear-gradient(90deg, #0b4ea7 0%, #123b76 100%);
        color:white;
        border-color:rgba(255,255,255,.08);
        box-shadow:0 8px 18px rgba(0,0,0,.14);
        font-weight:750;
    }

    .nav-icon {
        width:23px;
        text-align:center;
        font-size:1rem;
    }

    .side-foot {
        margin-top:26px;
        border-top:1px solid rgba(255,255,255,.10);
        padding-top:16px;
        color:#b9c8dc;
        font-size:.76rem;
        line-height:1.5;
    }

    /* HEADER */
    .exec-header {
        background:
          radial-gradient(circle at 85% 15%, rgba(47,111,237,.22), transparent 28%),
          linear-gradient(120deg, #071a37 0%, #082347 58%, #103b76 100%);
        color:#fff;
        border-radius:0 0 20px 20px;
        padding:20px 26px 18px;
        margin:-.35rem -.15rem 12px;
        box-shadow:0 12px 28px rgba(8,35,71,.16);
    }

    .meta-row {
        display:flex;
        flex-wrap:wrap;
        gap:8px;
        margin-bottom:11px;
    }

    .meta-pill {
        display:inline-flex;
        align-items:center;
        gap:6px;
        padding:6px 10px;
        border:1px solid rgba(255,255,255,.20);
        background:rgba(255,255,255,.07);
        color:#f8fbff;
        border-radius:8px;
        font-size:.74rem;
        font-weight:700;
    }

    .exec-header h1 {
        font-size:2rem;
        line-height:1.08;
        letter-spacing:-.035em;
        margin:0 0 6px;
    }

    .exec-header p {
        margin:0;
        color:#d7e5f8;
        font-size:.93rem;
    }

    .info-strip {
        display:flex;
        align-items:center;
        gap:8px;
        background:#fff;
        border:1px solid var(--line);
        border-radius:12px;
        padding:10px 13px;
        color:#55708f;
        font-size:.80rem;
        margin-bottom:12px;
        box-shadow:0 4px 12px rgba(15,23,42,.025);
    }

    .section-kicker {
        font-size:.88rem;
        font-weight:850;
        color:#0f2341;
        margin:4px 0 9px;
        letter-spacing:.02em;
    }

    /* KPI */
    .kpi-card {
        position:relative;
        background:#fff;
        border:1px solid var(--line);
        border-radius:15px;
        padding:14px 14px 13px;
        min-height:142px;
        box-shadow:0 8px 20px rgba(15,23,42,.05);
        overflow:hidden;
    }

    .kpi-card::before {
        content:"";
        position:absolute;
        top:0;
        left:0;
        right:0;
        height:4px;
        background:var(--accent);
    }

    .kpi-head {
        display:flex;
        align-items:center;
        gap:10px;
        min-height:40px;
        margin-bottom:9px;
    }

    .kpi-icon {
        width:36px;
        height:36px;
        border-radius:10px;
        display:flex;
        align-items:center;
        justify-content:center;
        color:var(--accent);
        background:var(--soft);
        font-size:1rem;
        font-weight:850;
        flex:none;
    }

    .kpi-title {
        color:#31435f;
        font-size:.76rem;
        font-weight:800;
        line-height:1.18;
    }

    .kpi-value {
        color:var(--value);
        font-size:1.88rem;
        line-height:1;
        font-weight:900;
        letter-spacing:-.04em;
        margin-bottom:8px;
    }

    .kpi-desc {
        color:#708099;
        font-size:.70rem;
        line-height:1.35;
    }

    /* PANELS */
    .panel {
        background:#fff;
        border:1px solid var(--line);
        border-radius:16px;
        padding:16px 18px;
        box-shadow:0 8px 22px rgba(15,23,42,.045);
        margin-bottom:12px;
        min-height:100%;
    }

    .panel-title {
        font-size:1.02rem;
        font-weight:850;
        color:#10213d;
        margin:0 0 3px;
        letter-spacing:-.015em;
    }

    .panel-sub {
        color:#718096;
        font-size:.76rem;
        margin-bottom:14px;
    }

    /* DONUT */
    .donut-wrap {
        display:grid;
        grid-template-columns:minmax(190px, .85fr) 1.15fr;
        gap:20px;
        align-items:center;
        min-height:300px;
    }

    .donut {
        width:220px;
        height:220px;
        margin:auto;
        border-radius:50%;
        position:relative;
        box-shadow:inset 0 0 0 1px rgba(15,23,42,.06);
    }

    .donut-hole {
        position:absolute;
        width:120px;
        height:120px;
        left:50%;
        top:50%;
        transform:translate(-50%,-50%);
        background:#fff;
        border-radius:50%;
        display:flex;
        align-items:center;
        justify-content:center;
        text-align:center;
        box-shadow:0 0 0 1px #e5eaf1;
    }

    .donut-total-small {
        color:#687891;
        font-size:.70rem;
    }

    .donut-total-value {
        color:#10213d;
        font-size:1.75rem;
        font-weight:900;
        line-height:1;
        margin:3px 0;
    }

    .legend-row {
        display:grid;
        grid-template-columns:12px 1fr auto auto;
        gap:8px;
        align-items:center;
        padding:8px 0;
        border-bottom:1px solid #eef2f7;
        color:#334155;
        font-size:.78rem;
    }

    .legend-dot {
        width:9px;
        height:9px;
        border-radius:50%;
    }

    .legend-value {
        font-weight:800;
        color:#10213d;
    }

    .legend-pct {
        color:#75849a;
        min-width:42px;
        text-align:right;
    }

    /* RANKING */
    .rank-head {
        display:grid;
        grid-template-columns:38px 1.35fr 1fr 1.3fr 70px;
        gap:10px;
        padding:8px 4px;
        color:#718096;
        font-size:.68rem;
        font-weight:800;
        text-transform:uppercase;
        border-bottom:1px solid #e7ebf1;
    }

    .rank-row {
        display:grid;
        grid-template-columns:38px 1.35fr 1fr 1.3fr 70px;
        gap:10px;
        align-items:center;
        padding:10px 4px;
        border-bottom:1px solid #eef2f7;
        font-size:.77rem;
        color:#334155;
    }

    .rank-n {
        width:24px;
        height:24px;
        border-radius:50%;
        display:flex;
        align-items:center;
        justify-content:center;
        background:#0a2146;
        color:#fff;
        font-weight:850;
        font-size:.70rem;
    }

    .rank-label {
        font-weight:750;
        color:#1f334f;
    }

    .bar-track {
        height:8px;
        border-radius:999px;
        background:#edf2f7;
        overflow:hidden;
    }

    .bar-fill {
        height:100%;
        border-radius:999px;
        background:linear-gradient(90deg,#0a2146,#2f6fed);
    }

    .rank-value {
        font-weight:850;
        color:#10213d;
        text-align:right;
    }

    .queue-caption {
        color:#718096;
        font-size:.76rem;
        margin:-2px 0 8px;
    }

    div[data-testid="stDataFrame"] {
        border:1px solid #e2e8f0;
        border-radius:12px;
        overflow:hidden;
    }

    div[data-testid="stButton"] button {
        border-radius:10px;
        border:1px solid #cbd5e1;
        background:#fff;
        color:#10213d;
        font-weight:750;
        font-size:.78rem;
    }

    @media (max-width: 1100px) {
        .donut-wrap {
            grid-template-columns:1fr;
        }
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


def find_numeric_col(df):
    if df is None or df.empty:
        return None

    best = None
    best_count = -1
    for col in df.columns:
        converted = pd.to_numeric(
            df[col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
            errors="coerce",
        )
        count = converted.notna().sum()
        if count > best_count:
            best = col
            best_count = count
    return best


def numeric_series(df, col):
    return pd.to_numeric(
        df[col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0)


def first_label_col(df, numeric_col):
    for col in df.columns:
        if col != numeric_col:
            return col
    return df.columns[0]


def kpi_card(label, value, desc, icon, accent, soft, value_color=None):
    value_color = value_color or "#10213d"
    st.markdown(
        f"""
        <div class="kpi-card"
             style="--accent:{accent};--soft:{soft};--value:{value_color};">
            <div class="kpi-head">
                <div class="kpi-icon">{icon}</div>
                <div class="kpi-title">{label}</div>
            </div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_donut_html(df):
    colors = ["#0a2146", "#355f99", "#6f8fb7", "#a9b5c5", "#d2d8df", "#7b8ea8", "#234d80"]

    if df is None or df.empty:
        return '<div style="padding:40px;color:#64748b">Sem dados de problemas.</div>'

    value_col = find_numeric_col(df)
    if value_col is None:
        return '<div style="padding:40px;color:#64748b">Sem dados numéricos.</div>'

    label_col = first_label_col(df, value_col)

    tmp = df[[label_col, value_col]].copy()
    tmp[value_col] = numeric_series(tmp, value_col)
    tmp = tmp[tmp[value_col] > 0].sort_values(value_col, ascending=False).head(5)

    total = float(tmp[value_col].sum())
    if total <= 0:
        return '<div style="padding:40px;color:#64748b">Sem dados para distribuição.</div>'

    segments = []
    legend = []
    cursor = 0.0

    for i, (_, row) in enumerate(tmp.iterrows()):
        label = html.escape(str(row[label_col]))
        value = float(row[value_col])
        pct = (value / total) * 100
        start = cursor
        end = cursor + pct
        color = colors[i % len(colors)]
        segments.append(f"{color} {start:.2f}% {end:.2f}%")
        cursor = end

        legend.append(
            f"""
            <div class="legend-row">
                <span class="legend-dot" style="background:{color}"></span>
                <span>{label}</span>
                <span class="legend-value">{int(round(value)):,}</span>
                <span class="legend-pct">{pct:.0f}%</span>
            </div>
            """
        )

    gradient = ", ".join(segments)

    return f"""
    <div class="donut-wrap">
        <div class="donut" style="background:conic-gradient({gradient});">
            <div class="donut-hole">
                <div>
                    <div class="donut-total-small">Total de</div>
                    <div class="donut-total-value">{int(round(total)):,}</div>
                    <div class="donut-total-small">pendências</div>
                </div>
            </div>
        </div>
        <div>
            {''.join(legend)}
        </div>
    </div>
    """.replace(",", ".")


def build_ranking_html(df):
    if df is None or df.empty:
        return '<div style="padding:40px;color:#64748b">Sem concentrações de pendência para exibir.</div>'

    value_col = find_numeric_col(df)
    if value_col is None:
        return '<div style="padding:40px;color:#64748b">Sem dados numéricos.</div>'

    label_col = first_label_col(df, value_col)

    tmp = df.copy()
    tmp[value_col] = numeric_series(tmp, value_col)
    tmp = tmp.sort_values(value_col, ascending=False).head(6)

    max_value = max(float(tmp[value_col].max()), 1)

    rows = []
    for pos, (_, row) in enumerate(tmp.iterrows(), start=1):
        label = html.escape(str(row[label_col]))
        value = float(row[value_col])
        pct = (value / max_value) * 100

        category = ""
        for col in tmp.columns:
            if col not in [label_col, value_col]:
                text = str(row[col]).strip()
                if text and text.lower() != "nan":
                    category = html.escape(text)
                    break

        rows.append(
            f"""
            <div class="rank-row">
                <div class="rank-n">{pos}</div>
                <div class="rank-label">{label}</div>
                <div>{category or "—"}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{pct:.1f}%"></div>
                </div>
                <div class="rank-value">{int(round(value)):,}</div>
            </div>
            """
        )

    return (
        """
        <div class="rank-head">
            <div>#</div>
            <div>Base / responsável</div>
            <div>Categoria</div>
            <div>Concentração</div>
            <div style="text-align:right">Qtd.</div>
        </div>
        """
        + "".join(rows)
    ).replace(",", ".")

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
    st.error("Fonte automática não configurada. Adicione MANAGER_SOURCE_URL nos Secrets.")
    st.stop()

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown(
        """
        <div class="brand-box">
            <div class="brand-gds">GDS</div>
            <div class="brand-log">LOGÍSTICA</div>
        </div>

        <div class="nav-stack">
            <div class="nav-item active"><span class="nav-icon">⌂</span>Visão Geral</div>
            <div class="nav-item"><span class="nav-icon">↗</span>Monitoramento</div>
            <div class="nav-item"><span class="nav-icon">▣</span>Pendências</div>
            <div class="nav-item"><span class="nav-icon">⚖</span>Acareações</div>
            <div class="nav-item"><span class="nav-icon">◔</span>Performance</div>
            <div class="nav-item"><span class="nav-icon">▤</span>Relatórios</div>
            <div class="nav-item"><span class="nav-icon">!</span>Alertas</div>
            <div class="nav-item"><span class="nav-icon">⚙</span>Configurações</div>
        </div>

        <div class="side-foot">
            <b>Dashboard Gerencial</b><br>
            Atualização automática<br>
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

# =========================================================
# HEADER
# =========================================================
st.markdown(
    f"""
    <div class="exec-header">
        <div class="meta-row">
            <span class="meta-pill">TORRE DE CONTROLE</span>
            <span class="meta-pill">VISÃO EXECUTIVA</span>
            <span class="meta-pill">▣ PERÍODO ANALISADO: {periodo}</span>
            <span class="meta-pill">◷ ATUALIZADO EM: {atualizado}</span>
        </div>

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

# =========================================================
# KPIs
# =========================================================
st.markdown('<div class="section-kicker">VISÃO EXECUTIVA</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    kpi_card(
        "AWBs Monitoradas",
        fmt_int(summary_value(resumo, "AWBs monitoradas", 0)),
        "Carteira única atualmente acompanhada",
        "▣",
        "#2f6fed",
        "#edf4ff",
    )

with k2:
    kpi_card(
        "Entrega em atraso",
        fmt_int(summary_value(resumo, "Entrega em atraso", 0)),
        "Cargas com SLA vencido",
        "◷",
        "#d92d20",
        "#fff0ef",
        "#c9231a",
    )

with k3:
    kpi_card(
        "SLA do dia sem rota",
        fmt_int(summary_value(resumo, "SLA do dia sem rota", 0)),
        "Cargas do dia ainda sem rota criada",
        "▦",
        "#d97706",
        "#fff7e8",
        "#b96804",
    )

with k4:
    kpi_card(
        "Backlog da Torre",
        fmt_int(summary_value(resumo, "Backlog da Torre", 0)),
        "Pendências ainda não finalizadas",
        "≡",
        "#6d3fd1",
        "#f4efff",
        "#5b2dbf",
    )

with k5:
    kpi_card(
        "Acareações em andamento",
        fmt_int(summary_value(resumo, "Acareações em andamento", 0)),
        "Tratativas ativas neste momento",
        "⚖",
        "#2459c4",
        "#edf4ff",
        "#16449f",
    )

with k6:
    kpi_card(
        "Valor em acareação",
        brl(summary_value(resumo, "Valor em acareação", 0)),
        "Valor financeiro atualmente exposto",
        "$",
        "#17633a",
        "#edf9f1",
        "#14532d",
    )

# =========================================================
# PAINÉIS CENTRAIS
# =========================================================
st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

c1, c2 = st.columns([1, 1.25])

with c1:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Onde está o problema?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel-sub">Distribuição das pendências por categoria operacional.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(build_donut_html(top_problemas), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel-title">Maiores concentrações de pendência</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="panel-sub">Bases ou responsáveis com maior volume de pendências em aberto.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(build_ranking_html(top_bases), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# FILA EXECUTIVA
# =========================================================
st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown('<div class="panel-title">Fila executiva de atenção</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="queue-caption">Pendências críticas e de maior impacto que exigem acompanhamento gerencial.</div>',
    unsafe_allow_html=True,
)

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

    st.dataframe(
        queue.head(15),
        use_container_width=True,
        hide_index=True,
        height=430,
    )
else:
    st.info("Sem ações executivas para exibir.")

st.markdown('</div>', unsafe_allow_html=True)
