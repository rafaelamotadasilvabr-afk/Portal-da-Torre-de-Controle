
import io
import re
import unicodedata
from datetime import date

import numpy as np
import pandas as pd
import requests
from io import BytesIO
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


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
def read_torre_from_dataframe(source_df):
    """
    Lê a planilha viva de Pendências da Torre vinda do Google Sheets.
    Retorna a mesma estrutura esperada pelo motor atual: latest, history.
    """
    if source_df is None or source_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = clean_columns(source_df.copy())

    awb_col = find_column(df, ["AWB", "awb"])
    if not awb_col:
        return pd.DataFrame(), pd.DataFrame()

    df["AWB"] = df[awb_col].apply(normalize_awb)

    treatment_col = find_column(df, ["DATA DA TRATATIVA"])
    status_col = find_column(df, ["STATUS", " STATUS"])
    origin_col = find_column(df, ["ORIGEM", " ORIGEM ", "BASE DE ORIGEM"])
    reason_col = find_column(df, ["OBS", "OBSERVAÇÃO", "MOTIVO DA PENDENCIA"])
    email_col = find_column(df, ["STATUS EMAIL"])

    history = pd.DataFrame({
        "AWB": df["AWB"],
        "EVENTO_TORRE": "PENDENCIA",
        "DATA_EVENTO_TORRE": (
            parse_date(df[treatment_col])
            if treatment_col else pd.Series(pd.NaT, index=df.index)
        ),
        "STATUS_TRATATIVA": df[status_col] if status_col else "",
        "ORIGEM_TORRE": df[origin_col] if origin_col else "",
        "MOTIVO_PENDENCIA": df[reason_col] if reason_col else "",
        "ABA_ORIGEM": "PENDENCIAS",
    })

    if email_col:
        history["STATUS_EMAIL"] = df[email_col]

    history = history[history["AWB"].notna()].copy()

    if history.empty:
        return pd.DataFrame(), history

    latest = (
        history.sort_values(["AWB", "DATA_EVENTO_TORRE"])
               .drop_duplicates("AWB", keep="last")
               .copy()
    )

    return latest, history


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


def build_edi_manager_views(first_mile_df, edi_base_df, reference_date):
    """
    Monta a visão EDI do dashboard gerencial.

    No gerente, chamaremos First Mile de EDI.
    """
    detail_rows = []
    ref_ts = pd.to_datetime(reference_date, errors="coerce")
    ref_date = ref_ts.date() if pd.notna(ref_ts) else pd.Timestamp.today().date()

    def pick(row, cols):
        for col in cols:
            if col in row.index:
                val = row.get(col)
                if pd.notna(val) and str(val).strip() not in {"", "nan", "None", "NaT"}:
                    return str(val).strip()
        return ""

    if first_mile_df is not None and not first_mile_df.empty:
        fm = first_mile_df.copy()

        if "GRUPO_FIRST_MILE" not in fm.columns and "STATUS_SISTEMA" in fm.columns:
            fm["GRUPO_FIRST_MILE"] = fm["STATUS_SISTEMA"].apply(first_mile_status_group)

        for _, row in fm.iterrows():
            base = str(row.get("BASE_EMISSORA", "")).strip().upper()
            if base not in {"SAO12", "TRES1"}:
                continue

            grupo = str(row.get("GRUPO_FIRST_MILE", "")).strip().upper()
            status_norm = normalize_text(row.get("STATUS_SISTEMA", ""))

            cliente_raw = str(row.get("CLIENTE_PADRONIZADO", row.get("BillTo", ""))).strip()
            cliente_norm = normalize_text(cliente_raw)

            # EDI gerencial — escopo de clientes:
            # SAO12: Riachuelo, Della Via, Stone, Tania Bulhões e Inbrands.
            # TRES1: Três Corações.
            clientes_sao12 = [
                "RIACHUELO",
                "DELLA VIA",
                "STONE",
                "TANIA BULHOES",
                "TANIA BULHÕES",
                "INBRANDS",
                "IMBRANDS",
                "ATS",
                "NEODENT",
                "JJC",
            ]

            if base == "SAO12" and not any(c in cliente_norm for c in clientes_sao12):
                continue

            if base == "TRES1" and not (
                "TRES" in cliente_norm
                or "TRES CORACOES" in cliente_norm
                or "TRÊS CORAÇÕES" in cliente_raw.upper()
            ):
                continue

            indicador = None
            if grupo == "PENDENTE DE EMBARQUE":
                indicador = "PENDENTE DE EMBARQUE"
            elif grupo == "PENDENTE DE DESEMBARQUE":
                indicador = "PENDENTE DE DESEMBARQUE"
            elif grupo == "MISSING":
                indicador = "MISSING"
            elif grupo == "DISCREPÂNCIA":
                indicador = "DISCREPÂNCIA"
            elif "PENDENTE ENTREGA" in status_norm:
                indicador = "ENTREGA NO DESTINO PELO SLA"

            if indicador is None:
                continue

            sla = pd.to_datetime(row.get("SLA_DATA"), errors="coerce")
            if pd.notna(sla):
                sla_date = sla.date()
                dias_sla = (ref_date - sla_date).days
                if dias_sla > 0:
                    status_sla = "SLA VENCIDO"
                elif dias_sla == 0:
                    status_sla = "SLA HOJE"
                else:
                    status_sla = "SLA FUTURO"
            else:
                sla_date = ""
                dias_sla = ""
                status_sla = "SEM SLA"

            # No EDI gerencial, pendente de embarque/desembarque e entrega no destino
            # só entram até o SLA do dia. SLA futuro não aparece para o gerente.
            if indicador in {
                "PENDENTE DE EMBARQUE",
                "PENDENTE DE DESEMBARQUE",
                "ENTREGA NO DESTINO PELO SLA",
            } and status_sla not in {"SLA VENCIDO", "SLA HOJE"}:
                continue

            origem_operacional = pick(row, ["OriginCode", "FltOrigin"])
            destino_operacional = pick(row, ["DestinationCode", "FltDestination", "OPSStation"])

            # Regra solicitada:
            # EDI pendente de embarque só pode entrar quando o local/origem do embarque
            # for SAO12 ou TRES1. Exemplo: pendente embarque em VCP não entra.
            if indicador == "PENDENTE DE EMBARQUE":
                origem_norm = normalize_text(origem_operacional)
                if origem_norm not in {"SAO12", "TRES1"}:
                    continue
                base = origem_norm

            trecho = (
                origem_operacional
                + " → "
                + destino_operacional
            ).strip(" →")

            detail_rows.append({
                "FONTE": "FIRST MILE",
                "BASE": base,
                "INDICADOR": indicador,
                "CLIENTE": cliente_raw,
                "AWB": row.get("AWB", ""),
                "STATUS": row.get("STATUS_SISTEMA", ""),
                "SLA": sla_date,
                "STATUS_SLA": status_sla,
                "DIAS_SLA": dias_sla,
                "ORIGEM": origem_operacional,
                "DESTINO": destino_operacional,
                "TRECHO": trecho,
                "VOO": row.get("FltNo", ""),
                "DATA_VOO": row.get("FltDt", ""),
                "BILL_TO": row.get("BillTo", ""),
            })

    if edi_base_df is not None and not edi_base_df.empty and "STATUS_EDI_GERENCIAL" in edi_base_df.columns:
        pend = edi_base_df[
            edi_base_df["STATUS_EDI_GERENCIAL"].isin(["BOOKING REAL", "AGUARDANDO BOOKING"])
        ].copy()
        for _, row in pend.iterrows():
            detail_rows.append({
                "FONTE": "NOTAS INTEGRADAS EDI",
                "BASE": "",
                "INDICADOR": str(row.get("STATUS_EDI_GERENCIAL", "")),
                "CLIENTE": str(row.get("CLIENTE_EDI", "")),
                "AWB": row.get("Nº AWB", ""),
                "STATUS": row.get("UltimaOcorrencia", ""),
                "SLA": "",
                "STATUS_SLA": "",
                "DIAS_SLA": "",
                "ORIGEM": row.get("Origem", ""),
                "DESTINO": row.get("Destino", ""),
                "TRECHO": "",
                "VOO": "",
                "DATA_VOO": "",
                "BILL_TO": "",
            })

    detalhe = pd.DataFrame(detail_rows)

    if detalhe.empty:
        return (
            pd.DataFrame(columns=["BASE", "INDICADOR", "AWBS"]),
            pd.DataFrame(columns=[
                "FONTE", "BASE", "INDICADOR", "CLIENTE", "AWB", "STATUS",
                "SLA", "STATUS_SLA", "DIAS_SLA", "ORIGEM", "DESTINO",
                "TRECHO", "VOO", "DATA_VOO", "BILL_TO"
            ]),
        )

    detalhe["AWB"] = detalhe["AWB"].fillna("").astype(str).str.strip()
    detalhe["_CONTAGEM"] = detalhe["AWB"].where(
        detalhe["AWB"].ne(""),
        detalhe.index.astype(str)
    )

    resumo = (
        detalhe.groupby(["BASE", "INDICADOR"], dropna=False)["_CONTAGEM"]
        .nunique()
        .reset_index(name="AWBS")
        .sort_values(["BASE", "AWBS"], ascending=[True, False])
    )

    detalhe = detalhe.drop(columns=["_CONTAGEM"], errors="ignore")
    return resumo, detalhe


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
# GOOGLE SHEETS — BASES VIVAS
# =========================
DEFAULT_GOOGLE_SHEETS = {
    "Pendências da Torre": "https://docs.google.com/spreadsheets/d/1OesmRR8cIQpB7-NezunmKu46ugJrDA5ZPqrUgtZFJsw/edit?usp=sharing",
    "Acareação e Ressalva": "https://docs.google.com/spreadsheets/d/1qQ266DPLPEi_BG3cSgyFcXAV9gBK3N7waZrl-Ybx5kU/edit?usp=sharing",
    "Passível a Débito e Indenização": "https://docs.google.com/spreadsheets/d/19dRtnW3dsDcyOpRhEU0ifoPhGr8cXkxu6El1W5A-Xws/edit?gid=0#gid=0",
}

