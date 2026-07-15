
import io
import re
import unicodedata
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Portal da Torre de Controle - V0",
    page_icon="📊",
    layout="wide",
)


# =========================
# UTILITÁRIOS
# =========================

def normalize_text(value):
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def normalize_awb(value):
    """
    Normaliza os formatos reais das fontes.

    REGRA DA PLANILHA DA TORRE / RETORNO FÍSICO:
    - Remove o prefixo 577.
    - Remove os 4 últimos dígitos.
    - O resultado deve ter 8 dígitos.
    - Se tiver 7 dígitos, completa com 0 à esquerda.

    Exemplos:
    577352504600001 -> 35250460
    577123456700001 -> 01234567  (quando o miolo tiver 7 dígitos úteis)

    OUTRAS FONTES:
    - Eu Entrego pode trazer 577 + AWB.
    - AWBStatus pode trazer a AWB pura.
    """
    if pd.isna(value):
        return None

    raw = str(value).strip()
    raw = re.sub(r"\.0$", "", raw)
    digits = re.sub(r"\D", "", raw)

    if not digits:
        return None

    # Formato de bipagem / Planilha da Torre:
    # 577 + conteúdo da AWB + 4 dígitos finais.
    if digits.startswith("577") and len(digits) >= 14:
        middle = digits[3:-4]
        # Mantém apenas os últimos 8 se houver lixo excedente,
        # ou completa com zero à esquerda quando tiver menos de 8.
        if len(middle) > 8:
            middle = middle[-8:]
        return middle.zfill(8)

    # Formato Eu Entrego: 577 + AWB
    if digits.startswith("577") and 10 <= len(digits) <= 12:
        middle = digits[3:]
        if len(middle) > 8:
            middle = middle[-8:]
        return middle.zfill(8)

    # AWB pura
    if len(digits) <= 8:
        return digits.zfill(8)

    # Fallback: tenta localizar 577 + bloco numérico
    match = re.search(r"577(\d+)", digits)
    if match:
        middle = match.group(1)
        if len(middle) >= 12:
            middle = middle[:-4]
        if len(middle) > 8:
            middle = middle[-8:]
        return middle.zfill(8)

    return digits[-8:].zfill(8)

def parse_date(series):
    return pd.to_datetime(series, errors="coerce", dayfirst=True)


def clean_columns(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def find_column(df, candidates):
    normalized = {normalize_text(c): c for c in df.columns}
    for candidate in candidates:
        key = normalize_text(candidate)
        if key in normalized:
            return normalized[key]
    return None


# =========================
# LEITURA DAS FONTES
# =========================

@st.cache_data(show_spinner=False)
def read_last_mile(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes))
    df = clean_columns(df)

    required = ["AWBNumber", "OPSStation", "StatusDescription", "ApproxSLA"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"AWBStatus sem colunas obrigatórias: {', '.join(missing)}")

    df["AWB"] = df["AWBNumber"].apply(normalize_awb)
    df["OPS_NORMALIZADO"] = df["OPSStation"].apply(normalize_text)

    # Regra oficial: Last Mile = somente CDSP2
    df = df[df["OPS_NORMALIZADO"] == "CDSP2"].copy()

    df["SLA_DATA"] = parse_date(df["ApproxSLA"]).dt.date
    df["STATUS_SISTEMA"] = df["StatusDescription"].astype(str).str.strip()

    # Mantém o registro operacional mais recente por AWB quando houver repetição.
    if "ExecutionDateTime" in df.columns:
        df["_DT_ORDEM"] = parse_date(df["ExecutionDateTime"])
    else:
        df["_DT_ORDEM"] = pd.NaT

    df = (
        df.sort_values(["AWB", "_DT_ORDEM"])
          .drop_duplicates("AWB", keep="last")
    )

    keep = [
        "AWB", "STATUS_SISTEMA", "SLA_DATA", "OPSStation",
        "OriginCode", "DestinationCode", "FltNo", "FltDt",
        "FltOrigin", "FltDestination", "BillTo", "DeliveryRequest"
    ]
    keep = [c for c in keep if c in df.columns]
    return df[keep].copy()


