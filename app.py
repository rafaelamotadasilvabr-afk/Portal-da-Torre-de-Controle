
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
    Regra oficial de normalização da AWB:

    Sempre que o código começar por 577:
    - descarta o prefixo 577;
    - pega exatamente os 8 dígitos seguintes;
    - ignora qualquer sufixo restante.

    Exemplos:
    5771788444250001 -> 17884442
    577178694340001  -> 17869434
    577003801330001  -> 00380133

    Se vier uma AWB pura, preserva/completa para 8 dígitos.
    """
    if pd.isna(value):
        return None

    raw = str(value).strip()
    raw = re.sub(r"\.0$", "", raw)
    digits = re.sub(r"\D", "", raw)

    if not digits:
        return None

    # Regra oficial: 577 + AWB(8) + qualquer sufixo
    if digits.startswith("577") and len(digits) >= 11:
        return digits[3:11]

    # AWB pura
    if len(digits) <= 8:
        return digits.zfill(8)

    return None

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


def classify_sao12_client(value):
    """
    Mantém somente os clientes corporativos de interesse no SAO12.
    Retorna nome padronizado ou None para descartar.
    """
    text = normalize_text(value)

    if "RIACHUELO" in text:
        return "Riachuelo"
    if "JJGC" in text or "JJC" in text or "NEODENT" in text:
        return "Neodent"
    if "DELLA VIA" in text:
        return "Della Via"
    if "STONE" in text:
        return "Stone"
    if "TB COMERCIO" in text or "TANIA BULHOES" in text or "TANIA BULHÕES" in text:
        return "Tania Bulhões"
    if "ATS VIAGENS" in text or text.startswith("ATS"):
        return "ATS"
    if "INBRANDS" in text:
        return "Inbrands"

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

    # Conta as tentativas registradas nas colunas Tentativa 1/2/3 do Eu Entrego.
    tentativa_cols = [
        c for c in df.columns
        if normalize_text(c).startswith("TENTATIVA")
    ]
    if tentativa_cols:
        tentativas_preenchidas = df[tentativa_cols].notna() & df[tentativa_cols].astype(str).ne("")
        df["QT_TENTATIVAS_INSUCESSO"] = tentativas_preenchidas.sum(axis=1)
    else:
        df["QT_TENTATIVAS_INSUCESSO"] = 0

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
        "ULTIMA_ALTERACAO", "QT_TENTATIVAS_INSUCESSO"
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



@st.cache_data(show_spinner=False)
def read_first_mile_awbstatus(file_bytes, base_name):
    df = pd.read_excel(io.BytesIO(file_bytes))
    df = clean_columns(df)

    required = ["AWBNumber", "StatusDescription"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"{base_name}: colunas obrigatórias ausentes: {', '.join(missing)}"
        )

    df["AWB"] = df["AWBNumber"].apply(normalize_awb)
    df["BASE_EMISSORA"] = base_name
    df["STATUS_SISTEMA"] = df["StatusDescription"].astype(str).str.strip()
    df["STATUS_NORMALIZADO"] = df["STATUS_SISTEMA"].apply(normalize_text)

    if "ApproxSLA" in df.columns:
        df["SLA_DATA"] = parse_date(df["ApproxSLA"]).dt.date
    else:
        df["SLA_DATA"] = pd.NaT

    if "ExecutionDateTime" in df.columns:
        df["_DT_ORDEM"] = parse_date(df["ExecutionDateTime"])
    else:
        df["_DT_ORDEM"] = pd.NaT

    # Regra SAO12: manter somente clientes corporativos selecionados.
    if base_name == "SAO12":
        if "BillTo" not in df.columns:
            raise ValueError("SAO12: coluna BillTo não encontrada para filtrar clientes.")

        df["CLIENTE_PADRONIZADO"] = df["BillTo"].apply(classify_sao12_client)
        df = df[df["CLIENTE_PADRONIZADO"].notna()].copy()
    else:
        # TRES1: por enquanto mantém toda a carteira.
        df["CLIENTE_PADRONIZADO"] = df.get("BillTo", "").apply(
            lambda x: str(x).strip() if pd.notna(x) else ""
        )

    df = (
        df.sort_values(["AWB", "_DT_ORDEM"])
          .drop_duplicates("AWB", keep="last")
          .copy()
    )
    return df


@st.cache_data(show_spinner=False)
def read_edi_files(files_payload):
    frames = []
    audit = []

    for file_name, file_bytes in files_payload:
        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
            df = clean_columns(df)
            df["ARQUIVO_EDI"] = file_name
            frames.append(df)
            audit.append({
                "ARQUIVO": file_name,
                "REGISTROS": len(df),
                "STATUS": "OK",
                "ERRO": "",
            })
        except Exception as exc:
            audit.append({
                "ARQUIVO": file_name,
                "REGISTROS": 0,
                "STATUS": "ERRO",
                "ERRO": str(exc),
            })

    consolidated = (
        pd.concat(frames, ignore_index=True, sort=False)
        if frames else pd.DataFrame()
    )
    return consolidated, pd.DataFrame(audit)


def first_mile_status_group(value):
    status = normalize_text(value)
    if status == "PENDENTE EMBARQUE":
        return "PENDENTE DE EMBARQUE"
    if status == "PENDENTE DESEMBARQUE":
        return "PENDENTE DE DESEMBARQUE"
    if status == "MISSING CARGO":
        return "MISSING"
    if "DISCREP" in status:
        return "DISCREPÂNCIA"
    if status == "BAIXADO":
        return "BAIXADO"
    return "OUTROS"


def safe_dataframe_for_streamlit(df):
    """
    Evita erro do PyArrow em colunas EDI com tipos misturados.
    Mantém números/datas quando homogêneos e converte colunas object problemáticas para texto.
    """
    safe = df.copy()
    for col in safe.columns:
        if safe[col].dtype == "object":
            safe[col] = safe[col].apply(
                lambda x: "" if pd.isna(x) else str(x)
            )
    return safe

def edi_client_name(row):
    """
    Padroniza clientes EDI conhecidos pelo ID_Empresa.
    Novos IDs continuam visíveis para posterior mapeamento.
    """
    company_id = str(row.get("ID_Empresa", "")).strip().replace(".0", "")
    mapping = {
        "1422": "Riachuelo",
        "1708": "Três Corações",
        "3608": "Neodent",
        "4358": "Della Via",
    }
    return mapping.get(company_id, f"Cliente {company_id}" if company_id else "Não identificado")


def classify_edi_status(row):
    """
    Regra operacional validada para Booking EDI.

    Recebimento e Integracao são etapas sistêmicas e NÃO encerram Booking.
    A existência de AWB também NÃO encerra Booking.

    BOOKING REAL:
    - última ocorrência indica Booking;
    - sem CTe efetivamente gerado;
    - sem emissão de CTe;
    - sem embarque;
    - sem entrega.

    BOOKING JÁ EXECUTADO:
    - registro de Booking que já avançou para emissão/CTe,
      embarque ou entrega.

    NÃO EXECUTADO:
    - não está classificado como Booking;
    - e não possui evidência de execução operacional.
    """
    occurrence = normalize_text(row.get("UltimaOcorrencia", ""))

    def filled(value):
        if pd.isna(value):
            return False
        return str(value).strip().upper() not in {"", "NAN", "NONE", "NAT"}

    emissao_ok = filled(row.get("EmissaoCTe"))
    embarque_ok = filled(row.get("EmbarqueVoo"))
    entrega_ok = filled(row.get("EntregaCarga"))

    cte_value = normalize_text(row.get("CTeGerado", ""))
    cte_ok = cte_value in {"SIM", "YES", "S", "TRUE", "1"}

    is_booking = (
        "BOOKING" in occurrence
        or "BOOKED" in occurrence
        or occurrence.startswith("BKD")
    )

    avancou = emissao_ok or cte_ok or embarque_ok or entrega_ok

    if is_booking and not avancou:
        return "BOOKING REAL"

    if is_booking and avancou:
        return "BOOKING JÁ EXECUTADO"

    if not avancou:
        if "VOID" in occurrence or occurrence.startswith("107"):
            return "AWB ANULADA"
        return "AGUARDANDO BOOKING"

    return "FORA DO BOOKING"

def normalize_cross_key(value):
    """Normaliza AWB para cruzamento EDI x Emissões."""
    return normalize_awb(value)


def mark_edi_execution_from_first_mile(edi_df, first_mile_df):
    """
    Cruza pendências EDI com o First Mile.

    Regra:
    - Se uma AWB classificada como BOOKING REAL ou AGUARDANDO BOOKING
      já existe em SAO12/TRES1, ela não deve continuar como pendência EDI.
    - A carga passa a ser tratada pelo status operacional atual do First Mile.
    """
    result = edi_df.copy()

    result["_AWB_CRUZAMENTO"] = result.get(
        "Nº AWB",
        pd.Series(index=result.index, dtype=object)
    ).apply(normalize_cross_key)

    result["ENCONTRADO_EMISSOES"] = False
    result["STATUS_FIRST_MILE_ATUAL"] = ""
    result["BASE_FIRST_MILE"] = ""

    if first_mile_df is None or first_mile_df.empty:
        return result

    fm_lookup = (
        first_mile_df[
            ["AWB", "BASE_EMISSORA", "STATUS_SISTEMA"]
        ]
        .dropna(subset=["AWB"])
        .drop_duplicates("AWB", keep="last")
        .copy()
    )

    fm_lookup["AWB"] = fm_lookup["AWB"].astype(str)

    status_map = fm_lookup.set_index("AWB")["STATUS_SISTEMA"].to_dict()
    base_map = fm_lookup.set_index("AWB")["BASE_EMISSORA"].to_dict()

    result["ENCONTRADO_EMISSOES"] = result["_AWB_CRUZAMENTO"].isin(status_map)
    result["STATUS_FIRST_MILE_ATUAL"] = (
        result["_AWB_CRUZAMENTO"].map(status_map).fillna("")
    )
    result["BASE_FIRST_MILE"] = (
        result["_AWB_CRUZAMENTO"].map(base_map).fillna("")
    )

    mask_advanced = (
        result["ENCONTRADO_EMISSOES"]
        & result["STATUS_EDI_GERENCIAL"].isin(
            ["BOOKING REAL", "AGUARDANDO BOOKING"]
        )
    )

    result.loc[
        mask_advanced,
        "STATUS_EDI_GERENCIAL"
    ] = "JÁ AVANÇOU NO FIRST MILE"

    return result


# =========================
# RETORNOS DO WHATSAPP
# =========================

def extract_returns(text):
    """
    Extrai AWBs do texto do WhatsApp.

    Regra oficial:
    qualquer código que contenha 577 seguido de pelo menos 8 dígitos
    terá como AWB os 8 dígitos imediatamente após 577.

    Também aceita AWB pura de exatamente 8 dígitos.
    """
    if not text:
        return []

    found = set()

    # Código completo com prefixo 577 e qualquer sufixo depois da AWB.
    for match in re.findall(r"(?<!\d)577(\d{8})\d*(?!\d)", text):
        found.add(match)

    # AWB pura digitada diretamente.
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
    route_today = bool(row.get("TEVE_ROTA_HOJE", False))
    returned = row.get("AWB") in returns_set

    # Pendência ativa da Torre prevalece.
    if tower_event in {"PENDENCIA", "PENDENCIA_CORP"}:
        return "PENDÊNCIA TORRE", "TRATAR PENDÊNCIA", "TORRE", "ALTA"

    # FINALIZADO significa somente que saiu da Torre.
    # A classificação atual depende do status operacional no CDSP2.
    if tower_event == "FINALIZADO":
        if status_system == "ENTREGUE":
            return "ENTREGUE", "SEM AÇÃO", "CONCLUÍDO", "BAIXA"

        if status_system == "PENDENTE ENTREGA":
            if route_today:
                if route_status == "INSUCESSO":
                    return "INSUCESSO DO DIA", "AGUARDAR RETORNO", "LAST MILE", "MÉDIA"
                return "REENTREGA - ROTA DO DIA", "ACOMPANHAR ROTA", "LAST MILE", "MÉDIA"

            # Finalizado na Torre + ainda Pendente Entrega = reentrega.
            return "REENTREGA AGUARDANDO ROTA", "PROGRAMAR/ACOMPANHAR NOVA TENTATIVA", "LAST MILE", "ALTA"

        if status_system == "BAIXADO":
            return "BAIXADO - VALIDAR FLUXO", "VALIDAR MOTIVO/DESTINO", "TORRE/OPERAÇÃO", "MÉDIA"

        if status_system == "MISSING CARGO":
            return "MISSING CARGO", "TRATAR OCORRÊNCIA", "TORRE/OPERAÇÃO", "CRÍTICA"

        if status_system == "DISCREPANCIA CRIADA":
            return "DISCREPÂNCIA CRIADA", "ACOMPANHAR DISCREPÂNCIA", "TORRE/OPERAÇÃO", "ALTA"

        return "FINALIZADO NA TORRE - OUTRO FLUXO", "ACOMPANHAR STATUS OPERACIONAL", "MONITORAMENTO", "BAIXA"

    # Cargas sem pendência ativa na Torre.
    if status_system == "ENTREGUE":
        return "ENTREGUE", "SEM AÇÃO", "CONCLUÍDO", "BAIXA"

    if route_today:
        if route_status == "INSUCESSO":
            return "INSUCESSO DO DIA", "AGUARDAR RETORNO", "LAST MILE", "MÉDIA"
        return "ROTA DO DIA", "ACOMPANHAR ROTA", "LAST MILE", "BAIXA"

    # Retorno físico é dimensão independente, mas pode ser a ação principal
    # quando não existe pendência ativa da Torre.
    if returned:
        return "RETORNO CONFIRMADO", "VALIDAR DIRECIONAMENTO", "EXPEDIÇÃO/TORRE", "ALTA"

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

    if (
        sla is not None
        and pd.notna(sla)
        and sla <= today
        and status_system == "PENDENTE ENTREGA"
    ):
        return "PENDENTE DE ENTREGA REAL", "ATUAR NA EXPEDIÇÃO", "LAST MILE", "ALTA"

    if status_system == "BAIXADO":
        return "BAIXADO - VALIDAR FLUXO", "VALIDAR MOTIVO/DESTINO", "TORRE/OPERAÇÃO", "MÉDIA"

    if status_system == "MISSING CARGO":
        return "MISSING CARGO", "TRATAR OCORRÊNCIA", "TORRE/OPERAÇÃO", "CRÍTICA"

    if status_system == "DISCREPANCIA CRIADA":
        return "DISCREPÂNCIA CRIADA", "ACOMPANHAR DISCREPÂNCIA", "TORRE/OPERAÇÃO", "ALTA"

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
st.caption("V0.8.13 — EDI cruzado com First Mile")

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


    st.divider()
    st.subheader("First Mile")

    file_sao12 = st.file_uploader(
        "4. Emissões SAO12",
        type=["xlsx", "xls"],
        key="fm_sao12",
        help="Será filtrado automaticamente para Riachuelo, Neodent, Della Via, Stone, Tania Bulhões e ATS."
    )
    file_tres1 = st.file_uploader(
        "5. Emissões TRES1",
        type=["xlsx", "xls"],
        key="fm_tres1",
    )
    files_edi = st.file_uploader(
        "6. Notas Integradas (EDI) — múltiplos arquivos",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="fm_edi",
        help="Selecione todos os relatórios EDI dos clientes de uma só vez."
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





# =========================
# FIRST MILE — V0.8
# =========================
if file_sao12 or file_tres1 or files_edi:
    st.divider()
    st.header("First Mile")

    fm_frames = []
    fm_errors = []

    if file_sao12:
        try:
            fm_frames.append(read_first_mile_awbstatus(file_sao12.getvalue(), "SAO12"))
        except Exception as exc:
            fm_errors.append(f"SAO12: {exc}")

    if file_tres1:
        try:
            fm_frames.append(read_first_mile_awbstatus(file_tres1.getvalue(), "TRES1"))
        except Exception as exc:
            fm_errors.append(f"TRES1: {exc}")

    first_mile = (
        pd.concat(fm_frames, ignore_index=True, sort=False)
        if fm_frames else pd.DataFrame()
    )

    if not first_mile.empty:
        first_mile["GRUPO_FIRST_MILE"] = first_mile["STATUS_SISTEMA"].apply(first_mile_status_group)

        base_filter = st.radio(
            "Visão First Mile",
            ["CONSOLIDADO", "SAO12", "TRES1"],
            horizontal=True,
        )
        fm_view = (
            first_mile
            if base_filter == "CONSOLIDADO"
            else first_mile[first_mile["BASE_EMISSORA"] == base_filter]
        )

        fm_counts = fm_view["GRUPO_FIRST_MILE"].value_counts()

        fm1, fm2, fm3, fm4, fm5 = st.columns(5)
        fm1.metric("Pendente de Embarque", int(fm_counts.get("PENDENTE DE EMBARQUE", 0)))
        fm2.metric("Pendente de Desembarque", int(fm_counts.get("PENDENTE DE DESEMBARQUE", 0)))
        fm3.metric("Missing", int(fm_counts.get("MISSING", 0)))
        fm4.metric("Discrepância", int(fm_counts.get("DISCREPÂNCIA", 0)))
        fm5.metric("Baixado", int(fm_counts.get("BAIXADO", 0)))

        if base_filter in {"CONSOLIDADO", "SAO12"}:
            sao12_view = fm_view[fm_view["BASE_EMISSORA"] == "SAO12"]
            if not sao12_view.empty:
                st.subheader("Clientes SAO12 monitorados")
                # Matriz operacional por cliente e status.
                client_matrix = (
                    sao12_view
                    .pivot_table(
                        index="CLIENTE_PADRONIZADO",
                        columns="GRUPO_FIRST_MILE",
                        values="AWB",
                        aggfunc="nunique",
                        fill_value=0,
                    )
                    .reset_index()
                    .rename(columns={"CLIENTE_PADRONIZADO": "CLIENTE"})
                )

                expected_cols = [
                    "PENDENTE DE EMBARQUE",
                    "PENDENTE DE DESEMBARQUE",
                    "MISSING",
                    "DISCREPÂNCIA",
                    "BAIXADO",
                    "OUTROS",
                ]
                for col in expected_cols:
                    if col not in client_matrix.columns:
                        client_matrix[col] = 0

                client_matrix["TOTAL"] = client_matrix[expected_cols].sum(axis=1)

                client_matrix = client_matrix[
                    [
                        "CLIENTE",
                        "PENDENTE DE EMBARQUE",
                        "PENDENTE DE DESEMBARQUE",
                        "MISSING",
                        "DISCREPÂNCIA",
                        "BAIXADO",
                        "OUTROS",
                        "TOTAL",
                    ]
                ].sort_values("TOTAL", ascending=False)

                st.dataframe(
                    client_matrix,
                    use_container_width=True,
                    hide_index=True,
                )

        st.subheader("Onde estão as pendências do First Mile")

        # Pendente de Embarque: visão por trecho do voo.
        pend_emb = fm_view[
            fm_view["GRUPO_FIRST_MILE"] == "PENDENTE DE EMBARQUE"
        ].copy()

        if not pend_emb.empty:
            pend_emb["TRECHO"] = (
                pend_emb.get("FltOrigin", "").fillna("").astype(str).str.strip()
                + " → "
                + pend_emb.get("FltDestination", "").fillna("").astype(str).str.strip()
            )
            trecho_rank = (
                pend_emb.groupby("TRECHO")["AWB"]
                .nunique()
                .reset_index(name="AWBS")
                .sort_values("AWBS", ascending=False)
            )

            st.markdown("**Pendente de Embarque — por trecho**")
            st.dataframe(
                trecho_rank,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma carga pendente de embarque na visão selecionada.")

        # Pendente de Desembarque: visão pelo destino do voo.
        pend_des = fm_view[
            fm_view["GRUPO_FIRST_MILE"] == "PENDENTE DE DESEMBARQUE"
        ].copy()

        if not pend_des.empty:
            destino_rank = (
                pend_des.groupby("FltDestination")["AWB"]
                .nunique()
                .reset_index(name="AWBS")
                .sort_values("AWBS", ascending=False)
            )

            st.markdown("**Pendente de Desembarque — por destino do voo**")
            st.dataframe(
                destino_rank,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma carga pendente de desembarque na visão selecionada.")

        fm_detail_option = st.selectbox(
            "Detalhar First Mile",
            ["TODOS"] + [
                "PENDENTE DE EMBARQUE",
                "PENDENTE DE DESEMBARQUE",
                "MISSING",
                "DISCREPÂNCIA",
                "BAIXADO",
                "OUTROS",
            ],
        )
        fm_detail = (
            fm_view
            if fm_detail_option == "TODOS"
            else fm_view[fm_view["GRUPO_FIRST_MILE"] == fm_detail_option]
        )
        fm_cols = [
            "BASE_EMISSORA", "CLIENTE_PADRONIZADO", "AWB",
            "STATUS_SISTEMA", "SLA_DATA", "OriginCode",
            "DestinationCode", "OPSStation", "FltNo", "FltDt",
            "FltOrigin", "FltDestination", "BillTo",
        ]
        fm_cols = [c for c in fm_cols if c in fm_detail.columns]
        st.dataframe(
            safe_dataframe_for_streamlit(fm_detail[fm_cols]),
            use_container_width=True,
            hide_index=True
        )

    for err in fm_errors:
        st.warning(err)

    if files_edi:
        edi_payload = tuple((f.name, f.getvalue()) for f in files_edi)
        edi_base, edi_audit = read_edi_files(edi_payload)

        st.subheader("Notas Integradas (EDI)")
        e1, e2, e3 = st.columns(3)
        e1.metric("Arquivos enviados", len(files_edi))
        e2.metric(
            "Arquivos processados",
            int((edi_audit["STATUS"] == "OK").sum()) if not edi_audit.empty else 0
        )
        e3.metric("Registros consolidados", len(edi_base))

        st.dataframe(
            safe_dataframe_for_streamlit(edi_audit),
            use_container_width=True,
            hide_index=True
        )

        if not edi_base.empty:
            edi_base = edi_base.copy()
            edi_base["CLIENTE_EDI"] = edi_base.apply(edi_client_name, axis=1)
            edi_base["STATUS_EDI_GERENCIAL"] = edi_base.apply(classify_edi_status, axis=1)
            edi_base = mark_edi_execution_from_first_mile(edi_base, first_mile)

            edi_counts = edi_base["STATUS_EDI_GERENCIAL"].value_counts()
            booking_total = int(
                edi_base["STATUS_EDI_GERENCIAL"].isin(
                    ["BOOKING REAL", "AGUARDANDO BOOKING"]
                ).sum()
            )

            st.markdown("### Booking e execução EDI")
            b1, b2, b3, b4, b5 = st.columns(5)
            b1.metric("Booking aguardando execução", int(edi_counts.get("BOOKING REAL", 0)))
            b2.metric("Ainda sem Booking", int(edi_counts.get("AGUARDANDO BOOKING", 0)))
            b3.metric("Já avançou no First Mile", int(edi_counts.get("JÁ AVANÇOU NO FIRST MILE", 0)))
            b4.metric("Booking já executado", int(edi_counts.get("BOOKING JÁ EXECUTADO", 0)))
            b5.metric(
                "Pendência EDI total",
                int(edi_counts.get("BOOKING REAL", 0)) + int(edi_counts.get("AGUARDANDO BOOKING", 0))
            )

            anuladas_total = int(edi_counts.get("AWB ANULADA", 0))
            if anuladas_total:
                st.caption(
                    f"{anuladas_total} AWB(s) anulada(s) identificada(s) e retirada(s) da pendência operacional."
                )

            st.caption(
                "Leitura operacional: Booking aguardando execução = booking confirmado, mas ainda sem emissão/CTe, embarque ou entrega. "
                "Ainda sem Booking = integração recebida, porém o processo ainda não chegou ao booking. "
                "Se a AWB já aparecer em SAO12/TRES1, ela sai da pendência EDI e passa a ser tratada no First Mile."
            )

            # Diagnóstico das etapas do EDI para validar qual campo representa avanço real.
            booking_occ_mask = edi_base["UltimaOcorrencia"].map(normalize_text).apply(
                lambda x: ("BOOKING" in x) or ("BOOKED" in x) or x.startswith("BKD")
            )
            edi_booking_diag = edi_base[booking_occ_mask].copy()

            if not edi_booking_diag.empty:
                def field_filled(series):
                    return (
                        series.notna()
                        & series.astype(str).str.strip().str.upper().ne("")
                        & series.astype(str).str.strip().str.upper().ne("NAN")
                        & series.astype(str).str.strip().str.upper().ne("NONE")
                        & series.astype(str).str.strip().str.upper().ne("NAT")
                    )

                diag_rows = []
                diag_fields = [
                    "Nº AWB",
                    "Recebimento",
                    "Integracao",
                    "EmissaoCTe",
                    "CTeGerado",
                    "EmbarqueVoo",
                    "EntregaCarga",
                ]

                for field in diag_fields:
                    if field in edi_booking_diag.columns:
                        filled_count = int(field_filled(edi_booking_diag[field]).sum())
                        diag_rows.append({
                            "CAMPO": field,
                            "PREENCHIDOS": filled_count,
                            "VAZIOS": int(len(edi_booking_diag) - filled_count),
                            "% PREENCHIDO": round(
                                (filled_count / len(edi_booking_diag)) * 100, 1
                            ) if len(edi_booking_diag) else 0,
                        })

                st.markdown("### Validação técnica do Booking")
                st.caption(
                    "Visão técnica de apoio. Não é um indicador operacional principal."
                )
                st.dataframe(
                    pd.DataFrame(diag_rows),
                    use_container_width=True,
                    hide_index=True,
                )

                with st.expander("Ver amostra dos registros de Booking"):
                    sample_cols = [
                        "CLIENTE_EDI",
                        "Pedido",
                        "Numero",
                        "Nº AWB",
                        "Recebimento",
                        "Integracao",
                        "EmissaoCTe",
                        "CTeGerado",
                        "EmbarqueVoo",
                        "EntregaCarga",
                        "UltimaOcorrencia",
                        "ARQUIVO_EDI",
                    ]
                    sample_cols = [
                        c for c in sample_cols if c in edi_booking_diag.columns
                    ]
                    st.dataframe(
                        safe_dataframe_for_streamlit(
                            edi_booking_diag[sample_cols].head(100)
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            # Diagnóstico específico da etapa anterior ao Booking.
            nao_executado_df = edi_base[
                edi_base["STATUS_EDI_GERENCIAL"] == "AGUARDANDO BOOKING"
            ].copy()

            if not nao_executado_df.empty:
                st.markdown("### Aguardando Booking — onde o processo parou")
                st.caption(
                    "Cargas recebidas no EDI que ainda não chegaram ao Booking. "
                    "AWBs anuladas ficam separadas e não entram na pendência operacional."
                )

                nao_executado_df["OCORRENCIA_ATUAL"] = (
                    nao_executado_df["UltimaOcorrencia"]
                    .fillna("SEM OCORRÊNCIA")
                    .astype(str)
                    .str.strip()
                    .replace("", "SEM OCORRÊNCIA")
                )

                occurrence_summary = (
                    nao_executado_df
                    .groupby(["CLIENTE_EDI", "OCORRENCIA_ATUAL"], dropna=False)
                    .size()
                    .reset_index(name="REGISTROS")
                    .sort_values("REGISTROS", ascending=False)
                )

                st.dataframe(
                    safe_dataframe_for_streamlit(occurrence_summary),
                    use_container_width=True,
                    hide_index=True,
                )

                with st.expander("Ver registros ainda não executados"):
                    detail_cols = [
                        "CLIENTE_EDI",
                        "Pedido",
                        "Numero",
                        "Nº AWB",
                        "Origem",
                        "Destino",
                        "Recebimento",
                        "Integracao",
                        "EmissaoCTe",
                        "CTeGerado",
                        "UltimaOcorrencia",
                        "ARQUIVO_EDI",
                    ]
                    detail_cols = [
                        c for c in detail_cols if c in nao_executado_df.columns
                    ]
                    st.dataframe(
                        safe_dataframe_for_streamlit(
                            nao_executado_df[detail_cols]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            booking_matrix = (
                edi_base[
                    edi_base["STATUS_EDI_GERENCIAL"].isin(
                        ["BOOKING REAL", "AGUARDANDO BOOKING"]
                    )
                ]
                .pivot_table(
                    index="CLIENTE_EDI",
                    columns="STATUS_EDI_GERENCIAL",
                    values="ID",
                    aggfunc="count",
                    fill_value=0,
                )
                .reset_index()
            )

            for expected_col in ["BOOKING REAL", "AGUARDANDO BOOKING"]:
                if expected_col not in booking_matrix.columns:
                    booking_matrix[expected_col] = 0

            booking_matrix["TOTAL"] = (
                booking_matrix["BOOKING REAL"] + booking_matrix["AGUARDANDO BOOKING"]
            )
            booking_matrix = booking_matrix[
                ["CLIENTE_EDI", "BOOKING REAL", "AGUARDANDO BOOKING", "TOTAL"]
            ].sort_values("TOTAL", ascending=False)

            st.dataframe(
                booking_matrix,
                use_container_width=True,
                hide_index=True,
            )

            edi_detail_status = st.selectbox(
                "Detalhar situação EDI",
                ["BOOKING REAL", "AGUARDANDO BOOKING", "JÁ AVANÇOU NO FIRST MILE", "AWB ANULADA", "BOOKING JÁ EXECUTADO", "BOOKING + AGUARDANDO", "TODOS"],
            )

            if edi_detail_status == "BOOKING + AGUARDANDO":
                edi_detail = edi_base[
                    edi_base["STATUS_EDI_GERENCIAL"].isin(
                        ["BOOKING REAL", "AGUARDANDO BOOKING"]
                    )
                ]
            elif edi_detail_status == "TODOS":
                edi_detail = edi_base
            else:
                edi_detail = edi_base[
                    edi_base["STATUS_EDI_GERENCIAL"] == edi_detail_status
                ]

            edi_cols = [
                "CLIENTE_EDI", "STATUS_EDI_GERENCIAL", "Pedido", "Numero",
                "Nº AWB", "Origem", "Destino", "Recebimento", "Integracao",
                "EmissaoCTe", "CTeGerado", "UltimaOcorrencia",
                "EmbarqueVoo", "EntregaCarga", "ENCONTRADO_EMISSOES",
                "BASE_FIRST_MILE", "STATUS_FIRST_MILE_ATUAL", "ARQUIVO_EDI",
            ]
            edi_cols = [c for c in edi_cols if c in edi_detail.columns]

            st.dataframe(
                safe_dataframe_for_streamlit(edi_detail[edi_cols]),
                use_container_width=True,
                hide_index=True,
            )

            with st.expander("Ver base EDI consolidada completa"):
                st.dataframe(
                    safe_dataframe_for_streamlit(edi_base),
                    use_container_width=True,
                    hide_index=True
                )


# =========================
# CAMADA PREVENTIVA V0.7
# =========================
master["EM_TORRE_ATIVA"] = master["EVENTO_TORRE"].isin(["PENDENCIA", "PENDENCIA_CORP"])
# Regra operacional: rota efetiva exige entregador alocado.
# Status "Planejada" sem entregador continua sendo carga no piso.
entregador_col = next(
    (c for c in ["ULTIMO_ENTREGADOR", "ENTREGADOR", "Entregador", "Motorista"] if c in master.columns),
    None
)

if entregador_col:
    master["TEM_ENTREGADOR"] = (
        master[entregador_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
    )
else:
    master["TEM_ENTREGADOR"] = False

master["TEM_ROTA_HOJE"] = (
    master["TEVE_ROTA_HOJE"].fillna(False).astype(bool)
    & master["TEM_ENTREGADOR"]
)
sla_dates = pd.to_datetime(master["SLA_DATA"], errors="coerce").dt.date
status_norm = master["STATUS_SISTEMA"].map(normalize_text)

master["SLA_DO_DIA_NO_PISO"] = (
    (status_norm == "PENDENTE ENTREGA")
    & (sla_dates == reference_date)
    & (~master["TEM_ROTA_HOJE"])
    & (~master["EM_TORRE_ATIVA"])
)

master["SLA_VENCIDO_SEM_ROTA"] = (
    (status_norm == "PENDENTE ENTREGA")
    & (sla_dates < reference_date)
    & (~master["TEM_ROTA_HOJE"])
    & (~master["EM_TORRE_ATIVA"])
)

# Quantidade de tentativas já vem calculada do Eu Entrego.
if "QT_TENTATIVAS_INSUCESSO" not in master.columns:
    master["QT_TENTATIVAS_INSUCESSO"] = 0
master["QT_TENTATIVAS_INSUCESSO"] = (
    master["QT_TENTATIVAS_INSUCESSO"].fillna(0).astype(int)
)

master["SEGUNDA_TENTATIVA_RISCO"] = (
    (status_norm == "PENDENTE ENTREGA")
    & (master["QT_TENTATIVAS_INSUCESSO"] == 2)
    & (~master["EM_TORRE_ATIVA"])
)

master["TERCEIRA_TENTATIVA_RISCO_ALTO"] = (
    (status_norm == "PENDENTE ENTREGA")
    & (master["QT_TENTATIVAS_INSUCESSO"] >= 3)
)

master["TERCEIRA_TENTATIVA_FALHA_PROCESSO"] = (
    master["TERCEIRA_TENTATIVA_RISCO_ALTO"]
    & (~master["EM_TORRE_ATIVA"])
)

st.divider()
st.subheader("Radar preventivo — Last Mile")

p1, p2, p3, p4 = st.columns(4)
p1.metric("SLA do dia no piso", int(master["SLA_DO_DIA_NO_PISO"].sum()))
p2.metric("SLA vencido sem rota", int(master["SLA_VENCIDO_SEM_ROTA"].sum()))
p3.metric("2ª tentativa — risco", int(master["SEGUNDA_TENTATIVA_RISCO"].sum()))
p4.metric("3ª tentativa — risco alto", int(master["TERCEIRA_TENTATIVA_RISCO_ALTO"].sum()))

f1, f2 = st.columns(2)
f1.metric(
    "3ª tentativa sem Pendência — falha de processo",
    int(master["TERCEIRA_TENTATIVA_FALHA_PROCESSO"].sum())
)
f2.metric(
    "3ª tentativa já direcionada à Torre",
    int(
        (
            master["TERCEIRA_TENTATIVA_RISCO_ALTO"]
            & master["EM_TORRE_ATIVA"]
        ).sum()
    )
)

st.caption(
    "SLA do dia no piso = Pendente Entrega, SLA vencendo na data de análise, "
    "sem entregador alocado no dia e sem pendência ativa na Torre. "
    "3ª tentativa concluída sem sucesso e ainda fora da Torre = cobrar time operacional para direcionar a carga."
)

alerta = st.selectbox(
    "Detalhar alerta preventivo",
    [
        "SLA do dia no piso",
        "SLA vencido sem rota",
        "2ª tentativa — risco",
        "3ª tentativa — risco alto",
        "3ª tentativa sem Pendência — falha de processo",
    ]
)
alert_map = {
    "SLA do dia no piso": "SLA_DO_DIA_NO_PISO",
    "SLA vencido sem rota": "SLA_VENCIDO_SEM_ROTA",
    "2ª tentativa — risco": "SEGUNDA_TENTATIVA_RISCO",
    "3ª tentativa — risco alto": "TERCEIRA_TENTATIVA_RISCO_ALTO",
    "3ª tentativa sem Pendência — falha de processo": "TERCEIRA_TENTATIVA_FALHA_PROCESSO",
}
det = master[master[alert_map[alerta]]].copy()
cols = [
    "AWB", "STATUS_SISTEMA", "SLA_DATA", "ULTIMA_ROTA",
    "STATUS_ULTIMA_ROTA", "ULTIMO_ENTREGADOR", "TEM_ENTREGADOR", "QT_TENTATIVAS_INSUCESSO",
    "EVENTO_TORRE", "BillTo", "OriginCode"
]
cols = [c for c in cols if c in det.columns]
st.dataframe(det[cols], use_container_width=True, hide_index=True)

# Carga parcial permanece como indicador planejado até validarmos
# quais colunas do AWBStatus Piece Level representam total e peças processadas.

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