def extract_google_sheet_id(url):
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", str(url))
    return match.group(1) if match else None

@st.cache_data(ttl=300, show_spinner=False)
def read_public_google_sheet(url):
    sheet_id = extract_google_sheet_id(url)
    if not sheet_id:
        raise ValueError("Link do Google Sheets inválido.")
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    response = requests.get(csv_url, timeout=30)
    response.raise_for_status()
    return pd.read_csv(BytesIO(response.content))


@st.cache_data(ttl=300, show_spinner=False)
def read_public_google_workbook_bytes(url):
    """
    Baixa o Google Sheets completo em XLSX para preservar todas as abas.
    Necessário para Pendências da Torre, pois a Performance usa:
    PENDENCIAS, PENDENCIA CORP e FINALIZADAS.
    """
    sheet_id = extract_google_sheet_id(url)
    if not sheet_id:
        raise ValueError("Link do Google Sheets inválido.")

    xlsx_url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        "/export?format=xlsx"
    )
    response = requests.get(xlsx_url, timeout=60)
    response.raise_for_status()
    return response.content

def load_live_control_bases():
    st.sidebar.markdown("### Bases vivas — Google Sheets")
    st.sidebar.caption("Links preenchidos por padrão. Altere somente se a planilha mudar.")
    bases = {}
    for label, default_url in DEFAULT_GOOGLE_SHEETS.items():
        url = st.sidebar.text_input(label, value=default_url, key=f"gs_{label}")
        try:
            bases[label] = read_public_google_sheet(url) if url.strip() else pd.DataFrame()
            st.sidebar.success(f"{label}: conectado")
        except Exception:
            bases[label] = pd.DataFrame()
            st.sidebar.warning(f"{label}: falha na atualização")
    return bases



def add_live_control_flags(master_df, pendencias_df, acareacao_df, indenizacao_df):
    if master_df is None or master_df.empty:
        return master_df

    result = master_df.copy()
    result["_AWB_CONTROLE"] = result["AWB"].astype(str).map(normalize_awb)

    def keyset(df, names):
        if df is None or df.empty:
            return set()
        col = find_column(df, names)
        if not col:
            return set()
        return {
            k for k in df[col].apply(normalize_awb).dropna().astype(str)
            if k
        }

    pend = keyset(pendencias_df, ["awb", "AWB"])
    acar = keyset(acareacao_df, ["awb", "AWB"])
    inden = keyset(indenizacao_df, ["AWB", "awb"])

    result["NA_PENDENCIA_TORRE_LINK"] = result["_AWB_CONTROLE"].isin(pend)
    result["EM_ACAREACAO_RESSALVA"] = result["_AWB_CONTROLE"].isin(acar)
    result["EM_DEBITO_INDENIZACAO"] = result["_AWB_CONTROLE"].isin(inden)

    def tags(row):
        out = []
        if row["NA_PENDENCIA_TORRE_LINK"]:
            out.append("PENDÊNCIA TORRE")
        if row["EM_ACAREACAO_RESSALVA"]:
            out.append("ACAREAÇÃO / RESSALVA")
        if row["EM_DEBITO_INDENIZACAO"]:
            out.append("DÉBITO / INDENIZAÇÃO")
        return " | ".join(out)

    result["CONTROLE_ESPECIAL"] = result.apply(tags, axis=1)

    # Detalhes da Acareação/Ressalva para o dashboard gerencial.
    # Mantém campos vazios quando a planilha não trouxer a coluna.
    result["ACAREACAO_ENTREGADOR"] = ""
    result["ACAREACAO_VALOR"] = ""
    result["ACAREACAO_STATUS"] = ""
    result["ACAREACAO_TIPO"] = ""
    result["ACAREACAO_OBSERVACAO"] = ""

    if acareacao_df is not None and not acareacao_df.empty:
        acar_df = clean_columns(acareacao_df.copy())
        awb_col = find_column(acar_df, ["AWB", "awb"])
        if awb_col:
            acar_df["_AWB_CONTROLE"] = acar_df[awb_col].apply(normalize_awb)
            acar_df = acar_df[acar_df["_AWB_CONTROLE"].notna()].copy()

            ent_col = find_column(acar_df, ["ENTREGADOR", "MOTORISTA", "NOME ENTREGADOR"])
            val_col = find_column(acar_df, ["VALOR DA CARGA", "VALOR", "VALOR CARGA"])
            status_col = find_column(acar_df, ["STATUS", "SITUAÇÃO", "SITUACAO"])
            tipo_col = find_column(acar_df, ["TIPO DE ACAREAÇÃO", "TIPO DE ACAREACAO", "TIPO"])
            obs_col = find_column(acar_df, ["OBSERVAÇÃO", "OBSERVACAO", "OBS"])

            # Mantém a linha mais recente por AWB quando houver data de solicitação/prazo.
            dt_col = find_column(acar_df, ["DATA DA SOLICITAÇÃO", "DATA DA SOLICITACAO", "PRAZO DE DEVOLUTIVA"])
            if dt_col:
                acar_df["_DT_ACAR"] = parse_date(acar_df[dt_col])
                acar_df = acar_df.sort_values(["_AWB_CONTROLE", "_DT_ACAR"]).drop_duplicates("_AWB_CONTROLE", keep="last")
            else:
                acar_df = acar_df.drop_duplicates("_AWB_CONTROLE", keep="last")

            def map_by(col):
                if not col:
                    return {}
                return dict(zip(acar_df["_AWB_CONTROLE"], acar_df[col].fillna("").astype(str)))

            ent_map = map_by(ent_col)
            val_map = map_by(val_col)
            status_map = map_by(status_col)
            tipo_map = map_by(tipo_col)
            obs_map = map_by(obs_col)

            result["ACAREACAO_ENTREGADOR"] = result["_AWB_CONTROLE"].map(ent_map).fillna("")
            result["ACAREACAO_VALOR"] = result["_AWB_CONTROLE"].map(val_map).fillna("")
            result["ACAREACAO_STATUS"] = result["_AWB_CONTROLE"].map(status_map).fillna("")
            result["ACAREACAO_TIPO"] = result["_AWB_CONTROLE"].map(tipo_map).fillna("")
            result["ACAREACAO_OBSERVACAO"] = result["_AWB_CONTROLE"].map(obs_map).fillna("")

    return result