@st.cache_data(show_spinner=False)
def read_eu_entrego(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes))
    df = clean_columns(df)

    if "Pedido" not in df.columns:
        raise ValueError("Eu Entrego: coluna 'Pedido' não encontrada.")

    df["AWB"] = df["Pedido"].apply(normalize_awb)
    df["DATA_ROTA"] = parse_date(df.get("Data da Rota"))
    df["ULTIMA_ALTERACAO_DT"] = parse_date(df.get("Última alteração"))
    df["EXECUTADA_DT"] = parse_date(df.get("Executada"))

    # Uma AWB pode ter múltiplas rotas/eventos.
    # Usamos a última alteração como prioridade e a data da rota como fallback.
    df["_DT_ORDEM"] = df["ULTIMA_ALTERACAO_DT"].fillna(df["DATA_ROTA"])

    latest = (
        df.sort_values(["AWB", "_DT_ORDEM"])
          .drop_duplicates("AWB", keep="last")
          .copy()
    )

    latest = latest.rename(columns={
        "Data da Rota": "ULTIMA_ROTA",
        "Status": "STATUS_ULTIMA_ROTA",
        "Nome Entregador": "ULTIMO_ENTREGADOR",
        "Motivo": "MOTIVO_ULTIMA_ROTA",
        "Última alteração": "ULTIMA_ALTERACAO"
    })

    keep = [
        "AWB", "ULTIMA_ROTA", "STATUS_ULTIMA_ROTA",
        "ULTIMO_ENTREGADOR", "MOTIVO_ULTIMA_ROTA",
        "ULTIMA_ALTERACAO"
    ]
    latest = latest[[c for c in keep if c in latest.columns]]

    # Guarda todas as rotas para saber se houve rota HOJE.
    route_dates = df[["AWB", "DATA_ROTA"]].dropna()
    return latest, route_dates


@st.cache_data(show_spinner=False)
def read_torre(file_bytes):
    xls = pd.ExcelFile(io.BytesIO(file_bytes))

    valid_sheets = {
        "PENDENCIAS": "PENDENCIA",
        "PENDENCIA CORP": "PENDENCIA_CORP",
        "FINALIZADAS": "FINALIZADO",
    }

    events = []

    for sheet, event_type in valid_sheets.items():
        if sheet not in xls.sheet_names:
            continue

        df = pd.read_excel(xls, sheet_name=sheet)
        df = clean_columns(df)

        awb_col = find_column(df, ["AWB", "awb"])
        if not awb_col:
            continue

        df["AWB"] = df[awb_col].apply(normalize_awb)

        if sheet == "FINALIZADAS":
            final_col = find_column(df, ["DATA MOV. FINALIZAÇÃO", "DATA MOV FINALIZAÇÃO"])
            treatment_col = find_column(df, ["DATA DA TRATATIVA"])
            final_dt = parse_date(df[final_col]) if final_col else pd.Series(pd.NaT, index=df.index)
            treatment_dt = parse_date(df[treatment_col]) if treatment_col else pd.Series(pd.NaT, index=df.index)
            df["DATA_EVENTO"] = final_dt.fillna(treatment_dt)
        else:
            treatment_col = find_column(df, ["DATA DA TRATATIVA"])
            df["DATA_EVENTO"] = (
                parse_date(df[treatment_col])
                if treatment_col else pd.NaT
            )

        status_col = find_column(df, ["STATUS", " STATUS"])
        origin_col = find_column(df, ["ORIGEM", " ORIGEM ", "BASE DE ORIGEM"])
        reason_col = find_column(df, ["MOTIVO DA PENDENCIA"])

        part = pd.DataFrame({
            "AWB": df["AWB"],
            "EVENTO_TORRE": event_type,
            "DATA_EVENTO_TORRE": df["DATA_EVENTO"],
            "STATUS_TRATATIVA": df[status_col] if status_col else "",
            "ORIGEM_TORRE": df[origin_col] if origin_col else "",
            "MOTIVO_PENDENCIA": df[reason_col] if reason_col else "",
            "ABA_ORIGEM": sheet,
        })
        events.append(part)

    if not events:
        return pd.DataFrame(), pd.DataFrame()

    history = pd.concat(events, ignore_index=True)
    history = history[history["AWB"].notna()].copy()

    latest = (
        history.sort_values(["AWB", "DATA_EVENTO_TORRE"])
               .drop_duplicates("AWB", keep="last")
               .copy()
    )

    return latest, history


# =========================
# RETORNOS DO WHATSAPP
# =========================