def build_unique_action_queue(master_df, edi_loaded=False, analysis_date=None):
    """
    Fila operacional única do Last Mile.
    Usa diretamente as colunas reais do master e mantém uma linha por AWB.
    """
    if master_df is None or master_df.empty:
        return pd.DataFrame()

    df = master_df.copy()
    analysis_ts = pd.Timestamp(analysis_date or date.today()).normalize()

    def value(row, col):
        if col not in df.columns:
            return ""
        v = row.get(col, "")
        return "" if pd.isna(v) else str(v).strip()

    def first_non_empty(row, columns):
        for col in columns:
            if col in df.columns:
                v = row.get(col)
                if pd.notna(v) and str(v).strip() not in {"", "nan", "None"}:
                    return str(v).strip()
        return ""

    # Campos operacionais reais.
    df["_FILA_CLIENTE"] = df.apply(
        lambda r: first_non_empty(
            r, ["BillTo", "CLIENTE", "CLIENTE_NOME", "CLIENTE_EDI"]
        ),
        axis=1,
    )

    def infer_etapa(row):
        controle = normalize_text(value(row, "CONTROLE_ESPECIAL"))
        if "ACAREACAO" in controle or "INDENIZA" in controle or "DEBITO" in controle:
            return "LAST MILE + TRATATIVA ESPECIAL"
        return "LAST MILE"

    df["_FILA_ETAPA"] = df.apply(infer_etapa, axis=1)

    def infer_local_responsavel(row):
        # Quando existe uma ação já definida, ela é o melhor direcionador.
        resp = first_non_empty(row, ["RESPONSAVEL_ACAO"])
        origem_torre = first_non_empty(row, ["ORIGEM_TORRE"])
        ops = first_non_empty(row, ["OPSStation"])
        destino = first_non_empty(row, ["DestinationCode", "FltDestination"])
        entregador = first_non_empty(row, ["ULTIMO_ENTREGADOR"])

        if origem_torre:
            return origem_torre
        if resp:
            return resp
        if entregador:
            return entregador
        if ops:
            return ops
        return destino

    df["_FILA_LOCAL_RESP"] = df.apply(infer_local_responsavel, axis=1)

    # SLA e atraso calculados com a data de análise escolhida no portal.
    if "SLA_DATA" in df.columns:
        sla_dt = pd.to_datetime(df["SLA_DATA"], errors="coerce")
        df["_FILA_DIAS_ATRASO"] = (analysis_ts - sla_dt.dt.normalize()).dt.days
        df["_FILA_DIAS_ATRASO"] = df["_FILA_DIAS_ATRASO"].where(
            df["_FILA_DIAS_ATRASO"] > 0, 0
        )
    else:
        df["_FILA_DIAS_ATRASO"] = 0

    def classify(row):
        situacao = normalize_text(value(row, "SITUACAO_GERENCIAL"))
        controle = normalize_text(value(row, "CONTROLE_ESPECIAL"))
        atraso = pd.to_numeric(row.get("_FILA_DIAS_ATRASO"), errors="coerce")
        atraso = 0 if pd.isna(atraso) else float(atraso)

        tentativas = pd.to_numeric(row.get("QT_TENTATIVAS_INSUCESSO", 0), errors="coerce")
        tentativas = 0 if pd.isna(tentativas) else int(tentativas)

        if "MISSING" in situacao or "DISCREP" in situacao:
            return 1, "CRÍTICA", "MISSING / DISCREPÂNCIA", \
                "Localizar a carga e validar a divergência imediatamente"

        status_sistema = normalize_text(value(row, "STATUS_SISTEMA"))

        try:
            sla_row = pd.to_datetime(row.get("SLA_DATA"), errors="coerce")
            sla_row = sla_row.normalize() if pd.notna(sla_row) else pd.NaT
        except Exception:
            sla_row = pd.NaT

        teve_rota_hoje = str(row.get("TEVE_ROTA_HOJE", "")).strip().lower() in {
            "true", "1", "sim", "yes", "y", "verdadeiro"
        }

        em_torre_ativa = str(row.get("EM_TORRE_ATIVA", "")).strip().lower() in {
            "true", "1", "sim", "yes", "y", "verdadeiro"
        }

        # Last Mile: pendente de desembarque até o SLA do dia.
        # Inclui SLA vencido e SLA hoje; não inclui SLA futuro.
        if (
            status_sistema == "PENDENTE DESEMBARQUE"
            and pd.notna(sla_row)
            and sla_row <= analysis_ts
        ):
            prioridade_des = "CRÍTICA" if sla_row < analysis_ts else "ALTA"
            return 2, prioridade_des, "PENDENTE DE DESEMBARQUE", \
                "Cobrar desembarque da carga até o SLA do dia"

        # Mesma regra do Radar Preventivo — Last Mile:
        # Pendente Entrega + SLA na data de análise + nenhuma rota criada hoje + fora da Torre ativa.
        if (
            status_sistema == "PENDENTE ENTREGA"
            and pd.notna(sla_row)
            and sla_row == analysis_ts
            and not teve_rota_hoje
            and not em_torre_ativa
        ):
            return 3, "ALTA", "SLA DO DIA SEM ROTA", \
                "Criar rota no Eu Entrego ou justificar ausência de rota no dia do SLA"

        # Regra gerencial: 3 ou mais tentativas precisa aparecer no relatório do gerente.
        # Entra antes de PENDENTE DE ENTREGA para não ficar escondido no grupo genérico.
        if tentativas >= 3 and (
            "ENTREGA" in situacao
            or "PENDENTE" in situacao
            or "INSUCESSO" in situacao
            or "RETORNO" in situacao
        ):
            prioridade = "CRÍTICA" if atraso > 0 else "ALTA"
            return 4, prioridade, "3ª TENTATIVA DE ENTREGA", \
                "Validar direcionamento para a Torre e definir nova tratativa de entrega"

        if atraso > 0 and "ENTREGA" in situacao:
            return 5, "CRÍTICA", "ENTREGA EM ATRASO", \
                "Cobrar regularização da entrega e registrar a causa do atraso"

        if "PENDENTE ENTREGA" in situacao or "PENDENTE DE ENTREGA" in situacao:
            return 6, "ALTA", "PENDENTE DE ENTREGA", \
                "Validar SLA, última tentativa e próxima ação operacional"

        if "3A TENTATIVA" in situacao or "3ª TENTATIVA" in situacao:
            return 7, "ALTA", "3ª TENTATIVA DE ENTREGA", \
                "Validar direcionamento para a Torre após a terceira tentativa"

        if "ACAREACAO" in controle:
            return 8, "MÉDIA", "ACAREAÇÃO EM TRATATIVA", \
                "Acompanhar devolutiva e prazo da acareação"

        if "INDENIZA" in controle or "DEBITO" in controle:
            return 9, "MÉDIA", "PASSÍVEL DE INDENIZAÇÃO", \
                "Acompanhar o andamento do processo"

        if edi_loaded and ("BOOKING" in situacao or "EDI" in situacao):
            return 10, "MÉDIA", "BOOKING / EDI", \
                "Validar execução do booking"

        return 99, "MONITORAR", value(row, "SITUACAO_GERENCIAL") or "SEM AÇÃO", \
            "Monitorar evolução operacional"

    classified = pd.DataFrame(
        [classify(row) for _, row in df.iterrows()],
        index=df.index,
        columns=[
            "_FILA_ORDEM", "_FILA_PRIORIDADE",
            "_FILA_PROBLEMA", "_FILA_ACAO"
        ],
    )
    df = pd.concat([df, classified], axis=1)

    df["_AWB_FILA"] = df["AWB"].apply(normalize_awb)
    df = (
        df.sort_values(
            ["_FILA_ORDEM", "_FILA_DIAS_ATRASO"],
            ascending=[True, False]
        )
        .drop_duplicates("_AWB_FILA", keep="first")
        .copy()
    )

    queue = pd.DataFrame(index=df.index)
    queue["PRIORIDADE"] = df["_FILA_PRIORIDADE"]
    queue["AWB"] = df["AWB"]
    queue["CLIENTE"] = df["_FILA_CLIENTE"]
    queue["ETAPA ATUAL"] = df["_FILA_ETAPA"]
    queue["SITUAÇÃO"] = df["SITUACAO_GERENCIAL"] if "SITUACAO_GERENCIAL" in df.columns else ""
    queue["LOCALIZAÇÃO / RESPONSÁVEL"] = df["_FILA_LOCAL_RESP"]
    queue["SLA"] = df["SLA_DATA"] if "SLA_DATA" in df.columns else ""
    queue["DIAS EM ATRASO"] = df["_FILA_DIAS_ATRASO"]
    queue["TRATATIVA ESPECIAL"] = df["CONTROLE_ESPECIAL"] if "CONTROLE_ESPECIAL" in df.columns else ""
    queue["PROBLEMA"] = df["_FILA_PROBLEMA"]
    queue["PRÓXIMA AÇÃO"] = df["_FILA_ACAO"]

    # Colunas adicionais para o dashboard gerencial.
    # Elas permitem filtros, controle de motoristas, retornos em aberto e Pendência Corp.
    queue["DATA ANÁLISE"] = str(analysis_ts.date())
    queue["MOTORISTA / ENTREGADOR"] = df["ULTIMO_ENTREGADOR"] if "ULTIMO_ENTREGADOR" in df.columns else ""
    queue["STATUS ÚLTIMA ROTA"] = df["STATUS_ULTIMA_ROTA"] if "STATUS_ULTIMA_ROTA" in df.columns else ""
    queue["MOTIVO ÚLTIMA ROTA"] = df["MOTIVO_ULTIMA_ROTA"] if "MOTIVO_ULTIMA_ROTA" in df.columns else ""
    queue["ÚLTIMA ROTA"] = df["ULTIMA_ROTA"] if "ULTIMA_ROTA" in df.columns else ""
    queue["ÚLTIMA ALTERAÇÃO"] = df["ULTIMA_ALTERACAO"] if "ULTIMA_ALTERACAO" in df.columns else ""
    queue["QT TENTATIVAS"] = df["QT_TENTATIVAS_INSUCESSO"] if "QT_TENTATIVAS_INSUCESSO" in df.columns else 0
    queue["RETORNO CONFIRMADO"] = df["RETORNO_CONFIRMADO"] if "RETORNO_CONFIRMADO" in df.columns else False
    queue["EVENTO TORRE"] = df["EVENTO_TORRE"] if "EVENTO_TORRE" in df.columns else ""
    queue["ABA TORRE"] = df["ABA_ORIGEM"] if "ABA_ORIGEM" in df.columns else ""
    queue["STATUS TORRE"] = df["STATUS_TRATATIVA"] if "STATUS_TRATATIVA" in df.columns else ""
    queue["ORIGEM TORRE"] = df["ORIGEM_TORRE"] if "ORIGEM_TORRE" in df.columns else ""
    queue["MOTIVO PENDÊNCIA"] = df["MOTIVO_PENDENCIA"] if "MOTIVO_PENDENCIA" in df.columns else ""
    queue["DATA EVENTO TORRE"] = df["DATA_EVENTO_TORRE"] if "DATA_EVENTO_TORRE" in df.columns else ""

    # Dados de acareação para o dashboard gerencial.
    queue["ACAREACAO ENTREGADOR"] = df["ACAREACAO_ENTREGADOR"] if "ACAREACAO_ENTREGADOR" in df.columns else ""
    queue["ACAREACAO VALOR"] = df["ACAREACAO_VALOR"] if "ACAREACAO_VALOR" in df.columns else ""
    queue["ACAREACAO STATUS"] = df["ACAREACAO_STATUS"] if "ACAREACAO_STATUS" in df.columns else ""
    queue["ACAREACAO TIPO"] = df["ACAREACAO_TIPO"] if "ACAREACAO_TIPO" in df.columns else ""
    queue["ACAREACAO OBSERVACAO"] = df["ACAREACAO_OBSERVACAO"] if "ACAREACAO_OBSERVACAO" in df.columns else ""

    if "ULTIMA_ROTA" in df.columns:
        _ult_rota_dt = pd.to_datetime(df["ULTIMA_ROTA"], errors="coerce")
        queue["DIAS DESDE ÚLTIMA ROTA"] = (analysis_ts - _ult_rota_dt.dt.normalize()).dt.days.where(_ult_rota_dt.notna(), "")
    else:
        queue["DIAS DESDE ÚLTIMA ROTA"] = ""

    queue["_ORDEM_FILA"] = df["_FILA_ORDEM"]

    return (
        queue.sort_values(
            ["_ORDEM_FILA", "DIAS EM ATRASO"],
            ascending=[True, False],
            na_position="last",
        )
        .reset_index(drop=True)
    )


def _panel_find_col(df, candidates):
    if df is None or df.empty:
        return None
    normalized = {normalize_text(c): c for c in df.columns}
    for cand in candidates:
        key = normalize_text(cand)
        if key in normalized:
            return normalized[key]
    for cand in candidates:
        key = normalize_text(cand)
        for norm_col, original in normalized.items():
            if key in norm_col:
                return original
    return None

def _panel_money_to_num(series):
    if series is None:
        return pd.Series(dtype=float)
    s = series.astype(str).str.strip()
    s = s.str.replace("R$", "", regex=False).str.replace(" ", "", regex=False)
    mask = s.str.contains(",", regex=False)
    s.loc[mask] = (
        s.loc[mask]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(s, errors="coerce").fillna(0)

def _panel_brl(value):
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")



def build_manager_pack_bytes(
    summary_df,
    fila_df,
    top_problemas_df,
    top_bases_df,
    top_clientes_df,
    extra_sheets=None,
):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="RESUMO", index=False)
        fila_df.to_excel(writer, sheet_name="FILA", index=False)
        top_problemas_df.to_excel(writer, sheet_name="TOP_PROBLEMAS", index=False)
        top_bases_df.to_excel(writer, sheet_name="TOP_BASES", index=False)
        top_clientes_df.to_excel(writer, sheet_name="TOP_CLIENTES", index=False)

        for sheet_name, df in (extra_sheets or {}).items():
            safe_name = str(sheet_name)[:31]
            (df if df is not None else pd.DataFrame()).to_excel(
                writer,
                sheet_name=safe_name,
                index=False,
            )

    output.seek(0)
    return output.getvalue()


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



def _google_service_account_info():
    """
    Lê as credenciais da conta de serviço do Streamlit Secrets.
    Esperado:
    [gcp_service_account]
    type = "service_account"
    project_id = "..."
    private_key_id = "..."
    private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
    client_email = "..."
    client_id = "..."
    auth_uri = "https://accounts.google.com/o/oauth2/auth"
    token_uri = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
    client_x509_cert_url = "..."
    """
    try:
        return dict(st.secrets["gcp_service_account"])
    except Exception:
        return None


def _google_credentials():
    info = _google_service_account_info()
    if not info:
        return None

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    return Credentials.from_service_account_info(info, scopes=scopes)


def _google_sheet_client():
    creds = _google_credentials()
    if creds is None:
        return None
    return gspread.authorize(creds)


def _sanitize_sheet_df(df):
    if df is None:
        return pd.DataFrame()

    safe = df.copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            safe[col] = safe[col].apply(
                lambda x: (
                    x.isoformat()
                    if hasattr(x, "isoformat") and not isinstance(x, str)
                    else x
                )
            )

    return safe.fillna("").astype(str)


def _write_df_to_worksheet(spreadsheet, sheet_name, df):
    safe_df = _sanitize_sheet_df(df)

    try:
        ws = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=sheet_name,
            rows=max(len(safe_df) + 10, 100),
            cols=max(len(safe_df.columns) + 5, 20),
        )

    values = [list(safe_df.columns)] + safe_df.values.tolist()
    if not values:
        values = [["SEM_DADOS"]]

    required_rows = max(len(values) + 5, 100)
    required_cols = max(max((len(r) for r in values), default=1) + 2, 20)

    if ws.row_count < required_rows or ws.col_count < required_cols:
        ws.resize(
            rows=max(ws.row_count, required_rows),
            cols=max(ws.col_count, required_cols),
        )

    ws.clear()
    ws.update(
        values=values,
        range_name="A1",
        value_input_option="USER_ENTERED",
    )


def sync_manager_dashboard_to_google_sheet(
    summary_df,
    fila_df,
    top_problemas_df,
    top_bases_df,
    extra_sheets=None,
):
    """
    Sincroniza as quatro abas usadas pelo app do gerente.
    Retorna (ok, mensagem).
    """
    try:
        spreadsheet_url = st.secrets.get("MANAGER_SOURCE_URL", "")
    except Exception:
        spreadsheet_url = ""

    if not spreadsheet_url:
        return False, "MANAGER_SOURCE_URL não configurado no app operacional."

    gc = _google_sheet_client()
    if gc is None:
        return False, "Credenciais gcp_service_account não configuradas."

    try:
        spreadsheet = gc.open_by_url(spreadsheet_url)

        _write_df_to_worksheet(spreadsheet, "RESUMO", summary_df)
        _write_df_to_worksheet(spreadsheet, "FILA", fila_df)
        _write_df_to_worksheet(spreadsheet, "TOP_PROBLEMAS", top_problemas_df)
        _write_df_to_worksheet(spreadsheet, "TOP_BASES", top_bases_df)

        for sheet_name, df in (extra_sheets or {}).items():
            _write_df_to_worksheet(spreadsheet, sheet_name, df)

        return True, "Base gerencial sincronizada com sucesso."
    except Exception as exc:
        return False, f"Falha ao sincronizar a base gerencial: {exc}"


# =========================
# INTERFACE
# =========================