def extract_returns(text):
    """
    Aceita:
    - Código completo: 577352504600001 -> 35250460
    - AWB direta de 8 dígitos.
    Pode colar texto inteiro copiado do WhatsApp.
    """
    if not text:
        return []

    found = set()

    # Código de bipagem: 577 + AWB(8) + 4 finais
    for match in re.findall(r"577(\d{8})\d{4}", text):
        found.add(match)

    # Também aceita AWB digitada diretamente
    for match in re.findall(r"(?<!\d)(\d{8})(?!\d)", text):
        found.add(match)

    return sorted(found)


# =========================
# MOTOR DE REGRAS V0
# =========================

def classify_row(row, today, returns_set):
    status_system = normalize_text(row.get("STATUS_SISTEMA"))
    tower_event = normalize_text(row.get("EVENTO_TORRE"))
    route_status = normalize_text(row.get("STATUS_ULTIMA_ROTA"))

    sla = row.get("SLA_DATA")
    last_route = pd.to_datetime(row.get("ULTIMA_ROTA"), errors="coerce")
    tower_date = pd.to_datetime(row.get("DATA_EVENTO_TORRE"), errors="coerce")

    route_today = bool(row.get("TEVE_ROTA_HOJE", False))
    returned = row.get("AWB") in returns_set

    # Status operacionais que não devem entrar em cobrança de entrega/retorno na V0.
    terminal_or_other_flow = {
        "ENTREGUE",
        "BAIXADO",
        "MISSING CARGO",
        "DISCREPANCIA CRIADA",
        "PENDENTE EMBARQUE",
        "PENDENTE DESEMBARQUE",
    }

    if status_system == "ENTREGUE":
        return "ENTREGUE", "SEM AÇÃO", "CONCLUÍDO", "BAIXA"

    # A situação atual da Torre prevalece quando o último evento é pendência.
    if tower_event in {"PENDENCIA", "PENDENCIA_CORP"}:
        return "PENDÊNCIA TORRE", "TRATAR PENDÊNCIA", "TORRE", "ALTA"

    # Uma carga finalizada pela Torre entra no fluxo de reentrega.
    if tower_event == "FINALIZADO":
        if pd.notna(last_route) and pd.notna(tower_date) and last_route > tower_date:
            if route_today:
                if route_status == "INSUCESSO":
                    return "INSUCESSO DO DIA", "AGUARDAR RETORNO", "LAST MILE", "MÉDIA"
                return "REENTREGA - ROTA DO DIA", "ACOMPANHAR ROTA", "LAST MILE", "MÉDIA"

            # Retorno atrasado só é acionável se a carga ainda estiver em Pendente Entrega.
            if (
                status_system == "PENDENTE ENTREGA"
                and route_status in {"INSUCESSO", "DEVOLVIDO"}
                and pd.notna(last_route)
                and last_route.date() < today
            ):
                if returned:
                    return "RETORNO CONFIRMADO", "DIRECIONAR CARGA", "EXPEDIÇÃO/TORRE", "ALTA"
                return (
                    "RETORNO PENDENTE",
                    "COBRAR ENTREGADOR",
                    row.get("ULTIMO_ENTREGADOR") or "LAST MILE",
                    "CRÍTICA",
                )

            return "REENTREGA EM NOVA TENTATIVA", "ACOMPANHAR", "LAST MILE", "MÉDIA"

        return "REENTREGA AGUARDANDO ROTA", "PROGRAMAR NOVA ROTA", "LAST MILE", "ALTA"

    # Rotas criadas hoje nunca entram na carteira de cobrança do dia.
    if route_today:
        if route_status == "INSUCESSO":
            return "INSUCESSO DO DIA", "AGUARDAR RETORNO", "LAST MILE", "MÉDIA"
        return "ROTA DO DIA", "ACOMPANHAR ROTA", "LAST MILE", "BAIXA"

    # Retorno confirmado pelo processo físico da Expedição.
    if returned:
        return "RETORNO CONFIRMADO", "VALIDAR DIRECIONAMENTO", "EXPEDIÇÃO/TORRE", "ALTA"

    # Não cria falso retorno para cargas já baixadas ou em outro fluxo.
    if status_system in terminal_or_other_flow:
        return "FORA DA FILA V0", "SEM AÇÃO V0", "MONITORAMENTO", "BAIXA"

    # Retorno pendente: somente carteira Pendente Entrega, rota anterior a hoje,
    # resultado de insucesso/devolvido, sem nova rota hoje e sem retorno físico.
    if (
        status_system == "PENDENTE ENTREGA"
        and route_status in {"INSUCESSO", "DEVOLVIDO"}
        and pd.notna(last_route)
        and last_route.date() < today
    ):
        return (
            "RETORNO PENDENTE",
            "COBRAR ENTREGADOR",
            row.get("ULTIMO_ENTREGADOR") or "LAST MILE",
            "CRÍTICA",
        )

    # Pendente de Entrega Real: SLA até hoje e nenhuma justificativa anterior.
    if (
        sla is not None
        and pd.notna(sla)
        and sla <= today
        and status_system == "PENDENTE ENTREGA"
    ):
        return "PENDENTE DE ENTREGA REAL", "ATUAR NA EXPEDIÇÃO", "LAST MILE", "ALTA"

    return "FORA DA FILA V0", "SEM AÇÃO V0", "MONITORAMENTO", "BAIXA"

def build_master(last_mile, eu_latest, route_dates, tower_latest, returns_set, today):
    master = last_mile.copy()

    master = master.merge(
        eu_latest,
        on="AWB",
        how="left",
        validate="one_to_one",
    )

    if not tower_latest.empty:
        cols = [
            "AWB", "EVENTO_TORRE", "DATA_EVENTO_TORRE",
            "STATUS_TRATATIVA", "ORIGEM_TORRE", "MOTIVO_PENDENCIA",
            "ABA_ORIGEM"
        ]
        master = master.merge(
            tower_latest[[c for c in cols if c in tower_latest.columns]],
            on="AWB",
            how="left",
            validate="one_to_one",
        )

    today_ts = pd.Timestamp(today)
    route_today_awbs = set(
        route_dates.loc[
            route_dates["DATA_ROTA"].dt.normalize() == today_ts,
            "AWB"
        ].dropna()
    )
    master["TEVE_ROTA_HOJE"] = master["AWB"].isin(route_today_awbs)
    master["RETORNO_CONFIRMADO"] = master["AWB"].isin(returns_set)

    results = master.apply(
        lambda row: classify_row(row, today, returns_set),
        axis=1,
        result_type="expand",
    )
    results.columns = [
        "SITUACAO_GERENCIAL",
        "ACAO_NECESSARIA",
        "RESPONSAVEL_ACAO",
        "PRIORIDADE",
    ]

    master = pd.concat([master, results], axis=1)
    return master


# =========================
# INTERFACE
# =========================

st.title("Portal de Gestão da Torre de Controle")
st.caption("V0 — Last Mile CDSP2 + Eu Entrego + Pendências da Torre")

with st.sidebar:
    st.header("Atualização das bases")

    file_lm = st.file_uploader(
        "1. AWBStatus — Last Mile",
        type=["xlsx", "xls"],
        help="O Portal manterá apenas OPSStation = CDSP2."
    )
    file_eu = st.file_uploader(
        "2. Eu Entrego",
        type=["xlsx", "xls"],
        help="Pedido será tratado como AWB."
    )
    file_torre = st.file_uploader(
        "3. Planilha da Torre",
        type=["xlsx", "xls"],
        help="Usa PENDENCIAS, PENDENCIA CORP e FINALIZADAS. Página81 é ignorada."
    )

    reference_date = st.date_input(
        "Data de análise",
        value=date.today(),
        help="Permite validar os números considerando uma data operacional específica."
    )

st.subheader("Retornos físicos")
st.write(
    "Cole aqui as mensagens ou códigos bipados no processo atual da Expedição. "
    "O processo operacional não é alterado; o Portal apenas interpreta os códigos."
)

returns_text = st.text_area(
    "Códigos / texto do WhatsApp",
    height=140,
    placeholder="Exemplo:\n577352504600001\n577342321440001",
)

return_awbs = extract_returns(returns_text)
if return_awbs:
    st.success(f"{len(return_awbs)} AWB(s) de retorno identificada(s).")
    with st.expander("Ver AWBs extraídas"):
        st.write(", ".join(return_awbs))

if not (file_lm and file_eu and file_torre):
    st.info("Envie os três arquivos na barra lateral para processar a V0.")
    st.stop()