st.title("Portal de Gestão da Torre de Controle")
st.caption("V1.4.0 — Operação + app do gerente separado")

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
    st.markdown("**3. Pendências da Torre — Google Sheets**")
    url_pendencias_torre = st.text_input("Link da planilha de Pendências", value=DEFAULT_GOOGLE_SHEETS["Pendências da Torre"], key="url_pendencias_torre")
    st.markdown("**4. Acareação e Ressalva — Google Sheets**")
    url_acareacao = st.text_input("Link da planilha de Acareação", value=DEFAULT_GOOGLE_SHEETS["Acareação e Ressalva"], key="url_acareacao")
    st.markdown("**5. Passível a Débito e Indenização — Google Sheets**")
    url_indenizacao = st.text_input("Link da planilha de Indenização", value=DEFAULT_GOOGLE_SHEETS["Passível a Débito e Indenização"], key="url_indenizacao")

    live_control_bases = {}
    for _nome, _url in {
        "Pendências da Torre": url_pendencias_torre,
        "Acareação e Ressalva": url_acareacao,
        "Passível a Débito e Indenização": url_indenizacao,
    }.items():
        try:
            live_control_bases[_nome] = read_public_google_sheet(_url) if _url.strip() else pd.DataFrame()
            st.success(f"{_nome}: conectado")
        except Exception:
            live_control_bases[_nome] = pd.DataFrame()
            st.warning(f"{_nome}: falha na atualização")

    pendencias_torre_link = live_control_bases["Pendências da Torre"]
    acareacao_ressalva_link = live_control_bases["Acareação e Ressalva"]
    debito_indenizacao_link = live_control_bases["Passível a Débito e Indenização"]

    # Arquivo completo da planilha de Pendências, preservando todas as abas.
    try:
        pendencias_torre_workbook = read_public_google_workbook_bytes(
            url_pendencias_torre
        )
    except Exception:
        pendencias_torre_workbook = None


    st.divider()
    st.subheader("First Mile")

    file_sao12 = st.file_uploader(
        "6. Emissões SAO12",
        type=["xlsx", "xls"],
        key="fm_sao12",
        help="Será filtrado automaticamente para Riachuelo, Neodent, Della Via, Stone, Tania Bulhões e ATS."
    )
    file_tres1 = st.file_uploader(
        "7. Emissões TRES1",
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

if not (file_lm and file_eu):
    st.info("Envie AWBStatus e Eu Entrego para processar o Last Mile. A Pendência da Torre é carregada pelo link.")
    st.stop()

try:
    with st.spinner("Processando bases e aplicando regras da V0..."):
        lm = read_last_mile(file_lm.getvalue())
        eu_latest, route_dates = read_eu_entrego(file_eu.getvalue())

        # Índice de retorno do entregador:
        # WhatsApp prevalece; quando a AWB não estiver no WhatsApp,
        # status DEVOLVIDO no Eu Entrego também conta como retorno confirmado.
        returns_set = set(return_awbs)
        _status_eu_retorno = next(
            (
                c for c in [
                    "STATUS_ULTIMA_ROTA",
                    "STATUS_EU_ENTREGO",
                    "STATUS_ROTA",
                    "STATUS"
                ]
                if c in eu_latest.columns
            ),
            None
        )
        if _status_eu_retorno:
            _devolvidos_eu = set(
                eu_latest.loc[
                    eu_latest[_status_eu_retorno]
                    .astype(str)
                    .map(normalize_text)
                    .eq("DEVOLVIDO"),
                    "AWB"
                ].dropna()
            )
            returns_set.update(_devolvidos_eu)

        tower_latest, tower_history = (
            read_torre(pendencias_torre_workbook)
            if pendencias_torre_workbook
            else read_torre_from_dataframe(pendencias_torre_link)
        )

        master = build_master(
            lm,
            eu_latest,
            route_dates,
            tower_latest,
            returns_set,
            reference_date,
        )


        portal_view_mode = st.radio(
            "Tela",
            ["Minha operação", "Dashboard do gerente"],
            horizontal=True,
            key="portal_view_mode",
        )

        if portal_view_mode == "Dashboard do gerente":
            # =========================
            # PAINEL GERENCIAL
            # =========================
            edi_loaded_for_panel = bool(files_edi) if "files_edi" in locals() else False
            fila_gerencial = build_unique_action_queue(
                master,
                edi_loaded=edi_loaded_for_panel,
                analysis_date=reference_date,
            )
            fila_gerencial = fila_gerencial[
                fila_gerencial["PRIORIDADE"].isin(["CRÍTICA", "ALTA", "MÉDIA"])
            ].copy()

            st.header("Dashboard do gerente")

            carteira_total = int(master["AWB"].nunique()) if not master.empty else 0
            awbs_acao = int(len(fila_gerencial))
            criticas = int((fila_gerencial["PRIORIDADE"] == "CRÍTICA").sum()) if not fila_gerencial.empty else 0
            entrega_atraso = int((fila_gerencial["PROBLEMA"] == "ENTREGA EM ATRASO").sum()) if not fila_gerencial.empty else 0
            backlog_torre = int(
                tower_latest.loc[~tower_latest["EVENTO_TORRE"].eq("FINALIZADO"), "AWB"].nunique()
            ) if not tower_latest.empty else 0

            if "SLA_DATA" in master.columns:
                _sla_dt = pd.to_datetime(master["SLA_DATA"], errors="coerce").dt.normalize()
            else:
                _sla_dt = pd.Series(pd.NaT, index=master.index)

            _teve_rota = (
                master["TEVE_ROTA_HOJE"].fillna(False).astype(bool)
                if "TEVE_ROTA_HOJE" in master.columns
                else pd.Series(False, index=master.index)
            )

            _situacao_norm = (
                master["SITUACAO_GERENCIAL"].astype(str).map(normalize_text)
                if "SITUACAO_GERENCIAL" in master.columns
                else pd.Series("", index=master.index)
            )

            _status_norm_panel = (
                master["STATUS_SISTEMA"].astype(str).map(normalize_text)
                if "STATUS_SISTEMA" in master.columns
                else pd.Series("", index=master.index)
            )

            _tentativas_panel = (
                pd.to_numeric(master["QT_TENTATIVAS_INSUCESSO"], errors="coerce").fillna(0).astype(int)
                if "QT_TENTATIVAS_INSUCESSO" in master.columns
                else pd.Series(0, index=master.index)
            )

            _em_torre_panel = (
                master["EM_TORRE_ATIVA"].fillna(False).astype(bool)
                if "EM_TORRE_ATIVA" in master.columns
                else pd.Series(False, index=master.index)
            )

            # Mesma regra do Radar Preventivo — Last Mile:
            # SLA do dia sem rota = Pendente Entrega + SLA hoje + nenhuma rota criada hoje + fora da Torre ativa.
            # Se teve rota hoje e voltou com insucesso, NÃO entra aqui.
            _piso_sem_rota_mask = (
                _sla_dt.eq(pd.Timestamp(reference_date).normalize())
                & ~_teve_rota
                & ~_em_torre_panel
                & _status_norm_panel.eq("PENDENTE ENTREGA")
                & ~_situacao_norm.str.contains("ENTREGUE|BAIXADO|DEVOLVIDO", regex=True, na=False)
            )
            sla_dia_piso_sem_rota = int(_piso_sem_rota_mask.sum())

            terceira_tentativa_entrega = int(
                (
                    _tentativas_panel.ge(3)
                    & _status_norm_panel.eq("PENDENTE ENTREGA")
                    & ~_situacao_norm.str.contains("ENTREGUE|BAIXADO|DEVOLVIDO", regex=True, na=False)
                ).sum()
            )

            last_mile_pendente_desembarque = int(
                (
                    _status_norm_panel.eq("PENDENTE DESEMBARQUE")
                    & _sla_dt.notna()
                    & _sla_dt.le(pd.Timestamp(reference_date).normalize())
                    & ~_situacao_norm.str.contains("ENTREGUE|BAIXADO|DEVOLVIDO", regex=True, na=False)
                ).sum()
            )

            # Acareação em andamento
            acar = acareacao_ressalva_link.copy()
            acar_status_col = _panel_find_col(acar, ["STATUS ACAREACAO", "STATUS ACAREAÇÃO", "STATUS", "SITUACAO", "SITUAÇÃO"])
            if acar_status_col:
                acar_status_norm = acar[acar_status_col].astype(str).map(normalize_text)
                acar_andamento = acar[acar_status_norm.eq("EM ANDAMENTO")].copy()
            else:
                acar_andamento = acar.iloc[0:0].copy()

            # Passíveis 2026 (CDSP2 + SAO12)
            inden = debito_indenizacao_link.copy()
            claim_col = _panel_find_col(inden, ["DATA DE CLAIM", "DATA CLAIM"])
            emissao_col = _panel_find_col(inden, ["DATA DE EMISSÃO", "DATA DE EMISSAO"])
            if claim_col:
                ano_ref = pd.to_datetime(inden[claim_col], errors="coerce").dt.year
            elif emissao_col:
                ano_ref = pd.to_datetime(inden[emissao_col], errors="coerce").dt.year
            else:
                ano_ref = pd.Series(pd.NA, index=inden.index)

            inden = inden[ano_ref.eq(2026)].copy()
            inden_base_col = _panel_find_col(inden, ["BASE OFENSORA", "OFENSOR", "BASE", "ORIGEM", "ESTAÇÃO", "ESTACAO"])
            inden_valor_col = _panel_find_col(inden, ["VALOR INDENIZAÇÃO", "VALOR INDENIZACAO", "VALOR DO CLAIM", "VALOR CLAIM", "VALOR"])
            inden["_VALOR_NUM"] = _panel_money_to_num(inden[inden_valor_col]) if inden_valor_col else 0.0
            if inden_base_col:
                base_norm = inden[inden_base_col].astype(str).map(normalize_text)
                passivel_total = float(inden.loc[
                    base_norm.str.contains("CDSP2|SAO12", regex=True, na=False),
                    "_VALOR_NUM"
                ].sum())
            else:
                passivel_total = 0.0

            # EDI gerencial: First Mile será exibido como EDI no painel do gerente.
            fm_frames_gerente = []
            if file_sao12:
                try:
                    fm_frames_gerente.append(
                        read_first_mile_awbstatus(file_sao12.getvalue(), "SAO12")
                    )
                except Exception:
                    pass

            if file_tres1:
                try:
                    fm_frames_gerente.append(
                        read_first_mile_awbstatus(file_tres1.getvalue(), "TRES1")
                    )
                except Exception:
                    pass

            first_mile_gerente = (
                pd.concat(fm_frames_gerente, ignore_index=True, sort=False)
                if fm_frames_gerente else pd.DataFrame()
            )

            if not first_mile_gerente.empty:
                first_mile_gerente["GRUPO_FIRST_MILE"] = (
                    first_mile_gerente["STATUS_SISTEMA"].apply(first_mile_status_group)
                )

            edi_base_gerente = pd.DataFrame()
            if files_edi:
                try:
                    edi_payload_gerente = tuple((f.name, f.getvalue()) for f in files_edi)
                    edi_base_gerente, _edi_audit_gerente = read_edi_files(edi_payload_gerente)
                    if not edi_base_gerente.empty:
                        edi_base_gerente = edi_base_gerente.copy()
                        edi_base_gerente["CLIENTE_EDI"] = edi_base_gerente.apply(edi_client_name, axis=1)
                        edi_base_gerente["STATUS_EDI_GERENCIAL"] = edi_base_gerente.apply(classify_edi_status, axis=1)
                        edi_base_gerente = mark_edi_execution_from_first_mile(
                            edi_base_gerente,
                            first_mile_gerente,
                        )
                except Exception:
                    edi_base_gerente = pd.DataFrame()

            edi_resumo_gerente, edi_detalhe_gerente = build_edi_manager_views(
                first_mile_gerente,
                edi_base_gerente,
                reference_date,
            )

            g1, g2, g3, g4 = st.columns(4)
            g1.metric("AWBs monitoradas", carteira_total)
            g2.metric("AWBs com ação", awbs_acao)
            g3.metric("Ações imediatas", criticas)
            g4.metric("Entrega em atraso", entrega_atraso)

            g5, g6, g7, g8 = st.columns(4)
            g5.metric("SLA do dia sem rota", sla_dia_piso_sem_rota)
            g6.metric("3ª tentativa de entrega", terceira_tentativa_entrega)
            g7.metric("Backlog da Torre", backlog_torre)
            g8.metric(
                "Acareações em andamento",
                int(len(acar_andamento))
            )

            g9, _g10, _g11, _g12 = st.columns(4)
            g9.metric(
                "Valor em acareação",
                _panel_brl(
                    _panel_money_to_num(
                        acar_andamento[_panel_find_col(acar_andamento, ["VALOR DA CARGA", "VALOR"])]
                    ).sum()
                    if not acar_andamento.empty and _panel_find_col(acar_andamento, ["VALOR DA CARGA", "VALOR"])
                    else 0.0
                )
            )

            if not fila_gerencial.empty:
                st.subheader("Principais problemas")
                prob_resumo = (
                    fila_gerencial.groupby(["PROBLEMA", "PRIORIDADE"], dropna=False)
                    .size()
                    .reset_index(name="AWBS")
                    .sort_values(["AWBS"], ascending=False)
                    .head(10)
                )
                st.dataframe(prob_resumo, use_container_width=True, hide_index=True)

                st.subheader("Bases / responsáveis com mais ações")
                local_resumo = (
                    fila_gerencial.groupby("LOCALIZAÇÃO / RESPONSÁVEL", dropna=False)
                    .size()
                    .reset_index(name="AWBS")
                    .sort_values(["AWBS"], ascending=False)
                    .head(10)
                )
                st.dataframe(local_resumo, use_container_width=True, hide_index=True)

            if not fila_gerencial.empty:
                cliente_resumo = (
                    fila_gerencial.groupby("CLIENTE", dropna=False)
                    .size()
                    .reset_index(name="AWBS")
                    .sort_values(["AWBS"], ascending=False)
                    .head(10)
                )
                st.subheader("Top clientes impactados")
                st.dataframe(cliente_resumo, use_container_width=True, hide_index=True)

            st.divider()

            st.caption(
                "AWBs monitoradas = total de AWBs únicas na carteira atual. "
                "Não representa entregas concluídas."
            )
            resumo_dashboard = pd.DataFrame([
                {"METRICA": "Data de análise", "VALOR": str(reference_date)},
                {"METRICA": "Atualizado em", "VALOR": str(pd.Timestamp.now())},
                {"METRICA": "AWBs monitoradas", "VALOR": carteira_total},
                {"METRICA": "AWBs com ação", "VALOR": awbs_acao},
                {"METRICA": "Ações imediatas", "VALOR": criticas},
                {"METRICA": "Entrega em atraso", "VALOR": entrega_atraso},
                {"METRICA": "SLA do dia sem rota", "VALOR": sla_dia_piso_sem_rota},
                {"METRICA": "Last Mile pendente desembarque", "VALOR": last_mile_pendente_desembarque},
                {"METRICA": "3ª tentativa de entrega", "VALOR": terceira_tentativa_entrega},
                {"METRICA": "Backlog da Torre", "VALOR": backlog_torre},
                {"METRICA": "Acareações em andamento", "VALOR": int(len(acar_andamento))},
                {"METRICA": "Valor em acareação", "VALOR": float(
                    _panel_money_to_num(
                        acar_andamento[_panel_find_col(acar_andamento, ["VALOR DA CARGA", "VALOR"])]
                    ).sum()
                    if not acar_andamento.empty and _panel_find_col(acar_andamento, ["VALOR DA CARGA", "VALOR"])
                    else 0.0
                )},
                {"METRICA": "EDI pendente embarque SAO12", "VALOR": int(
                    edi_detalhe_gerente[
                        (edi_detalhe_gerente["BASE"].astype(str).str.upper().eq("SAO12"))
                        & (edi_detalhe_gerente["INDICADOR"].astype(str).eq("PENDENTE DE EMBARQUE"))
                    ]["AWB"].nunique()
                ) if not edi_detalhe_gerente.empty else 0},
                {"METRICA": "EDI pendente embarque TRES1", "VALOR": int(
                    edi_detalhe_gerente[
                        (edi_detalhe_gerente["BASE"].astype(str).str.upper().eq("TRES1"))
                        & (edi_detalhe_gerente["INDICADOR"].astype(str).eq("PENDENTE DE EMBARQUE"))
                    ]["AWB"].nunique()
                ) if not edi_detalhe_gerente.empty else 0},
                {"METRICA": "EDI pendente desembarque SAO12", "VALOR": int(
                    edi_detalhe_gerente[
                        (edi_detalhe_gerente["BASE"].astype(str).str.upper().eq("SAO12"))
                        & (edi_detalhe_gerente["INDICADOR"].astype(str).eq("PENDENTE DE DESEMBARQUE"))
                    ]["AWB"].nunique()
                ) if not edi_detalhe_gerente.empty else 0},
                {"METRICA": "EDI pendente desembarque TRES1", "VALOR": int(
                    edi_detalhe_gerente[
                        (edi_detalhe_gerente["BASE"].astype(str).str.upper().eq("TRES1"))
                        & (edi_detalhe_gerente["INDICADOR"].astype(str).eq("PENDENTE DE DESEMBARQUE"))
                    ]["AWB"].nunique()
                ) if not edi_detalhe_gerente.empty else 0},
                {"METRICA": "EDI entrega destino SLA", "VALOR": int(
                    edi_detalhe_gerente[
                        edi_detalhe_gerente["INDICADOR"].astype(str).eq("ENTREGA NO DESTINO PELO SLA")
                    ]["AWB"].nunique()
                ) if not edi_detalhe_gerente.empty else 0},
                {"METRICA": "EDI missing", "VALOR": int(
                    edi_detalhe_gerente[
                        edi_detalhe_gerente["INDICADOR"].astype(str).eq("MISSING")
                    ]["AWB"].nunique()
                ) if not edi_detalhe_gerente.empty else 0},
                {"METRICA": "EDI discrepância", "VALOR": int(
                    edi_detalhe_gerente[
                        edi_detalhe_gerente["INDICADOR"].astype(str).eq("DISCREPÂNCIA")
                    ]["AWB"].nunique()
                ) if not edi_detalhe_gerente.empty else 0},
            ])

            pacote_gerente = build_manager_pack_bytes(
                resumo_dashboard,
                fila_gerencial.drop(columns=["_ORDEM_FILA"], errors="ignore"),
                prob_resumo if 'prob_resumo' in locals() else pd.DataFrame(),
                local_resumo if 'local_resumo' in locals() else pd.DataFrame(),
                pd.DataFrame(),
                extra_sheets={
                    "EDI_RESUMO": edi_resumo_gerente,
                    "EDI_DETALHE": edi_detalhe_gerente,
                },
            )

            st.download_button(
                "Baixar pacote do dashboard do gerente",
                data=pacote_gerente,
                file_name="dashboard_gerente.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_pacote_gerente",
            )


            # Sincronização automática da base gerencial.
            _sync_key = (
                str(reference_date),
                int(carteira_total),
                int(awbs_acao),
                int(criticas),
                int(entrega_atraso),
                int(sla_dia_piso_sem_rota),
                int(terceira_tentativa_entrega),
                int(backlog_torre),
                int(len(acar_andamento)),
                int(last_mile_pendente_desembarque),
                int(len(edi_detalhe_gerente)),
            )

            if st.session_state.get("_manager_last_sync_key") != _sync_key:
                _sync_ok, _sync_msg = sync_manager_dashboard_to_google_sheet(
                    resumo_dashboard,
                    fila_gerencial.drop(columns=["_ORDEM_FILA"], errors="ignore"),
                    prob_resumo if "prob_resumo" in locals() else pd.DataFrame(),
                    local_resumo if "local_resumo" in locals() else pd.DataFrame(),
                extra_sheets={
                    "EDI_RESUMO": edi_resumo_gerente,
                    "EDI_DETALHE": edi_detalhe_gerente,
                },
                )
                if _sync_ok:
                    st.session_state["_manager_last_sync_key"] = _sync_key

            with st.expander("Sincronização do dashboard gerencial"):
                if st.button("Sincronizar agora", key="sync_manager_dashboard_now"):
                    _sync_ok, _sync_msg = sync_manager_dashboard_to_google_sheet(
                        resumo_dashboard,
                        fila_gerencial.drop(columns=["_ORDEM_FILA"], errors="ignore"),
                        prob_resumo if "prob_resumo" in locals() else pd.DataFrame(),
                        local_resumo if "local_resumo" in locals() else pd.DataFrame(),
                    extra_sheets={
                        "EDI_RESUMO": edi_resumo_gerente,
                        "EDI_DETALHE": edi_detalhe_gerente,
                    },
                    )
                    if _sync_ok:
                        st.success(_sync_msg)
                        st.session_state["_manager_last_sync_key"] = _sync_key
                    else:
                        st.error(_sync_msg)

            st.stop()




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
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Booking aguardando execução", int(edi_counts.get("BOOKING REAL", 0)))
            b2.metric("Ainda sem Booking", int(edi_counts.get("AGUARDANDO BOOKING", 0)))
            b3.metric("Booking já executado", int(edi_counts.get("BOOKING JÁ EXECUTADO", 0)))
            b4.metric(
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
                "O cruzamento com First Mile permanece como validação técnica e não altera a pendência sem correspondência confirmada."
            )

            # Validação do cruzamento EDI x First Mile.
            edi_pending_cross = edi_base[
                edi_base["STATUS_EDI_GERENCIAL"].isin(
                    ["BOOKING REAL", "AGUARDANDO BOOKING"]
                )
            ].copy()

            edi_keys = set(
                edi_pending_cross["_AWB_CRUZAMENTO"]
                .dropna()
                .astype(str)
                .loc[lambda s: s.str.strip().ne("")]
            )

            fm_keys = set()
            if first_mile is not None and not first_mile.empty and "AWB" in first_mile.columns:
                fm_keys = set(
                    first_mile["AWB"]
                    .dropna()
                    .astype(str)
                    .map(normalize_cross_key)
                    .loc[lambda s: s.str.strip().ne("")]
                )

            common_keys = edi_keys.intersection(fm_keys)

            with st.expander("Validar cruzamento EDI × First Mile"):
                c1, c2, c3 = st.columns(3)
                c1.metric("AWBs pendentes no EDI", len(edi_keys))
                c2.metric("AWBs disponíveis no First Mile", len(fm_keys))
                c3.metric("AWBs encontradas nos dois", len(common_keys))

                st.caption(
                    "Esta validação confirma se o zero do cruzamento é real ou se existe diferença de formato entre as AWBs."
                )

                sample_edi = sorted(list(edi_keys))[:20]
                sample_fm = sorted(list(fm_keys))[:20]

                max_len = max(len(sample_edi), len(sample_fm), 1)
                sample_df = pd.DataFrame({
                    "EXEMPLO_AWB_EDI": sample_edi + [""] * (max_len - len(sample_edi)),
                    "EXEMPLO_AWB_FIRST_MILE": sample_fm + [""] * (max_len - len(sample_fm)),
                })

                st.dataframe(
                    safe_dataframe_for_streamlit(sample_df),
                    use_container_width=True,
                    hide_index=True,
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

            # Priorização operacional das pendências EDI por idade.
            edi_priority = edi_base[
                edi_base["STATUS_EDI_GERENCIAL"].isin(
                    ["BOOKING REAL", "AGUARDANDO BOOKING"]
                )
            ].copy()

            if not edi_priority.empty:
                analysis_date = pd.to_datetime(reference_date, errors="coerce")

                # Para Booking, usa a data de integração como referência operacional.
                # Se não houver, utiliza Recebimento.
                edi_priority["DATA_REFERENCIA_EDI"] = pd.to_datetime(
                    edi_priority.get("Integracao"), errors="coerce"
                )
                fallback_date = pd.to_datetime(
                    edi_priority.get("Recebimento"), errors="coerce"
                )
                edi_priority["DATA_REFERENCIA_EDI"] = (
                    edi_priority["DATA_REFERENCIA_EDI"].fillna(fallback_date)
                )

                edi_priority["DIAS_EM_ABERTO"] = (
                    analysis_date.normalize()
                    - edi_priority["DATA_REFERENCIA_EDI"].dt.normalize()
                ).dt.days

                def faixa_idade_edi(dias):
                    if pd.isna(dias):
                        return "SEM DATA"
                    if dias <= 0:
                        return "HOJE"
                    if dias == 1:
                        return "1 DIA"
                    if dias <= 3:
                        return "2 A 3 DIAS"
                    if dias <= 7:
                        return "4 A 7 DIAS"
                    return "MAIS DE 7 DIAS"

                edi_priority["FAIXA_IDADE"] = edi_priority["DIAS_EM_ABERTO"].apply(
                    faixa_idade_edi
                )

                st.markdown("### Prioridade das pendências EDI")
                st.caption(
                    "A fila é priorizada pelo tempo desde a integração do registro. "
                    "Quanto mais antiga a pendência, maior a prioridade de atuação."
                )

                p1, p2, p3, p4 = st.columns(4)
                p1.metric(
                    "Mais de 7 dias",
                    int((edi_priority["DIAS_EM_ABERTO"] > 7).sum())
                )
                p2.metric(
                    "4 a 7 dias",
                    int(edi_priority["DIAS_EM_ABERTO"].between(4, 7).sum())
                )
                p3.metric(
                    "2 a 3 dias",
                    int(edi_priority["DIAS_EM_ABERTO"].between(2, 3).sum())
                )
                p4.metric(
                    "Até 1 dia",
                    int((edi_priority["DIAS_EM_ABERTO"] <= 1).sum())
                )

                priority_summary = (
                    edi_priority
                    .groupby(
                        ["CLIENTE_EDI", "STATUS_EDI_GERENCIAL", "FAIXA_IDADE"],
                        dropna=False
                    )
                    .size()
                    .reset_index(name="AWBS")
                )

                faixa_order = {
                    "MAIS DE 7 DIAS": 1,
                    "4 A 7 DIAS": 2,
                    "2 A 3 DIAS": 3,
                    "1 DIA": 4,
                    "HOJE": 5,
                    "SEM DATA": 6,
                }
                priority_summary["_ORDEM"] = (
                    priority_summary["FAIXA_IDADE"]
                    .map(faixa_order)
                    .fillna(99)
                )
                priority_summary = (
                    priority_summary
                    .sort_values(
                        ["_ORDEM", "AWBS"],
                        ascending=[True, False]
                    )
                    .drop(columns="_ORDEM")
                )

                st.dataframe(
                    safe_dataframe_for_streamlit(priority_summary),
                    use_container_width=True,
                    hide_index=True,
                )

                with st.expander("Ver fila priorizada das pendências EDI"):
                    priority_cols = [
                        "CLIENTE_EDI",
                        "STATUS_EDI_GERENCIAL",
                        "DIAS_EM_ABERTO",
                        "FAIXA_IDADE",
                        "Pedido",
                        "Numero",
                        "Nº AWB",
                        "Origem",
                        "Destino",
                        "DATA_REFERENCIA_EDI",
                        "UltimaOcorrencia",
                    ]
                    priority_cols = [
                        c for c in priority_cols if c in edi_priority.columns
                    ]
                    priority_detail = edi_priority.sort_values(
                        ["DIAS_EM_ABERTO"],
                        ascending=False,
                        na_position="last"
                    )
                    st.dataframe(
                        safe_dataframe_for_streamlit(
                            priority_detail[priority_cols]
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

# Rota criada hoje precisa considerar a existência de rota no Eu Entrego,
# independentemente de ter terminado com sucesso ou insucesso.
# Se teve rota hoje e voltou com insucesso, NÃO é "sem rota".
master["TEM_ROTA_HOJE"] = master["TEVE_ROTA_HOJE"].fillna(False).astype(bool)
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


st.divider()
st.subheader("Radar preventivo — Last Mile")

p1, p2, p3, p4 = st.columns(4)
p1.metric("SLA do dia sem rota", int(master["SLA_DO_DIA_NO_PISO"].sum()))
p2.metric("SLA vencido sem rota", int(master["SLA_VENCIDO_SEM_ROTA"].sum()))
p3.metric("2ª tentativa — risco", int(master["SEGUNDA_TENTATIVA_RISCO"].sum()))
p4.metric("3ª tentativa de entrega", int(master["TERCEIRA_TENTATIVA_RISCO_ALTO"].sum()))

st.caption(
    "SLA do dia sem rota = Pendente Entrega, SLA vencendo na data de análise, "
    "sem rota criada no Eu Entrego na data analisada e sem pendência ativa na Torre. "
    "Se houve rota no dia e voltou com insucesso, a carga deve sair de SLA sem rota e entrar como insucesso/tentativa."
)

alerta = st.selectbox(
    "Detalhar alerta preventivo",
    [
        "SLA do dia sem rota",
        "SLA vencido sem rota",
        "2ª tentativa — risco",
        "3ª tentativa de entrega",
    ]
)
alert_map = {
    "SLA do dia sem rota": "SLA_DO_DIA_NO_PISO",
    "SLA vencido sem rota": "SLA_VENCIDO_SEM_ROTA",
    "2ª tentativa — risco": "SEGUNDA_TENTATIVA_RISCO",
    "3ª tentativa de entrega": "TERCEIRA_TENTATIVA_RISCO_ALTO",
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


master = add_live_control_flags(
    master,
    pendencias_torre_link,
    acareacao_ressalva_link,
    debito_indenizacao_link,
)

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


st.header("Tratativas especiais")

def _col(df, termos):
    if df is None or df.empty: return None
    mapa={normalize_text(c):c for c in df.columns}
    for t in termos:
        n=normalize_text(t)
        if n in mapa:return mapa[n]
    for t in termos:
        n=normalize_text(t)
        for k,v in mapa.items():
            if n in k:return v
    return None

def _num_money(s):
    x=s.astype(str).str.replace("R$","",regex=False).str.replace(" ","",regex=False)
    m=x.str.contains(",",regex=False)
    x.loc[m]=x.loc[m].str.replace(".","",regex=False).str.replace(",",".",regex=False)
    return pd.to_numeric(x,errors="coerce").fillna(0)

def _brl(v):
    return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")

acar=acareacao_ressalva_link.copy()

def _status_acareacao_col(df):
    # Primeiro tenta nomes explícitos.
    explicit = _col(df, ["STATUS ACAREAÇÃO", "STATUS ACAREACAO", "STATUS", "SITUAÇÃO", "SITUACAO"])
    if explicit:
        vals = df[explicit].astype(str).map(normalize_text)
        if vals.str.contains("EM ANDAMENTO|CONCLUID", regex=True, na=False).any():
            return explicit

    # A planilha atual possui a coluna de status sem título (Unnamed).
    # Identifica pela presença dos valores operacionais.
    for c in df.columns:
        vals = df[c].astype(str).map(normalize_text)
        if vals.str.contains("EM ANDAMENTO", regex=False, na=False).any():
            return c
        if vals.str.contains("CONCLUID", regex=False, na=False).any():
            return c
    return None

sc=_status_acareacao_col(acar)
vc=_col(acar,["VALOR DA CARGA","VALOR"])
ec=_col(acar,["ENTREGADOR"])
ac=_col(acar,["AWB"])

if sc:
    status_acar_norm = acar[sc].astype(str).map(normalize_text)
    aberta = acar[status_acar_norm.eq("EM ANDAMENTO")].copy()
else:
    # Sem status confiável, não contabiliza para evitar valor incorreto.
    aberta = acar.iloc[0:0].copy()

aberta["_VALOR"]=_num_money(aberta[vc]) if vc else 0.0

inden=debito_indenizacao_link.copy()

# Somente processos/claims de 2026.
data_claim_col = _col(inden, ["DATA DE CLAIM", "DATA CLAIM"])
data_emissao_col = _col(inden, ["DATA DE EMISSÃO", "DATA DE EMISSAO"])

if data_claim_col:
    _ano_ref = pd.to_datetime(inden[data_claim_col], errors="coerce").dt.year
elif data_emissao_col:
    _ano_ref = pd.to_datetime(inden[data_emissao_col], errors="coerce").dt.year
else:
    _ano_ref = pd.Series(pd.NA, index=inden.index)

inden = inden[_ano_ref.eq(2026)].copy()

vi=_col(inden,["VALOR INDENIZAÇÃO","VALOR INDENIZACAO","VALOR DO CLAIM","VALOR CLAIM","VALOR"])
bi=_col(inden,["BASE OFENSORA","OFENSOR","BASE","ORIGEM","ESTAÇÃO","ESTACAO"])
ai=_col(inden,["AWB"])
inden["_VALOR"]=_num_money(inden[vi]) if vi else 0.0
if bi:
    bn=inden[bi].astype(str).map(normalize_text)
    cdsp2=inden[bn.str.contains("CDSP2",na=False)].copy()
    sao12=inden[bn.str.contains("SAO12",na=False)].copy()
else:
    cdsp2=inden.iloc[0:0].copy(); sao12=inden.iloc[0:0].copy()

c1,c2,c3,c4=st.columns(4)
c1.metric("Acareações em aberto",len(aberta))
c2.metric("Valor em acareação",_brl(aberta["_VALOR"].sum()))
c3.metric("Passível de indenização — CDSP2",_brl(cdsp2["_VALOR"].sum()))
c4.metric("Passível de indenização — SAO12",_brl(sao12["_VALOR"].sum()))

if not aberta.empty and ec:
    st.subheader("Acareação em aberto por entregador")
    r=(aberta.assign(ENTREGADOR=aberta[ec].fillna("NÃO INFORMADO").astype(str).str.strip())
       .groupby("ENTREGADOR",dropna=False)
       .agg(ACAREACOES=("_VALOR","size"),VALOR_TOTAL=("_VALOR","sum"))
       .reset_index().sort_values(["VALOR_TOTAL","ACAREACOES"],ascending=False))
    r["VALOR_TOTAL"]=r["VALOR_TOTAL"].apply(_brl)
    st.dataframe(r,use_container_width=True,hide_index=True)

with st.expander("Ver acareações em andamento"):
    cliente_col = _col(acar, ["CLIENTE"])
    tipo_acar_col = _col(acar, ["TIPO DE ACAREAÇÃO", "TIPO DE ACAREACAO"])
    prazo_col = _col(acar, ["PRAZO DE DEVOLUTIVA", "PRAZO"])
    obs_col = _col(acar, ["OBSERVAÇÃO", "OBSERVACAO", "OBS"])

    cols = [
        c for c in [
            ac,
            cliente_col,
            sc,
            tipo_acar_col,
            ec,
            vc,
            prazo_col,
            obs_col,
        ]
        if c
    ]

    detalhe_acar = aberta[cols].copy() if cols else aberta.copy()

    rename_map = {}
    if ac: rename_map[ac] = "AWB"
    if cliente_col: rename_map[cliente_col] = "CLIENTE"
    if sc: rename_map[sc] = "STATUS"
    if tipo_acar_col: rename_map[tipo_acar_col] = "TIPO DE ACAREAÇÃO"
    if ec: rename_map[ec] = "ENTREGADOR"
    if vc: rename_map[vc] = "VALOR DA CARGA"
    if prazo_col: rename_map[prazo_col] = "PRAZO DE DEVOLUTIVA"
    if obs_col: rename_map[obs_col] = "OBSERVAÇÃO"

    detalhe_acar = detalhe_acar.rename(columns=rename_map)

    st.dataframe(
        detalhe_acar,
        use_container_width=True,
        hide_index=True
    )

st.subheader("Passíveis de indenização — CDSP2 e SAO12")
pv=pd.concat([cdsp2,sao12],ignore_index=True)
if not pv.empty:
    cols=[c for c in [ai,bi,vi,_col(inden,["STATUS DO PROCESSO","STATUS"]),_col(inden,["ANDAMENTO"]),
        _col(inden,["TIPO DO CLAIM","TIPO CLAIM"]),_col(inden,["MOTIVO"]),
        _col(inden,["NÚMERO DO PROCESSO","NUMERO DO PROCESSO","PROCESSO"])] if c]
    if cols: st.dataframe(pv[cols],use_container_width=True,hide_index=True)
else:
    st.info("Nenhum registro identificado para CDSP2 ou SAO12 na coluna de base/ofensor.")

st.divider()


st.header("Fila Única de Ação da Torre")

# EDI é opcional. Detecta se existe algum arquivo EDI carregado na sessão.
edi_loaded_for_queue = False
for _edi_var in ["files_edi", "file_edi", "uploaded_edi", "edi_files"]:
    if _edi_var in locals():
        _edi_value = locals()[_edi_var]
        if isinstance(_edi_value, (list, tuple)):
            edi_loaded_for_queue = len(_edi_value) > 0
        else:
            edi_loaded_for_queue = _edi_value is not None
        if edi_loaded_for_queue:
            break

fila_unica_completa = build_unique_action_queue(
    master,
    edi_loaded=edi_loaded_for_queue,
    analysis_date=reference_date,
)

fila_unica = fila_unica_completa[
    fila_unica_completa["PRIORIDADE"].isin(["CRÍTICA", "ALTA", "MÉDIA"])
].copy()

if not fila_unica.empty:
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Ações críticas", int((fila_unica["PRIORIDADE"] == "CRÍTICA").sum()))
    f2.metric("Prioridade alta", int((fila_unica["PRIORIDADE"] == "ALTA").sum()))
    f3.metric("Prioridade média", int((fila_unica["PRIORIDADE"] == "MÉDIA").sum()))
    f4.metric("AWBs com ação", int(len(fila_unica)))

    filtro_prioridade = st.multiselect(
        "Prioridade",
        ["CRÍTICA", "ALTA", "MÉDIA"],
        default=["CRÍTICA", "ALTA", "MÉDIA"],
        key="filtro_fila_unica_prioridade",
    )

    fila_exibicao = fila_unica[
        fila_unica["PRIORIDADE"].isin(filtro_prioridade)
    ].copy()

    st.dataframe(
        fila_exibicao.drop(columns=["_ORDEM_FILA"], errors="ignore"),
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Baixar Fila Única de Ação",
        data=fila_exibicao.drop(
            columns=["_ORDEM_FILA"], errors="ignore"
        ).to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="fila_unica_acao_torre.csv",
        mime="text/csv",
        key="download_fila_unica",
    )

    if not edi_loaded_for_queue:
        st.info(
            "EDI não carregado nesta atualização. A fila continua operacional; "
            "apenas validações específicas de Booking/EDI não são aplicadas."
        )
else:
    st.info("Não há registros disponíveis para montar a Fila Única de Ação.")

st.divider()

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
    perf = tower_history.copy()
    perf["DATA_EVENTO_DIA"] = pd.to_datetime(
        perf["DATA_EVENTO_TORRE"],
        errors="coerce"
    ).dt.date

    entradas_hoje = perf[
        perf["EVENTO_TORRE"].isin(["PENDENCIA", "PENDENCIA_CORP"])
        & perf["DATA_EVENTO_DIA"].eq(reference_date)
    ]["AWB"].nunique()

    saidas_hoje = perf[
        perf["EVENTO_TORRE"].eq("FINALIZADO")
        & perf["DATA_EVENTO_DIA"].eq(reference_date)
    ]["AWB"].nunique()

    backlog_atual = (
        tower_latest[
            ~tower_latest["EVENTO_TORRE"].eq("FINALIZADO")
        ]["AWB"].nunique()
        if not tower_latest.empty
        else 0
    )

    p1, p2, p3 = st.columns(3)
    p1.metric("Entradas na Torre hoje", int(entradas_hoje))
    p2.metric("Saídas da Torre hoje", int(saidas_hoje))
    p3.metric("Backlog atual", int(backlog_atual))

    st.caption(
        "Entradas = AWBs incluídas hoje nas abas PENDENCIAS/PENDENCIA CORP. "
        "Saídas = AWBs finalizadas hoje na aba FINALIZADAS. "
        "Backlog = AWBs cujo evento mais recente ainda não é FINALIZADO."
    )

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