try:
    with st.spinner("Processando bases e aplicando regras da V0..."):
        lm = read_last_mile(file_lm.getvalue())
        eu_latest, route_dates = read_eu_entrego(file_eu.getvalue())
        tower_latest, tower_history = read_torre(file_torre.getvalue())

        master = build_master(
            lm,
            eu_latest,
            route_dates,
            tower_latest,
            set(return_awbs),
            reference_date,
        )
except Exception as exc:
    st.error(f"Não foi possível processar os arquivos: {exc}")
    st.stop()



# Conciliação dos retornos colados
st.divider()
st.subheader("Conciliação dos retornos físicos")

master_awbs = set(master["AWB"].dropna().astype(str))
returns_input_set = set(return_awbs)
returns_found = sorted(returns_input_set & master_awbs)
returns_not_found = sorted(returns_input_set - master_awbs)

r1, r2, r3 = st.columns(3)
r1.metric("AWBs coladas", len(returns_input_set))
r2.metric("Encontradas na carteira CDSP2", len(returns_found))
r3.metric("Fora da carteira atual", len(returns_not_found))

if returns_not_found:
    with st.expander("Ver AWBs de retorno fora da carteira CDSP2"):
        st.dataframe(
            pd.DataFrame({"AWB": returns_not_found}),
            use_container_width=True,
            hide_index=True,
        )

# Diagnóstico dos cruzamentos
st.subheader("Diagnóstico dos cruzamentos")

lm_awbs = set(lm["AWB"].dropna().astype(str))
tower_current = tower_latest[
    tower_latest["EVENTO_TORRE"].isin(["PENDENCIA", "PENDENCIA_CORP"])
].copy()
tower_current_awbs = set(tower_current["AWB"].dropna().astype(str))

tower_in_lm = sorted(tower_current_awbs & lm_awbs)
tower_out_lm = sorted(tower_current_awbs - lm_awbs)

returns_other_class = master[
    master["RETORNO_CONFIRMADO"]
    & (master["SITUACAO_GERENCIAL"] != "RETORNO CONFIRMADO")
].copy()

d1, d2, d3, d4 = st.columns(4)
d1.metric("AWBs atuais na Torre", len(tower_current_awbs))
d2.metric("Torre encontradas no CDSP2", len(tower_in_lm))
d3.metric("Torre fora do CDSP2", len(tower_out_lm))
d4.metric("Retornos com outra situação", len(returns_other_class))

with st.expander("Ver diagnóstico detalhado"):
    tab1, tab2, tab3 = st.tabs([
        "Torre x CDSP2",
        "Torre fora do CDSP2",
        "Retornos com outra situação",
    ])

    with tab1:
        st.dataframe(
            tower_current[tower_current["AWB"].isin(tower_in_lm)],
            use_container_width=True,
            hide_index=True,
        )

    with tab2:
        st.dataframe(
            tower_current[tower_current["AWB"].isin(tower_out_lm)],
            use_container_width=True,
            hide_index=True,
        )

    with tab3:
        cols_diag = [
            "AWB", "SITUACAO_GERENCIAL", "STATUS_SISTEMA",
            "ULTIMA_ROTA", "STATUS_ULTIMA_ROTA",
            "EVENTO_TORRE", "DATA_EVENTO_TORRE"
        ]
        cols_diag = [c for c in cols_diag if c in returns_other_class.columns]
        st.dataframe(
            returns_other_class[cols_diag],
            use_container_width=True,
            hide_index=True,
        )

# KPIs
st.divider()

st.subheader("Visão operacional V0")

priority_classes = [
    "PENDENTE DE ENTREGA REAL",
    "PENDÊNCIA TORRE",
    "REENTREGA AGUARDANDO ROTA",
    "RETORNO PENDENTE",
]

counts = master["SITUACAO_GERENCIAL"].value_counts()

cols = st.columns(4)
for col, label in zip(cols, priority_classes):
    col.metric(label.title(), int(counts.get(label, 0)))

cols2 = st.columns(4)
secondary = [
    "ROTA DO DIA",
    "INSUCESSO DO DIA",
    "RETORNO CONFIRMADO",
    "ENTREGUE",
]
for col, label in zip(cols2, secondary):
    col.metric(label.title(), int(counts.get(label, 0)))

st.caption(
    f"Retorno físico confirmado é uma dimensão independente: "
    f"{int(master['RETORNO_CONFIRMADO'].sum())} AWB(s) da carteira atual possuem bipagem de retorno, "
    "mesmo quando a situação gerencial principal é Pendência Torre, Rota do Dia ou outra classificação."
)


# Fila de ação
st.subheader("Fila de ação")
action_df = master[
    master["SITUACAO_GERENCIAL"].isin([
        "PENDENTE DE ENTREGA REAL",
        "PENDÊNCIA TORRE",
        "REENTREGA AGUARDANDO ROTA",
        "RETORNO PENDENTE",
        "RETORNO CONFIRMADO",
    ])
].copy()

priority_order = {"CRÍTICA": 1, "ALTA": 2, "MÉDIA": 3, "BAIXA": 4}
action_df["_ORDEM"] = action_df["PRIORIDADE"].map(priority_order).fillna(9)
action_df = action_df.sort_values(["_ORDEM", "SLA_DATA", "AWB"])

display_cols = [
    "PRIORIDADE", "AWB", "SITUACAO_GERENCIAL",
    "ACAO_NECESSARIA", "RESPONSAVEL_ACAO",
    "SLA_DATA", "STATUS_SISTEMA", "ULTIMA_ROTA",
    "STATUS_ULTIMA_ROTA", "ULTIMO_ENTREGADOR",
    "EVENTO_TORRE", "DATA_EVENTO_TORRE",
]
display_cols = [c for c in display_cols if c in action_df.columns]

st.dataframe(
    action_df[display_cols],
    use_container_width=True,
    hide_index=True,
)


# Detalhamento por categoria
st.subheader("Análise detalhada")
selected_class = st.selectbox(
    "Situação gerencial",
    ["TODAS"] + sorted(master["SITUACAO_GERENCIAL"].dropna().unique().tolist())
)

detail = master if selected_class == "TODAS" else master[
    master["SITUACAO_GERENCIAL"] == selected_class
]
st.dataframe(detail.drop(columns=["_ORDEM"], errors="ignore"), use_container_width=True, hide_index=True)


# Performance da Torre
st.subheader("Performance da Torre")
if not tower_history.empty:
    event_dates = tower_history["DATA_EVENTO_TORRE"].dt.date
    entries_today = (
        event_dates.eq(reference_date)
        & tower_history["EVENTO_TORRE"].isin(["PENDENCIA", "PENDENCIA_CORP"])
    ).sum()
    exits_today = (
        event_dates.eq(reference_date)
        & tower_history["EVENTO_TORRE"].eq("FINALIZADO")
    ).sum()
    current_backlog = tower_latest[
        tower_latest["EVENTO_TORRE"].isin(["PENDENCIA", "PENDENCIA_CORP"])
    ]["AWB"].nunique()

    c1, c2, c3 = st.columns(3)
    c1.metric("Entradas na Torre", int(entries_today))
    c2.metric("Saídas da Torre", int(exits_today))
    c3.metric("Backlog atual", int(current_backlog))


# Download
st.subheader("Exportação")
output = io.BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    master.to_excel(writer, index=False, sheet_name="BASE_MESTRE_V0")
    action_df.drop(columns=["_ORDEM"], errors="ignore").to_excel(
        writer, index=False, sheet_name="FILA_ACAO"
    )
    tower_history.to_excel(writer, index=False, sheet_name="HISTORICO_TORRE")

    pd.DataFrame({
        "INDICADOR": [
            "AWBs atuais na Torre",
            "Torre encontradas no CDSP2",
            "Torre fora do CDSP2",
            "Retornos colados",
            "Retornos encontrados no CDSP2",
            "Retornos com outra situação gerencial",
        ],
        "QUANTIDADE": [
            len(tower_current_awbs),
            len(tower_in_lm),
            len(tower_out_lm),
            len(returns_input_set),
            len(returns_found),
            len(returns_other_class),
        ],
    }).to_excel(writer, index=False, sheet_name="DIAGNOSTICO")

    tower_current[tower_current["AWB"].isin(tower_out_lm)].to_excel(
        writer, index=False, sheet_name="TORRE_FORA_CDSP2"
    )

st.download_button(
    "Baixar resultado da V0 em Excel",
    data=output.getvalue(),
    file_name=f"Base_Mestre_Torre_V0_{reference_date}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.caption(
    "V0 em validação. As regras de retorno físico dependem dos códigos colados no campo de retornos. "
    "As classificações serão refinadas após validação operacional das AWBs."
)
