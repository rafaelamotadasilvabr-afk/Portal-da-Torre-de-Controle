import io
import re
import unicodedata
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo

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

SHEET_NAMES = [
    "RESUMO",
    "FILA",
    "TOP_PROBLEMAS",
    "TOP_BASES",
    "EDI_RESUMO",
    "EDI_DETALHE",
    "PENDENCIA_MOVIMENTOS",
    "ACAREACOES_DETALHE",
    "AVARIAS_DETALHE",
    "QUALIDADE_DETALHE",
    "BI_AZUL_RESUMO",
    "BI_AZUL_DETALHE",
    "BI_AZUL_CONFERENCIA",
]



# =========================================================
# CSS — LAYOUT CLARO
# =========================================================
st.markdown(
    """
    <style>
    :root {
        --op-blue-900: #08254e;
        --op-blue-800: #0a346e;
        --op-blue-700: #0b63ce;
        --op-blue-100: #eaf3ff;
        --op-slate-900: #10213d;
        --op-slate-700: #3e5168;
        --op-slate-500: #718198;
        --op-border: #dbe5f0;
        --op-bg: #f6f8fb;
        --op-white: #ffffff;
        --op-red: #d92d20;
        --op-orange: #d97706;
        --op-yellow: #b7791f;
        --op-green: #0f766e;
        --op-purple: #7c3aed;
        --op-shadow: 0 8px 22px rgba(8, 37, 78, .07);
        --op-shadow-soft: 0 4px 14px rgba(8, 37, 78, .045);
    }

    .stApp {
        background: var(--op-bg);
        color: var(--op-slate-900);
    }

    .block-container {
        padding-top: .72rem !important;
        padding-left: 1.15rem !important;
        padding-right: 1.15rem !important;
        padding-bottom: 1.2rem !important;
        max-width: 1560px !important;
    }

    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--op-border);
        box-shadow: 8px 0 18px rgba(8, 37, 78, .045);
    }

    [data-testid="stSidebar"] * {
        color: var(--op-slate-900);
    }

    .brand-box {
        padding: 14px 10px 16px 10px;
        border-bottom: 1px solid var(--op-border);
        margin-bottom: 12px;
    }

    .brand-main {
        color: var(--op-blue-900);
        font-size: 3.10rem;
        font-weight: 980;
        font-style: italic;
        letter-spacing: -.07em;
        line-height: .84;
    }

    .brand-sub {
        color: var(--op-blue-700);
        font-size: .78rem;
        font-weight: 900;
        letter-spacing: .38em;
        margin-top: 8px;
    }

    [data-testid="stSidebar"] div[data-testid="stButton"] button {
        width: 100%;
        justify-content: flex-start;
        text-align: left;
        border-radius: 11px;
        border: 1px solid var(--op-border);
        background: #ffffff;
        color: var(--op-slate-900);
        font-weight: 780;
        padding: .58rem .72rem;
        margin-bottom: .24rem;
        min-height: 39px;
        box-shadow: none;
        transition: all .14s ease-in-out;
    }

    [data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
        background: var(--op-blue-100);
        border-color: #9cc5f5;
        color: var(--op-blue-900);
    }

    [data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
        background: var(--op-blue-700);
        color: #ffffff;
        border-color: var(--op-blue-700);
        box-shadow: 0 6px 16px rgba(11, 99, 206, .20);
    }

    .side-note {
        margin-top: 14px;
        border-top: 1px solid var(--op-border);
        padding-top: 10px;
        color: var(--op-slate-500);
        font-size: .72rem;
        line-height: 1.42;
    }

    .hero {
        background: #ffffff;
        color: var(--op-slate-900);
        border: 1px solid var(--op-border);
        border-left: 5px solid var(--op-blue-700);
        border-radius: 16px;
        padding: 12px 16px;
        margin-bottom: 8px;
        box-shadow: var(--op-shadow-soft);
        position: relative;
        overflow: hidden;
    }

    .hero:before { display: none; }

    .hero h1 {
        margin: 0 0 4px 0;
        font-size: 1.45rem;
        line-height: 1.12;
        letter-spacing: -0.035em;
        color: var(--op-blue-900);
        font-weight: 950;
    }

    .hero p {
        margin: 0;
        color: var(--op-slate-500);
        font-size: .82rem;
    }

    .status-strip {
        display: flex;
        align-items: center;
        gap: 8px;
        background: #ffffff;
        border: 1px solid var(--op-border);
        border-left: 4px solid var(--op-blue-700);
        border-radius: 12px;
        padding: 7px 10px;
        margin-bottom: 8px;
        box-shadow: var(--op-shadow-soft);
        color: var(--op-slate-500);
        font-size: .73rem;
        line-height: 1.35;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        background: var(--op-blue-700);
        border-radius: 999px;
        display: inline-block;
        box-shadow: 0 0 0 4px rgba(11, 99, 206, .10);
        flex: 0 0 auto;
    }

    .status-strong {
        color: var(--op-blue-900);
        font-weight: 850;
    }

    .filter-caption {
        color: var(--op-blue-900);
        font-weight: 850;
        font-size: .76rem;
        margin-bottom: 4px;
    }

    .filter-note-compact {
        color: var(--op-slate-500);
        font-size: .68rem;
        text-align: right;
        margin-top: 2px;
    }

    .section-title {
        font-size: 1.02rem;
        font-weight: 950;
        color: var(--op-blue-900);
        margin: 10px 0 2px 0;
    }

    .section-subtitle {
        color: var(--op-slate-500);
        font-size: .78rem;
        margin-bottom: 10px;
    }

    .ops-card {
        background: #ffffff;
        border: 1px solid var(--op-border);
        border-top: 4px solid var(--accent);
        border-radius: 16px;
        padding: 16px 16px 14px 16px;
        min-height: 208px;
        max-height: 208px;
        box-shadow: var(--op-shadow-soft);
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .ops-icon {
        width: 38px;
        height: 38px;
        border-radius: 11px;
        background: var(--soft);
        color: var(--accent);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 950;
        margin-bottom: 10px;
        font-size: .96rem;
    }

    .ops-label {
        color: var(--op-blue-900);
        font-size: .78rem;
        font-weight: 950;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: .012em;
        min-height: 38px;
        line-height: 1.24;
        overflow: hidden;
    }

    .ops-value {
        color: var(--accent);
        font-size: 2.55rem;
        font-weight: 980;
        line-height: 1;
        letter-spacing: -.055em;
        margin-bottom: 8px;
    }

    .ops-sub {
        color: var(--op-slate-500);
        font-size: .76rem;
        line-height: 1.34;
        margin-top: auto;
        min-height: 42px;
        overflow: hidden;
    }

    .ops-mini-grid {
        margin-top: auto;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
    }

    .ops-mini {
        border: 1px solid var(--op-border);
        background: #f8fafc;
        border-radius: 11px;
        padding: 8px 8px;
        text-align: center;
    }

    .ops-mini-title {
        color: var(--op-slate-500);
        font-size: .66rem;
        font-weight: 800;
        margin-bottom: 3px;
    }

    .ops-mini-value {
        color: var(--mini-color);
        font-size: 1.16rem;
        font-weight: 950;
        line-height: 1;
    }

    .kpi {
        background: #ffffff;
        border: 1px solid var(--op-border);
        border-radius: 15px;
        padding: 13px 14px 11px 14px;
        height: 172px;
        min-height: 172px;
        max-height: 172px;
        box-shadow: var(--op-shadow-soft);
        border-top: 4px solid var(--accent);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        position: relative;
    }

    .kpi:after { display: none; }

    .kpi-icon {
        width: 34px;
        height: 34px;
        border-radius: 10px;
        background: var(--soft);
        color: var(--accent);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 950;
        margin-bottom: 8px;
    }

    .label {
        color: var(--op-blue-900);
        font-size: .70rem;
        font-weight: 950;
        margin-bottom: 6px;
        text-transform: uppercase;
        min-height: 31px;
        max-height: 31px;
        line-height: 1.22;
        overflow: hidden;
        letter-spacing: .012em;
    }

    .value {
        color: var(--value);
        font-size: 2.16rem;
        font-weight: 980;
        line-height: 1;
        margin-bottom: 6px;
        letter-spacing: -.055em;
        min-height: 34px;
        display: flex;
        align-items: center;
    }

    .sub {
        color: var(--op-slate-500);
        font-size: .69rem;
        line-height: 1.28;
        min-height: 34px;
        max-height: 34px;
        overflow: hidden;
        margin-top: auto;
    }

    div[data-testid="stButton"] button {
        border-radius: 11px;
        font-weight: 800;
        min-height: 38px;
        padding-top: .34rem;
        padding-bottom: .34rem;
        border: 1px solid #cfd9e7;
        background: #ffffff;
        color: var(--op-blue-900);
        box-shadow: 0 3px 10px rgba(8, 37, 78, .035);
    }

    div[data-testid="stButton"] button:hover {
        border-color: var(--op-blue-700);
        background: var(--op-blue-100);
        color: var(--op-blue-900);
    }

    div[data-testid="column"] div[data-testid="stButton"] {
        margin-top: -0.34rem;
    }

    .card-row-spacer {
        height: 10px;
    }

    .detail-box {
        background: #ffffff;
        border: 1px solid #cfe0f5;
        border-left: 5px solid var(--op-blue-700);
        border-radius: 15px;
        padding: 14px 16px;
        margin-top: 4px;
        margin-bottom: 14px;
        box-shadow: 0 10px 24px rgba(8, 37, 78, .075);
    }

    .detail-title {
        color: var(--op-blue-900);
        font-size: 1.02rem;
        font-weight: 950;
        margin-bottom: 4px;
    }

    .detail-sub {
        color: var(--op-slate-500);
        font-size: .76rem;
        margin-bottom: 9px;
        line-height: 1.36;
    }

    .detail-count {
        display: inline-block;
        background: var(--op-blue-100);
        color: var(--op-blue-900);
        border: 1px solid #c9dcf8;
        border-radius: 999px;
        padding: 5px 9px;
        font-size: .70rem;
        font-weight: 900;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--op-border);
        border-radius: 14px;
        overflow: hidden;
        box-shadow: var(--op-shadow-soft);
    }

    div[data-testid="stDownloadButton"] button {
        border-radius: 11px;
        border: 1px solid #cfd9e7;
        background: #ffffff;
        color: var(--op-blue-900);
        font-weight: 800;
        min-height: 38px;
    }

    .stAlert { border-radius: 13px !important; }

    div[data-testid="stVerticalBlock"] { gap: .50rem; }
    .element-container { margin-bottom: .18rem; }

    /* Cabeçalho corporativo — Central Operacional */
    .ops-header-shell {
        width: 100%;
        background: #ffffff;
        border: 1px solid var(--op-border);
        border-bottom: 1px solid #d8e3f0;
        border-radius: 16px;
        box-shadow: 0 8px 22px rgba(8, 37, 78, .055);
        padding: 14px 16px;
        margin-bottom: 10px;
    }

    .ops-header-title {
        margin: 0;
        color: var(--op-blue-900);
        font-size: 1.52rem;
        font-weight: 950;
        letter-spacing: -0.04em;
        line-height: 1.08;
        text-transform: uppercase;
        white-space: nowrap;
    }

    .ops-header-subtitle {
        margin-top: 6px;
        color: var(--op-slate-500);
        font-size: .82rem;
        font-weight: 650;
        display: flex;
        align-items: center;
        gap: 7px;
        white-space: nowrap;
    }

    .ops-info-icon {
        width: 17px;
        height: 17px;
        border-radius: 999px;
        border: 1px solid #b8c8dc;
        color: var(--op-slate-500);
        font-size: .68rem;
        font-weight: 850;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: #f8fafc;
    }

    .ops-update-box {
        min-height: 50px;
        padding: 7px 9px;
        border-radius: 12px;
        border: 1px solid #e0e8f2;
        background: #f8fafc;
        line-height: 1.18;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    .ops-update-label {
        color: var(--op-slate-500);
        font-size: .64rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: .035em;
        margin-bottom: 3px;
        white-space: nowrap;
    }

    .ops-update-value {
        color: var(--op-blue-900);
        font-size: .78rem;
        font-weight: 850;
        white-space: nowrap;
    }

    .ops-header-control-label {
        color: var(--op-blue-900);
        font-size: .68rem;
        font-weight: 850;
        margin-bottom: 4px;
    }

    .ops-filter-static {
        min-height: 38px;
        border-radius: 11px;
        border: 1px solid #d5dfeb;
        background: #ffffff;
        color: var(--op-slate-700);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 11px;
        font-size: .78rem;
        font-weight: 750;
        box-shadow: 0 2px 8px rgba(8, 37, 78, .025);
    }

    .ops-filter-static span:last-child {
        color: var(--op-slate-500);
        font-size: .72rem;
    }

    .ops-header-button-spacer {
        height: 18px;
    }

    .ops-header-shell div[data-testid="stButton"] button {
        min-height: 38px;
        border-radius: 11px;
        border: 1px solid var(--op-blue-700);
        background: var(--op-blue-700);
        color: #ffffff;
        font-weight: 850;
        padding: .38rem .84rem;
        white-space: nowrap;
        box-shadow: 0 5px 14px rgba(11, 99, 206, .22);
    }

    .ops-header-shell div[data-testid="stButton"] button:hover {
        background: #0959bb;
        color: #ffffff;
        border-color: #0959bb;
    }

    .ops-header-shell div[data-testid="stDateInput"] input {
        min-height: 38px;
        border-radius: 11px;
        border: 1px solid #d5dfeb;
        background: #ffffff;
        font-size: .78rem;
        font-weight: 750;
    }

    .ops-header-filter-note {
        color: var(--op-slate-500);
        font-size: .66rem;
        text-align: right;
        margin-top: 2px;
    }



    /* Cabeçalho — sincronização administrativa */
    .sync-card {
        min-height: 54px;
        padding: 8px 11px;
        border-radius: 13px;
        border: 1px solid #dbe5f0;
        background: #f8fafc;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow: 0 3px 10px rgba(8, 37, 78, .03);
    }

    .sync-card-label {
        color: var(--op-slate-500);
        font-size: .64rem;
        font-weight: 850;
        text-transform: uppercase;
        letter-spacing: .035em;
        margin-bottom: 3px;
    }

    .sync-card-value {
        color: var(--op-blue-900);
        font-size: .82rem;
        font-weight: 900;
        white-space: nowrap;
    }

    .sync-card-detail {
        color: var(--op-slate-500);
        font-size: .66rem;
        font-weight: 650;
        margin-top: 3px;
        white-space: nowrap;
    }

    .sync-success-strip {
        background: #ecfdf5;
        border: 1px solid #bbf7d0;
        color: #0f766e;
        border-radius: 11px;
        padding: 6px 10px;
        font-size: .74rem;
        font-weight: 800;
        margin-top: 6px;
    }

    .ops-header-shell div[data-testid="stButton"] button {
        min-height: 40px;
        border-radius: 11px;
        border: 1px solid var(--op-blue-700);
        background: var(--op-blue-700);
        color: #ffffff;
        font-weight: 850;
        padding: .40rem .82rem;
        white-space: nowrap;
        box-shadow: 0 5px 14px rgba(11, 99, 206, .18);
    }

    .ops-header-shell div[data-testid="stButton"] button:hover {
        background: #0959bb;
        border-color: #0959bb;
        color: #ffffff;
    }

    .ops-header-button-spacer {
        height: 18px;
    }



    /* Cards operacionais — footer interno sem sobreposição */
    .clickable-card-wrap {
        height: 100%;
        margin-bottom: 0;
    }

    .clickable-card-wrap .ops-card {
        cursor: pointer;
        display: flex;
        flex-direction: column;
        min-height: 238px;
        max-height: none;
        height: 100%;
        overflow: hidden;
        transition:
            transform .18s ease,
            box-shadow .18s ease,
            border-color .18s ease;
    }

    .clickable-card-wrap:hover .ops-card {
        transform: translateY(-2px);
        box-shadow: 0 12px 26px rgba(15, 23, 42, .10);
        border-color: var(--accent);
    }

    .ops-card-main {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-height: 0;
    }

    .ops-sub {
        min-height: auto !important;
        max-height: none !important;
        margin-top: 0 !important;
        overflow: visible !important;
    }

    .ops-mini-grid {
        margin-top: 12px !important;
        margin-bottom: 0 !important;
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
    }

    .ops-mini {
        min-width: 0;
        overflow: hidden;
    }

    .ops-mini-title,
    .ops-mini-value {
        white-space: normal;
        overflow-wrap: anywhere;
    }

    .ops-card-footer {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        min-height: 36px;
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid #e5e7eb;
        color: var(--op-slate-500);
        font-size: .72rem;
        font-weight: 850;
        white-space: nowrap;
        transition: color .18s ease, transform .18s ease;
    }

    .clickable-card-wrap:hover .ops-card-footer {
        color: var(--accent);
        transform: translateX(1px);
    }

    .card-footer-action div[data-testid="stButton"] {
        margin-top: -48px !important;
        height: 48px !important;
        position: relative;
        z-index: 15;
    }

    .card-footer-action div[data-testid="stButton"] button {
        height: 48px !important;
        min-height: 48px !important;
        width: 100% !important;
        border: 0 !important;
        background: transparent !important;
        color: transparent !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
        cursor: pointer !important;
    }

    .card-footer-action div[data-testid="stButton"] button:hover,
    .card-footer-action div[data-testid="stButton"] button:focus,
    .card-footer-action div[data-testid="stButton"] button:active {
        background: transparent !important;
        color: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
    }

    .card-footer-action div[data-testid="stButton"] button p {
        color: transparent !important;
    }

    @media (max-width: 900px) {
        .ops-mini-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 640px) {
        .ops-mini-grid {
            grid-template-columns: 1fr;
        }
        .clickable-card-wrap .ops-card {
            min-height: 260px;
        }
    }


    /* V2.6.9 — card como link real, sem botão Streamlit externo */
    a.operational-card-link,
    a.operational-card-link:visited,
    a.operational-card-link:hover,
    a.operational-card-link:active {
        text-decoration: none !important;
        color: inherit !important;
        display: block;
        height: 100%;
    }

    a.operational-card-link .ops-card {
        cursor: pointer;
        display: flex;
        flex-direction: column;
        min-height: 238px;
        height: 100%;
        max-height: none;
        overflow: hidden;
        transition:
            transform .18s ease,
            box-shadow .18s ease,
            border-color .18s ease;
    }

    a.operational-card-link:hover .ops-card {
        transform: translateY(-2px);
        box-shadow: 0 12px 26px rgba(15, 23, 42, .10);
        border-color: var(--accent);
    }

    a.operational-card-link:hover .ops-card-footer {
        color: var(--accent);
        transform: translateX(1px);
    }

    .card-footer-action {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }


    /* V2.7.1 — rodapé de ação integrado ao card */
    a.operational-card-link,
    a.operational-card-link:visited,
    a.operational-card-link:hover,
    a.operational-card-link:active {
        text-decoration: none !important;
        color: inherit !important;
        cursor: default !important;
        pointer-events: none !important;
    }

    .clickable-card-wrap {
        margin-bottom: 0 !important;
    }

    .clickable-card-wrap .ops-card {
        cursor: default !important;
        border-bottom-left-radius: 0 !important;
        border-bottom-right-radius: 0 !important;
        border-bottom: 0 !important;
        box-shadow: 0 8px 22px rgba(8, 37, 78, .055) !important;
        transition:
            transform .18s ease,
            box-shadow .18s ease,
            border-color .18s ease;
    }

    .ops-card-footer {
        display: none !important;
        visibility: hidden !important;
    }

    .card-footer-button {
        margin-top: -1px !important;
        margin-bottom: 12px !important;
        position: relative;
        z-index: 5;
        padding: 0 !important;
        width: 100%;
    }

    .card-footer-button div[data-testid="stButton"] {
        margin: 0 !important;
        width: 100%;
    }

    .card-footer-button div[data-testid="stButton"] button {
        width: 100% !important;
        height: 42px !important;
        min-height: 42px !important;
        border-radius: 0 0 16px 16px !important;
        border: 1px solid var(--op-border) !important;
        border-top: 1px solid #e5e7eb !important;
        background: #ffffff !important;
        color: var(--op-slate-700) !important;
        box-shadow: 0 8px 22px rgba(8, 37, 78, .055) !important;
        font-size: .78rem !important;
        font-weight: 850 !important;
        line-height: 1 !important;
        padding: 0 15px !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-end !important;
        transition:
            background-color .18s ease,
            color .18s ease,
            border-color .18s ease,
            box-shadow .18s ease;
    }

    .card-footer-button div[data-testid="stButton"] button:hover,
    .card-footer-button div[data-testid="stButton"] button:focus {
        background: #f8fbff !important;
        color: var(--op-blue-700) !important;
        border-color: #c9dcf8 !important;
        border-top-color: #dbe5f0 !important;
        box-shadow: 0 10px 24px rgba(8, 37, 78, .075) !important;
        transform: none !important;
    }

    .card-footer-button div[data-testid="stButton"] button p {
        width: 100%;
        text-align: right;
        color: inherit !important;
        font-size: inherit !important;
        font-weight: inherit !important;
    }

    .clickable-card-wrap:has(+ .card-footer-button:hover) .ops-card,
    .clickable-card-wrap:hover .ops-card {
        transform: translateY(-2px);
        box-shadow: 0 12px 26px rgba(15, 23, 42, .10) !important;
        border-color: var(--accent) !important;
    }

    .clickable-card-wrap:hover + .card-footer-button div[data-testid="stButton"] button {
        color: var(--op-blue-700) !important;
        border-color: #c9dcf8 !important;
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


@st.cache_resource(show_spinner=False)
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


def _values_to_dataframe(values):
    if not values:
        return pd.DataFrame()

    headers = [str(h).strip() for h in values[0]]
    rows = values[1:]

    if not headers:
        return pd.DataFrame()

    width = len(headers)
    normalized_rows = []

    for row in rows:
        row = list(row)
        if len(row) < width:
            row = row + [""] * (width - len(row))
        elif len(row) > width:
            row = row[:width]
        normalized_rows.append(row)

    return pd.DataFrame(normalized_rows, columns=headers)


@st.cache_data(ttl=300, show_spinner=False)
def load_source(url):
    """
    Carrega todas as abas do Google Sheets com cache de 5 minutos.

    Evita erro 429 quando o usuário abre card, fecha card ou baixa Excel,
    porque o Streamlit reroda o script a cada interação.
    """
    gc = _google_sheet_client()
    if gc is None:
        raise RuntimeError(
            "Credenciais gcp_service_account não configuradas no app do gerente."
        )

    spreadsheet = gc.open_by_url(url)
    result = {sheet_name: pd.DataFrame() for sheet_name in SHEET_NAMES}

    ranges = [f"'{sheet_name}'!A:ZZ" for sheet_name in SHEET_NAMES]

    try:
        response = spreadsheet.values_batch_get(ranges=ranges)
        value_ranges = response.get("valueRanges", [])

        for sheet_name, value_range in zip(SHEET_NAMES, value_ranges):
            values = value_range.get("values", [])
            result[sheet_name] = _values_to_dataframe(values)

        return result

    except Exception as batch_error:
        for sheet_name in SHEET_NAMES:
            try:
                ws = spreadsheet.worksheet(sheet_name)
                values = ws.get_all_values()
                result[sheet_name] = _values_to_dataframe(values)
            except gspread.WorksheetNotFound:
                result[sheet_name] = pd.DataFrame()
            except Exception as e:
                if "429" in str(e) or "Quota exceeded" in str(e) or "Read requests per minute" in str(e):
                    raise RuntimeError(
                        "Limite temporário do Google Sheets atingido. "
                        "Aguarde 1 a 2 minutos e clique em Atualizar dados do Google. "
                        "Esta versão reduz leituras com cache e leitura em lote."
                    ) from e
                raise

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
    atraso = number(summary_value(resumo, "Backlog (atraso de entrega)", 0))

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


def money_series_flexible(series):
    if series is None:
        return pd.Series(dtype="float64")

    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0)

    txt = (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.replace("R$", "", regex=False)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
    )

    def _parse_money(value):
        value = str(value).strip()
        if not value:
            return 0.0

        value = re.sub(r"[^0-9,\.\-]", "", value)
        if not value:
            return 0.0

        if "," in value and "." in value:
            # 1.234,56
            if value.rfind(",") > value.rfind("."):
                value = value.replace(".", "").replace(",", ".")
            # 1,234.56
            else:
                value = value.replace(",", "")
        elif "," in value:
            value = value.replace(",", ".")

        try:
            return float(value)
        except Exception:
            return 0.0

    return txt.map(_parse_money).fillna(0)


def find_value_column_flexible(df):
    if df is None or df.empty:
        return None

    preferred = [
        "ACAREACAO VALOR",
        "VALOR_NUM",
        "VALOR DA CARGA",
        "VALOR CARGA",
        "VALOR NF",
        "VALOR_TOTAL",
        "VALOR",
        "VL",
    ]

    col = first_col(df, preferred)
    if col:
        return col

    for col in df.columns:
        col_norm = normalize_text(col)
        if "VALOR" in col_norm or "VL" == col_norm or col_norm.startswith("ORIG_VALOR"):
            return col

    for col in df.columns:
        try:
            sample = " ".join(df[col].dropna().astype(str).head(30).tolist()).upper()
            if "R$" in sample:
                return col
        except Exception:
            continue

    return None


def acareacao_total_value(df):
    if df is None or df.empty:
        return 0.0

    col = find_value_column_flexible(df)
    if not col:
        return 0.0

    return float(money_series_flexible(df[col]).sum())



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
    """
    Filtro dinâmico da visão gerencial.

    Regra:
    - Filtro em branco: não aplica filtro de SLA/data; mostra tudo que está aberto.
    - 1 único dia: prioriza SLA = dia selecionado.
    - Período: prioriza SLA dentro do período.
    - Se não existir SLA válida, usa fallback por outras datas operacionais.
    """
    if df is None or df.empty:
        return df, "sem dados"

    # Campo em branco no Streamlit pode vir como None, lista vazia, tupla vazia,
    # ou intervalo incompleto. Nesses casos, não filtra.
    if date_range is None:
        return df.copy(), "sem filtro de data — exibindo tudo que está aberto"

    if isinstance(date_range, (list, tuple)) and len(date_range) == 0:
        return df.copy(), "sem filtro de data — exibindo tudo que está aberto"

    if not isinstance(date_range, (list, tuple)):
        return df.copy(), "sem filtro de data — exibindo tudo que está aberto"

    if len(date_range) != 2:
        return df.copy(), "sem filtro de data — exibindo tudo que está aberto"

    start, end = date_range

    if start is None or end is None:
        return df.copy(), "sem filtro de data — exibindo tudo que está aberto"

    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()
    single_day = start_ts == end_ts

    # 1) Prioridade: SLA.
    sla_col = first_col(df, ["SLA", "DATA SLA", "DT SLA", "PREVISÃO", "PREVISAO"])
    if sla_col:
        sla_dates = parse_date_col(df[sla_col])
        if sla_dates.notna().any():
            sla_norm = sla_dates.dt.normalize()

            if single_day:
                mask = sla_norm.eq(start_ts)
                return df[mask].copy(), f"Filtro aplicado por SLA do dia {start_ts.strftime('%d/%m/%Y')}"

            mask = sla_norm.between(start_ts, end_ts)
            return df[mask].copy(), f"Filtro aplicado por SLA de {start_ts.strftime('%d/%m/%Y')} a {end_ts.strftime('%d/%m/%Y')}"

    # 2) Fallback: outras datas operacionais.
    date_candidates = [
        "DATA ANÁLISE",
        "DATA ANALISE",
        "ÚLTIMA ROTA",
        "ULTIMA ROTA",
        "DATA EVENTO TORRE",
        "DATA_EVENTO_TORRE",
        "ÚLTIMA ALTERAÇÃO",
        "ULTIMA ALTERACAO",
    ]

    for col_name in date_candidates:
        col = first_col(df, [col_name])
        if col:
            dates = parse_date_col(df[col])
            if dates.notna().any():
                dates_norm = dates.dt.normalize()

                if single_day:
                    mask = dates_norm.eq(start_ts)
                    return df[mask].copy(), f"Filtro aplicado por {col} no dia {start_ts.strftime('%d/%m/%Y')}"

                mask = dates_norm.between(start_ts, end_ts)
                return df[mask].copy(), f"Filtro aplicado por {col}"

    # Se não achou nenhuma data útil, não corta a base.
    return df.copy(), "sem coluna de data disponível — exibindo tudo que está aberto"




def operational_card(label, value, subtitle, icon, accent, soft, card_key=None):
    st.markdown(
        f"""            <div class="clickable-card-wrap">
                <article class="ops-card" style="--accent:{accent}; --soft:{soft};">
                    <header>
                        <div class="ops-icon">{icon}</div>
                        <div class="ops-label">{label}</div>
                    </header>
                    <main class="ops-card-main">
                        <div class="ops-value">{value}</div>
                        <div class="ops-sub">{subtitle}</div>
                    </main>
                    <footer class="ops-card-footer">Visualizar detalhes →</footer>
                </article>
            </div>
        """,
        unsafe_allow_html=True,
    )


def pendencia_operational_card(total, entradas, saidas, saldo, card_key=None):
    saldo_txt = f"+{saldo}" if saldo > 0 else str(saldo)
    saldo_color = "#d97706" if saldo > 0 else "#0f766e"
    st.markdown(
        f"""            <div class="clickable-card-wrap">
                <article class="ops-card" style="--accent:#b7791f; --soft:#fff8e1;">
                    <header>
                        <div class="ops-icon">Σ</div>
                        <div class="ops-label">Pendências da Torre</div>
                    </header>
                    <main class="ops-card-main">
                        <div class="ops-value">{total}</div>
                        <div class="ops-sub">Backlog atual da Torre</div>
                        <section class="ops-mini-grid">
                            <div class="ops-mini">
                                <div class="ops-mini-title">Entraram hoje</div>
                                <div class="ops-mini-value" style="--mini-color:#d92d20;">{entradas}</div>
                            </div>
                            <div class="ops-mini">
                                <div class="ops-mini-title">Saíram hoje</div>
                                <div class="ops-mini-value" style="--mini-color:#0f766e;">{saidas}</div>
                            </div>
                            <div class="ops-mini">
                                <div class="ops-mini-title">Saldo do dia</div>
                                <div class="ops-mini-value" style="--mini-color:{saldo_color};">{saldo_txt}</div>
                            </div>
                        </section>
                    </main>
                    <footer class="ops-card-footer">Visualizar detalhes →</footer>
                </article>
            </div>
        """,
        unsafe_allow_html=True,
    )


def acareacao_operational_card(qtd, valor, vencendo_hoje, card_key=None):
    st.markdown(
        f"""            <div class="clickable-card-wrap">
                <article class="ops-card" style="--accent:#0b63ce; --soft:#eaf3ff;">
                    <header>
                        <div class="ops-icon">▤</div>
                        <div class="ops-label">Acareações</div>
                    </header>
                    <main class="ops-card-main">
                        <div class="ops-value">{qtd}</div>
                        <div class="ops-sub">Solicitações de comprovação em aberto</div>
                        <section class="ops-mini-grid">
                            <div class="ops-mini">
                                <div class="ops-mini-title">Valor</div>
                                <div class="ops-mini-value" style="--mini-color:#08254e;">{valor}</div>
                            </div>
                            <div class="ops-mini">
                                <div class="ops-mini-title">Vencem hoje</div>
                                <div class="ops-mini-value" style="--mini-color:#d92d20;">{vencendo_hoje}</div>
                            </div>
                            <div class="ops-mini">
                                <div class="ops-mini-title">Status</div>
                                <div class="ops-mini-value" style="--mini-color:#0b63ce;">aberto</div>
                            </div>
                        </section>
                    </main>
                    <footer class="ops-card-footer">Visualizar detalhes →</footer>
                </article>
            </div>
        """,
        unsafe_allow_html=True,
    )



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



def looks_like_date_column(col_name):
    col_norm = normalize_text(col_name)
    date_tokens = [
        "DATA",
        "DT",
        "SLA",
        "PREVISAO",
        "PREVISÃO",
        "ROTA",
        "ALTERACAO",
        "ALTERAÇÃO",
        "EXECUTADA",
        "VOO",
        "EMISSAO",
        "EMISSÃO",
    ]
    return any(token in col_norm for token in date_tokens)


def format_excel_date_columns(writer, df, sheet_name):
    """
    Padroniza colunas de data no Excel para DD/MM/AAAA.
    Não altera o dataframe original nem as regras do painel.
    """
    if df is None or df.empty:
        return

    ws = writer.sheets.get(str(sheet_name)[:31])
    if ws is None:
        return

    for col_idx, col_name in enumerate(df.columns, start=1):
        if not looks_like_date_column(col_name):
            continue

        # Tenta converter a coluna para datas apenas para identificar se faz sentido formatar.
        converted = pd.to_datetime(df[col_name], errors="coerce", dayfirst=True)
        if converted.notna().sum() == 0:
            continue

        for row_idx in range(2, len(df) + 2):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value in [None, ""]:
                continue
            cell.number_format = "DD/MM/YYYY"


def excel_bytes(df, sheet_name="DADOS"):
    output = io.BytesIO()
    safe_df = df.copy() if df is not None else pd.DataFrame()
    sheet = str(sheet_name)[:31]

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        safe_df.to_excel(writer, sheet_name=sheet, index=False)
        format_excel_date_columns(writer, safe_df, sheet)

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


def edi_reference_date():
    """
    Usa a data final do filtro lateral como data de análise do EDI.
    Fallback: período do resumo ou data atual.
    """
    try:
        dr = globals().get("date_range")
        if isinstance(dr, (list, tuple)) and len(dr) == 2 and dr[1] is not None:
            return pd.Timestamp(dr[1]).normalize()
    except Exception:
        pass

    try:
        periodo_txt = str(globals().get("periodo", "")).strip()
        parsed = pd.to_datetime(periodo_txt, errors="coerce")
        if pd.notna(parsed):
            return pd.Timestamp(parsed).normalize()
    except Exception:
        pass

    return pd.Timestamp(date.today()).normalize()


def edi_sla_series(df):
    if df is None or df.empty:
        return pd.Series(pd.NaT, index=df.index if df is not None else None)

    sla_col = first_col(df, ["SLA", "PREVISAO", "PREVISÃO", "DATA SLA", "DT SLA"])
    if not sla_col:
        return pd.Series(pd.NaT, index=df.index)

    return parse_date_col(df[sla_col]).dt.normalize()


def edi_rows_embarque_atrasado(df):
    """
    Pendente de embarque EDI dos dias anteriores.
    Não entra SLA do dia atual.
    """
    data = edi_rows(df, "PENDENTE DE EMBARQUE")
    if data is None or data.empty:
        return pd.DataFrame()

    ref = edi_reference_date()
    sla = edi_sla_series(data)

    if sla.notna().any():
        data = data[sla.lt(ref)].copy()
    elif "STATUS_SLA" in data.columns:
        status = data["STATUS_SLA"].astype(str).map(normalize_text)
        data = data[status.eq("SLA VENCIDO")].copy()
    else:
        data = pd.DataFrame()

    return data


def edi_rows_entrega_destino_sla(df):
    """
    Cargas pendentes de entrega no destino, por SLA.
    Mantém SLA vencido e SLA do dia.
    """
    data = edi_rows(df, "ENTREGA NO DESTINO PELO SLA")
    if data is None or data.empty:
        return pd.DataFrame()

    ref = edi_reference_date()
    sla = edi_sla_series(data)

    if sla.notna().any():
        data = data[sla.le(ref)].copy()
    elif "STATUS_SLA" in data.columns:
        status = data["STATUS_SLA"].astype(str).map(normalize_text)
        data = data[status.isin(["SLA VENCIDO", "SLA HOJE"])].copy()

    return data


def edi_rows_desembarque(df):
    """
    Pendente desembarque EDI.

    Regra:
    - Entra somente o que estiver classificado como PENDENTE DE DESEMBARQUE.
    - Remove entregue/baixado.
    - Remove discrepância.
    - Remove pendente de embarque / Bag Create.
    - Remove entrega destino / SLA.
    """
    data = edi_rows(df, "PENDENTE DE DESEMBARQUE")

    if data is None or data.empty:
        return pd.DataFrame()

    data = data.copy()

    # Junta colunas textuais relevantes para identificar falsos positivos.
    text_cols = [
        "INDICADOR",
        "STATUS",
        "STATUS_EN",
        "STATUS EN",
        "STATUS_SLA",
        "STATUS SLA",
        "SITUACAO",
        "SITUAÇÃO",
        "OCORRENCIA",
        "OCORRÊNCIA",
        "EVENTO",
        "DESCRICAO",
        "DESCRIÇÃO",
    ]

    texto = pd.Series("", index=data.index, dtype="object")
    for col in text_cols:
        if col in data.columns:
            texto = texto + " " + data[col].fillna("").astype(str)

    texto_norm = texto.map(normalize_text)

    # Flags estruturadas quando existirem.
    ja_entregue_col = first_col(data, ["JA_ENTREGUE", "JÁ ENTREGUE", "ENTREGUE", "BAIXADO"])
    bag_create_col = first_col(data, ["BAG_CREATE", "BAG CREATE"])
    indicador_col = first_col(data, ["INDICADOR"])

    if ja_entregue_col:
        ja_entregue = data[ja_entregue_col].fillna(False).astype(str).str.strip().str.lower().isin(
            ["true", "1", "sim", "yes", "y", "verdadeiro", "entregue", "baixado"]
        )
    else:
        ja_entregue = pd.Series(False, index=data.index)

    if bag_create_col:
        bag_create = data[bag_create_col].fillna(False).astype(str).str.strip().str.lower().isin(
            ["true", "1", "sim", "yes", "y", "verdadeiro"]
        )
    else:
        bag_create = pd.Series(False, index=data.index)

    if indicador_col:
        indicador_norm = data[indicador_col].fillna("").astype(str).map(normalize_text)
    else:
        indicador_norm = pd.Series("", index=data.index, dtype="object")

    entregue_ou_baixado = ja_entregue | texto_norm.str.contains(
        "ENTREGUE|BAIXAD|FINALIZAD|CONCLUID|DELIVERED|ENTREGA REALIZADA",
        regex=True,
        na=False,
    )

    discrepancia = indicador_norm.str.contains("DISCREP", regex=True, na=False) | texto_norm.str.contains(
        "DISCREP",
        regex=True,
        na=False,
    )

    pendente_embarque = bag_create | indicador_norm.str.contains(
        "PENDENTE DE EMBARQUE|PENDENTE EMBARQUE|EMBARQUE",
        regex=True,
        na=False,
    ) | texto_norm.str.contains(
        "PENDENTE DE EMBARQUE|PENDENTE EMBARQUE|BAG CREATE|BAGCREATE|AGUARDANDO EMBARQUE",
        regex=True,
        na=False,
    )

    entrega_destino = indicador_norm.str.contains(
        "ENTREGA NO DESTINO|ENTREGA DESTINO|ENTREGA.*SLA",
        regex=True,
        na=False,
    )

    # Mantém apenas o desembarque real.
    data = data[
        (~entregue_ou_baixado)
        & (~discrepancia)
        & (~pendente_embarque)
        & (~entrega_destino)
    ].copy()

    # Prioriza colunas úteis no detalhe.
    preferred = [
        "AWB",
        "STATUS_EMAIL",
        "STATUS EMAIL",
        "CLIENTE",
        "BASE",
        "OPS_STATION",
        "OPS STATION",
        "DESTINO",
        "FLTDESTINATION",
        "FLT DESTINATION",
        "INDICADOR",
        "SLA",
        "STATUS_EN",
        "STATUS EN",
        "STATUS_SLA",
        "STATUS SLA",
        "BAG_CREATE",
        "BAG CREATE",
        "JA_ENTREGUE",
        "JÁ ENTREGUE",
    ]
    cols = [c for c in preferred if c in data.columns]
    remaining = [c for c in data.columns if c not in cols]
    return data[cols + remaining].copy() if cols else data




def edi_resumo_desembarque_onde_esta(df):
    data = edi_rows_desembarque(df)
    if data is None or data.empty:
        return pd.DataFrame()

    ops_col = first_col(data, ["OPS_STATION", "OPS STATION", "ESTA_EM", "ESTÁ EM"])
    destino_col = first_col(data, ["DESTINO", "FLTDESTINATION", "FLT DESTINATION"])
    base_col = first_col(data, ["BASE"])
    awb_col = first_col(data, ["AWB"])

    group_cols = []
    rename_map = {}

    if ops_col:
        group_cols.append(ops_col)
        rename_map[ops_col] = "ONDE ESTÁ"
    if destino_col:
        group_cols.append(destino_col)
        rename_map[destino_col] = "DESTINO"
    if base_col:
        group_cols.append(base_col)
        rename_map[base_col] = "BASE"

    if not group_cols:
        return pd.DataFrame()

    if awb_col:
        resumo = (
            data.groupby(group_cols, dropna=False)
            .agg(QTDE_AWBS=(awb_col, "nunique"))
            .reset_index()
        )
    else:
        resumo = (
            data.groupby(group_cols, dropna=False)
            .size()
            .reset_index(name="QTDE_AWBS")
        )

    return (
        resumo.rename(columns=rename_map)
        .sort_values("QTDE_AWBS", ascending=False)
        .reset_index(drop=True)
    )


def edi_count_df(data):
    if data is None or data.empty:
        return 0

    if "AWB" in data.columns:
        awbs = data["AWB"].fillna("").astype(str).str.strip()
        awbs = awbs[awbs.ne("")]
        return int(awbs.nunique()) if not awbs.empty else int(len(data))

    return int(len(data))


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
        "edi_entrega_sla": {
            "title": "EDI — Pendente entrega destino / SLA",
            "subtitle": "Cargas pendentes de entrega no destino com SLA vencido ou SLA do dia.",
            "df": edi_rows_entrega_destino_sla(edi_detalhe),
            "sheet": "ENTREGA_DESTINO",
        },
        "edi_emb_atrasado": {
            "title": "EDI — Pendente embarque atrasado",
            "subtitle": "Pendente de embarque apenas dos dias anteriores. SLA do dia atual não entra.",
            "df": edi_rows_embarque_atrasado(edi_detalhe),
            "sheet": "EMBARQUE_ATRASADO",
        },
        "edi_discrepancia": {
            "title": "EDI — Discrepância",
            "subtitle": "Divergências classificadas no First Mile.",
            "df": edi_rows(edi_detalhe, "DISCREPÂNCIA"),
            "sheet": "DISCREPANCIA",
        },
        "edi_desembarque": {
            "title": "EDI — Pendente desembarque",
            "subtitle": "Somente cargas realmente pendentes de desembarque. Exclui entregue, baixado, discrepância e embarque.",
            "df": edi_rows_desembarque(edi_detalhe),
            "sheet": "DESEMBARQUE",
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
            st.session_state["bi_detail_card"] = ""
            st.rerun()

    if card_key == "edi_desembarque":
        st.markdown("#### Resumo — onde está")
        resumo_onde = edi_resumo_desembarque_onde_esta(edi_detalhe)
        render_table(resumo_onde, height=260)

        st.markdown("#### Detalhe por AWB")
        render_table(df, height=500)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            resumo_onde.to_excel(writer, sheet_name="RESUMO_ONDE_ESTA", index=False)
            format_excel_date_columns(writer, resumo_onde, "RESUMO_ONDE_ESTA")

            df.to_excel(writer, sheet_name="DETALHE_AWB", index=False)
            format_excel_date_columns(writer, df, "DETALHE_AWB")

        output.seek(0)

        st.download_button(
            "Baixar Excel deste card",
            output.getvalue(),
            file_name="edi_pendente_desembarque_onde_esta.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        return

    render_table(df, height=500)
    st.download_button(
        "Baixar Excel deste card",
        excel_bytes(df, sheet_name=item["sheet"]),
        file_name=f"{safe_filename(item['title'])}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def bi_rows(df, resultado=None, base=None):
    if df is None or df.empty:
        return pd.DataFrame()

    data = df.copy()

    if resultado and "RESULTADO_CONFERENCIA" in data.columns:
        data = data[data["RESULTADO_CONFERENCIA"].astype(str).eq(resultado)]

    if base:
        base_cols = [c for c in ["BASE_BI", "BASE_EDI"] if c in data.columns]
        if base_cols:
            mask = pd.Series(False, index=data.index)
            for col in base_cols:
                mask = mask | data[col].astype(str).str.upper().eq(str(base).upper())
            data = data[mask]

    return data.copy()


def bi_count(df, resultado=None, base=None):
    data = bi_rows(df, resultado=resultado, base=base)
    if data.empty:
        return 0
    if "AWB" in data.columns:
        awbs = data["AWB"].fillna("").astype(str).str.strip()
        awbs = awbs[awbs.ne("")]
        return int(awbs.nunique()) if not awbs.empty else int(len(data))
    return int(len(data))


def render_bi_card_detail(card_key):
    mapping = {
        "bi_tres1": {
            "title": "BI Azul — TRES1",
            "subtitle": "Relatório Power BI Azul filtrado para TRES1.",
            "df": bi_rows(bi_azul_detalhe, base="TRES1"),
            "sheet": "BI_TRES1",
        },
        "bi_sao12": {
            "title": "BI Azul — SAO12",
            "subtitle": "Relatório Power BI Azul filtrado para SAO12.",
            "df": bi_rows(bi_azul_detalhe, base="SAO12"),
            "sheet": "BI_SAO12",
        },
        "bi_cdsp2": {
            "title": "BI Azul — CDSP2",
            "subtitle": "Relatório Power BI Azul filtrado para CDSP2.",
            "df": bi_rows(bi_azul_detalhe, base="CDSP2"),
            "sheet": "BI_CDSP2",
        },
        "bi_divergentes": {
            "title": "BI Azul — Divergências",
            "subtitle": "AWBs com divergência entre BI Azul e EDI.",
            "df": bi_azul_conferencia[
                ~bi_azul_conferencia["RESULTADO_CONFERENCIA"].astype(str).eq("OK")
            ].copy() if bi_azul_conferencia is not None and not bi_azul_conferencia.empty and "RESULTADO_CONFERENCIA" in bi_azul_conferencia.columns else pd.DataFrame(),
            "sheet": "DIVERGENCIAS",
        },
        "bi_no_bi_nao_edi": {
            "title": "BI Azul — No BI e não no EDI",
            "subtitle": "AWBs cobradas no BI que não apareceram no EDI.",
            "df": bi_rows(bi_azul_conferencia, resultado="NO BI E NÃO NO EDI"),
            "sheet": "BI_NAO_EDI",
        },
        "bi_no_edi_nao_bi": {
            "title": "BI Azul — No EDI e não no BI",
            "subtitle": "AWBs do EDI que não apareceram no BI.",
            "df": bi_rows(bi_azul_conferencia, resultado="NO EDI E NÃO NO BI"),
            "sheet": "EDI_NAO_BI",
        },
        "bi_resumo": {
            "title": "BI Azul — Resumo",
            "subtitle": "Resumo por base enviada.",
            "df": bi_azul_resumo.copy() if bi_azul_resumo is not None else pd.DataFrame(),
            "sheet": "RESUMO_BI",
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
        if st.button("Fechar detalhe", key="fechar_bi_detail", use_container_width=True):
            st.session_state["bi_detail_card"] = ""
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

    df = df.copy()
    if "STATUS_EMAIL" in df.columns and "STATUS EMAIL" not in df.columns:
        df = df.rename(columns={"STATUS_EMAIL": "STATUS EMAIL"})

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


def truthy_series(series, index=None):
    if series is None:
        return pd.Series(False, index=index)

    return series.fillna(False).astype(str).str.strip().str.lower().isin(
        ["true", "1", "sim", "yes", "y", "verdadeiro"]
    )


def entregue_eu_entrego_pendente_sk_rows(df):
    """
    Cargas que constam como entregues/fechadas/baixadas no Eu Entrego,
    mas continuam como PENDENTE ENTREGA no SK.

    Esta função precisa existir antes de overdue_delivery_rows,
    porque o backlog usa ela para remover sobreposição.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    data = df.copy()

    flag_col = first_col(data, [
        "EU ENTREGO BAIXADO ENTREGUE",
        "EU_ENTREGO_BAIXADO_ENTREGUE",
        "BAIXADO EU ENTREGO",
    ])

    status_col = first_col(data, [
        "STATUS ÚLTIMA ROTA",
        "STATUS ULTIMA ROTA",
        "STATUS_ULTIMA_ROTA",
    ])

    motivo_col = first_col(data, [
        "MOTIVO ÚLTIMA ROTA",
        "MOTIVO ULTIMA ROTA",
        "MOTIVO_ULTIMA_ROTA",
    ])

    analise_col = first_col(data, [
        "STATUS ANALISE EU ENTREGO",
        "EU_ENTREGO_STATUS_ANALISE",
    ])

    mask_flag = (
        truthy_series(data[flag_col], index=data.index)
        if flag_col
        else pd.Series(False, index=data.index)
    )

    texto = pd.Series("", index=data.index, dtype="object")
    for col in [status_col, motivo_col, analise_col]:
        if col:
            texto = texto + " " + data[col].fillna("").astype(str)

    texto_norm = texto.map(normalize_text)

    status_eu_norm = (
        data[status_col].fillna("").astype(str).map(normalize_text)
        if status_col
        else pd.Series("", index=data.index, dtype="object")
    )

    fechada_status = status_eu_norm.str.fullmatch(
        r"FECHAD[AO]?|FECHADA|FECHADO",
        na=False,
    )

    entregue = mask_flag | fechada_status | texto_norm.str.contains(
        "ENTREGUE|ENTREGA REALIZADA|BAIXAD|FINALIZAD|CONCLUID|SUCESSO|DELIVERED",
        regex=True,
        na=False,
    )

    negativo = texto_norm.str.contains(
        "INSUCESS|NAO ENTREG|NÃO ENTREG|AUSENTE|RECUS|DEVOLVID|RETORN|CANCELAD|EXTRAVI",
        regex=True,
        na=False,
    )

    status_sk_col = first_col(data, [
        "STATUS SK",
        "STATUS_SISTEMA",
        "STATUS SISTEMA",
    ])

    sk_flag_col = first_col(data, [
        "SK PENDENTE ENTREGA",
        "SK_PENDENTE_ENTREGA",
    ])

    sk_flag = (
        truthy_series(data[sk_flag_col], index=data.index)
        if sk_flag_col
        else pd.Series(False, index=data.index)
    )

    if status_sk_col:
        status_sk_norm = data[status_sk_col].fillna("").astype(str).map(normalize_text)
        sk_pendente = sk_flag | status_sk_norm.str.contains(
            "PENDENTE ENTREGA|PENDENTE DE ENTREGA",
            regex=True,
            na=False,
        )
    else:
        sk_pendente = sk_flag

    out = data[sk_pendente & entregue & (~negativo)].copy()

    preferred = [
        "AWB",
        "CLIENTE",
        "STATUS SK",
        "SITUAÇÃO",
        "PROBLEMA",
        "SLA",
        "DIAS EM ATRASO",
        "STATUS ÚLTIMA ROTA",
        "MOTIVO ÚLTIMA ROTA",
        "ÚLTIMA ROTA",
        "ÚLTIMA ALTERAÇÃO",
        "EXECUTADA EU ENTREGO",
        "STATUS ANALISE EU ENTREGO",
        "STATUS ROTA EU ENTREGO NORMALIZADO",
        "EU ENTREGO BAIXADO ENTREGUE",
        "LOCALIZAÇÃO / RESPONSÁVEL",
        "TRATATIVA ESPECIAL",
    ]

    cols = [c for c in preferred if c in out.columns]
    return out[cols].copy() if cols else out


def backlog_baixado_eu_entrego_rows(df):
    # Compatibilidade com versões anteriores.
    return entregue_eu_entrego_pendente_sk_rows(df)


def _awb_norm_for_match(value):
    return re.sub(r"\D+", "", str(value or "").strip())


def _extract_awb_set_from_df(df):
    """
    Extrai AWBs de um dataframe mesmo quando a coluna de AWB
    veio com nome diferente ou preservada como ORIG_*.
    """
    if df is None or df.empty:
        return set()

    data = df.copy()

    preferred_cols = [
        "AWB",
        "Nº AWB",
        "NUMERO AWB",
        "NÚMERO AWB",
        "AWB NUMBER",
        "AWBNumber",
    ]

    cols_to_try = []
    awb_col = first_col(data, preferred_cols)
    if awb_col:
        cols_to_try.append(awb_col)

    # Também verifica colunas originais preservadas.
    for col in data.columns:
        col_norm = normalize_text(str(col))
        if "AWB" in col_norm and col not in cols_to_try:
            cols_to_try.append(col)

    # Fallback: escolhe colunas que tenham bastante valor normalizável como AWB.
    if not cols_to_try:
        scored = []
        for col in data.columns:
            norm_values = data[col].fillna("").astype(str).map(_awb_norm_for_match)
            count = int(norm_values.str.len().between(7, 12).sum())
            if count > 0:
                scored.append((count, col))

        scored = sorted(scored, reverse=True)
        cols_to_try = [col for _, col in scored[:2]]

    awbs = set()
    for col in cols_to_try:
        values = (
            data[col]
            .fillna("")
            .astype(str)
            .map(_awb_norm_for_match)
        )
        awbs.update(
            values.loc[values.str.len().between(7, 12)].tolist()
        )

    return {awb for awb in awbs if awb}


def avaria_awbs_set():
    """
    AWBs que estão na planilha de Avarias / Salvados.
    Prioridade:
    1. Aba sincronizada AVARIAS_DETALHE.
    2. Dataframe avaria_df já calculado na tela.
    """
    frames = []

    if "avarias_detalhe" in globals() and avarias_detalhe is not None and not avarias_detalhe.empty:
        frames.append(avarias_detalhe)

    if "avaria_df" in globals() and avaria_df is not None and not avaria_df.empty:
        frames.append(avaria_df)

    awbs = set()
    for frame in frames:
        awbs.update(_extract_awb_set_from_df(frame))

    return awbs



def filter_qualidade_pendente_rows(df):
    """
    No gerente, protege bases antigas:
    só linhas com RETORNO_QUALIDADE = PENDENTE entram no card
    e nas exclusões de backlog/pendente entrega.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    data = df.copy()
    retorno_col = first_col(data, [
        "RETORNO_QUALIDADE",
        "RETORNO QUALIDADE",
        "RETORNO DA QUALIDADE",
        "RETORNO",
        "STATUS RETORNO",
    ])

    if not retorno_col:
        return pd.DataFrame(columns=data.columns)

    retorno_norm = data[retorno_col].fillna("").astype(str).map(normalize_text)
    return data[retorno_norm.eq("PENDENTE")].copy()


def qualidade_awbs_set():
    """
    AWBs que estão na planilha de Qualidade com RETORNO_QUALIDADE = PENDENTE.
    Essas AWBs não devem aparecer no backlog/pendente entrega.
    """
    frames = []

    if "qualidade_detalhe" in globals() and qualidade_detalhe is not None and not qualidade_detalhe.empty:
        frames.append(filter_qualidade_pendente_rows(qualidade_detalhe))

    awbs = set()
    for frame in frames:
        awbs.update(_extract_awb_set_from_df(frame))

    return awbs


def aguardando_qualidade_rows(df):
    """
    Linhas classificadas como AGUARDANDO RETORNO DA QUALIDADE.
    Também cruza por AWB com QUALIDADE_DETALHE para proteger bases antigas.
    """
    frames = []

    if df is not None and not df.empty:
        data = df.copy()
        problema_col = first_col(data, ["PROBLEMA"])
        if problema_col:
            problema = data[problema_col].astype(str).map(normalize_text)
            part = data[problema.eq("AGUARDANDO RETORNO DA QUALIDADE")].copy()
            if not part.empty:
                frames.append(part)

        q_awbs = qualidade_awbs_set()
        if q_awbs and "AWB" in data.columns:
            awb_norm = (
                data["AWB"]
                .fillna("")
                .astype(str)
                .map(lambda x: re.sub(r"\D+", "", str(x)))
            )
            part = data[awb_norm.isin(q_awbs)].copy()
            if not part.empty:
                frames.append(part)

    # Caso não esteja na FILA, mostra o detalhe direto da Qualidade,
    # mas somente RETORNO_QUALIDADE = PENDENTE.
    if "qualidade_detalhe" in globals() and qualidade_detalhe is not None and not qualidade_detalhe.empty:
        q = filter_qualidade_pendente_rows(qualidade_detalhe)
        if q is not None and not q.empty:
            if "PROBLEMA" not in q.columns:
                q["PROBLEMA"] = "AGUARDANDO RETORNO DA QUALIDADE"
            frames.append(q)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True, sort=False)
    if "AWB" in out.columns:
        out["_AWB_NORM"] = out["AWB"].fillna("").astype(str).map(lambda x: re.sub(r"\D+", "", str(x)))
        out = out.drop_duplicates("_AWB_NORM", keep="first").drop(columns=["_AWB_NORM"], errors="ignore")

    return out



def overdue_delivery_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    problema_col = first_col(df, ["PROBLEMA"])
    if problema_col:
        problema = df[problema_col].astype(str).map(normalize_text)
        data = df[problema.eq("ENTREGA EM ATRASO")].copy()
    else:
        data = filter_terms(df, ["ENTREGA EM ATRASO", "ATRASO DE ENTREGA"])

    if data is None or data.empty:
        return pd.DataFrame()

    # Regra de não sobreposição:
    # Se Eu Entrego está Fechada/Entregue e SK está PENDENTE ENTREGA,
    # a carga pertence ao card "Entregue Eu Entrego x SK", não ao backlog.
    eu_sk = entregue_eu_entrego_pendente_sk_rows(data) if "entregue_eu_entrego_pendente_sk_rows" in globals() else pd.DataFrame()
    if eu_sk is not None and not eu_sk.empty and "AWB" in eu_sk.columns and "AWB" in data.columns:
        awbs_eu_sk = set(
            eu_sk["AWB"]
            .dropna()
            .astype(str)
            .str.strip()
            .map(lambda x: re.sub(r"\D+", "", x))
            .loc[lambda s: s.ne("")]
        )
        data_awb_norm = (
            data["AWB"]
            .fillna("")
            .astype(str)
            .str.strip()
            .map(lambda x: re.sub(r"\D+", "", x))
        )
        data = data[~data_awb_norm.isin(awbs_eu_sk)].copy()

    # Regra de não sobreposição com Avarias / Salvados:
    # Se está na planilha de avaria, não compõe o backlog de atraso.
    # Exemplo: AWB 84702015.
    avaria_awbs = avaria_awbs_set() if "avaria_awbs_set" in globals() else set()
    if avaria_awbs and "AWB" in data.columns:
        data_awb_norm = (
            data["AWB"]
            .fillna("")
            .astype(str)
            .str.strip()
            .map(lambda x: re.sub(r"\D+", "", x))
        )
        data = data[~data_awb_norm.isin(avaria_awbs)].copy()

    # Regra de não sobreposição com Qualidade:
    # Se está aguardando retorno da Qualidade, não compõe backlog.
    qualidade_awbs = qualidade_awbs_set() if "qualidade_awbs_set" in globals() else set()
    if qualidade_awbs and "AWB" in data.columns:
        data_awb_norm = (
            data["AWB"]
            .fillna("")
            .astype(str)
            .str.strip()
            .map(lambda x: re.sub(r"\D+", "", x))
        )
        data = data[~data_awb_norm.isin(qualidade_awbs)].copy()

    return data




def insucesso_sem_pendencia_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    data = df.copy()
    problema_col = first_col(data, ["PROBLEMA"])

    if problema_col:
        problema = data[problema_col].astype(str).map(normalize_text)
        data = data[problema.eq("INSUCESSO SEM PENDÊNCIA")].copy()
    else:
        data = filter_terms(data, [
            "INSUCESSO SEM PENDÊNCIA",
            "INSUCESSO SEM PENDENCIA",
            "DESTINATÁRIO DESCONHECIDO",
            "DESTINATARIO DESCONHECIDO",
            "ENDEREÇO NÃO LOCALIZADO",
            "ENDERECO NAO LOCALIZADO",
        ])

    return data.copy() if data is not None else pd.DataFrame()


def pendencia_ativa_awbs():
    """
    Retorna AWBs que estão na pendência ativa da Torre,
    usando a aba PENDENCIA_MOVIMENTOS quando disponível.
    """
    df = pendencia_movimentos if "pendencia_movimentos" in globals() else pd.DataFrame()

    if df is None or df.empty or "AWB" not in df.columns:
        return set()

    data = df.copy()

    if "TIPO_MOVIMENTO" in data.columns:
        tipo = data["TIPO_MOVIMENTO"].astype(str).map(normalize_text)
        awbs = data.loc[
            tipo.eq("TOTAL NA PENDÊNCIA") | tipo.eq("TOTAL NA PENDENCIA"),
            "AWB"
        ]
    elif "EVENTO_TORRE" in data.columns:
        evento = data["EVENTO_TORRE"].astype(str).map(normalize_text)
        awbs = data.loc[evento.isin(["PENDENCIA", "PENDENCIA_CORP"]), "AWB"]
    else:
        awbs = data["AWB"]

    return set(
        awbs.dropna()
        .astype(str)
        .str.strip()
        .map(lambda x: re.sub(r"\D+", "", x))
        .loc[lambda s: s.ne("")]
    )


def remove_pendencia_from_rows(df):
    """
    Remove AWBs que estão na pendência da Torre.
    Usado principalmente no card SLA do dia sem rota.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    data = df.copy()

    # 1) Remove por evento explícito da Torre na própria FILA.
    evento_col = first_col(data, ["EVENTO TORRE", "EVENTO_TORRE"])
    if evento_col:
        evento = data[evento_col].fillna("").astype(str).map(normalize_text)
        data = data[~evento.isin(["PENDENCIA", "PENDENCIA_CORP"])].copy()

    # 2) Remove por flags booleanas de pendência.
    for flag_name in [
        "EM TORRE ATIVA",
        "EM_TORRE_ATIVA",
        "NA PENDENCIA TORRE LINK",
        "NA_PENDENCIA_TORRE_LINK",
    ]:
        flag_col = first_col(data, [flag_name])
        if flag_col:
            flags = data[flag_col].fillna(False).astype(str).str.strip().str.lower().isin(
                ["true", "1", "sim", "yes", "y", "verdadeiro"]
            )
            data = data[~flags].copy()

    # 3) Remove cruzando AWB contra a aba PENDENCIA_MOVIMENTOS / TOTAL NA PENDÊNCIA.
    awb_col = first_col(data, ["AWB"])
    pend_awbs = pendencia_ativa_awbs()

    if awb_col and pend_awbs:
        awbs_norm = (
            data[awb_col]
            .fillna("")
            .astype(str)
            .str.strip()
            .map(lambda x: re.sub(r"\D+", "", x))
        )
        data = data[~awbs_norm.isin(pend_awbs)].copy()

    return data


def sla_sem_rota_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    problema_col = first_col(df, ["PROBLEMA"])
    if problema_col:
        problema = df[problema_col].astype(str).map(normalize_text)
        exact = df[problema.eq("SLA DO DIA SEM ROTA")].copy()
        if not exact.empty:
            return remove_pendencia_from_rows(exact)

    filtered = filter_terms(df, ["SLA DO DIA SEM ROTA", "SLA SEM ROTA"])
    return remove_pendencia_from_rows(filtered)




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

    if "STATUS_EMAIL" in out.columns and "STATUS EMAIL" not in out.columns:
        out = out.rename(columns={"STATUS_EMAIL": "STATUS EMAIL"})

    preferred = [
        "TIPO_MOVIMENTO",
        "AWB",
        "STATUS_EMAIL",
        "STATUS EMAIL",
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


def avaria_rows(df):
    # Prioriza a aba própria da planilha Pendências da Torre.
    sheet = avarias_detalhe if "avarias_detalhe" in globals() else pd.DataFrame()
    if sheet is not None and not sheet.empty:
        data = sheet.copy()

        preferred = [
            "ORIGEM_AVARIA",
            "ABA_ORIGEM",
            "AWB",
            "CLIENTE",
            "STATUS",
            "MOTIVO",
            "DATA",
            "VALOR",
            "VALOR_NUM",
            "RESPONSAVEL",
            "NF",
            "PEDIDO",
        ]
        orig_cols = [c for c in data.columns if str(c).startswith("ORIG_")]

        # Se AWB/CLIENTE vierem vazios por nome de coluna diferente, exibe também as colunas originais.
        cols = [c for c in preferred if c in data.columns] + orig_cols

        if cols:
            out = data[cols].copy()
        else:
            out = data.copy()

        # Remove colunas 100% vazias para melhorar leitura, mas preserva ORIG úteis.
        non_empty_cols = []
        for col in out.columns:
            s = out[col]
            if s.notna().any() and not s.astype(str).str.strip().eq("").all():
                non_empty_cols.append(col)

        return out[non_empty_cols].copy() if non_empty_cols else out

    # Fallback antigo: busca na FILA.
    if df is None or df.empty:
        return pd.DataFrame()

    problema_col = first_col(df, ["PROBLEMA", "PENDÊNCIA", "PENDENCIA", "MOTIVO"])
    if problema_col:
        problema = df[problema_col].astype(str).map(normalize_text)
        exact = df[problema.str.contains("AVARIA", na=False)].copy()
        if not exact.empty:
            return exact

    return filter_terms(df, ["AVARIA", "DANIFICAD", "QUEBRAD", "RESSALVA", "SALVADO"])


def acareacao_rows_prefer_sheet(fila_df):
    sheet = acareacoes_detalhe if "acareacoes_detalhe" in globals() else pd.DataFrame()
    if sheet is not None and not sheet.empty:
        data = sheet.copy()

        preferred = [
            "AWB",
            "CLIENTE",
            "ENTREGADOR",
            "VALOR",
            "VALOR_NUM",
            "STATUS",
            "TIPO",
            "OBSERVACAO",
            "DATA",
            "NF",
            "PEDIDO",
        ]
        orig_cols = [c for c in data.columns if str(c).startswith("ORIG_")]
        cols = [c for c in preferred if c in data.columns] + orig_cols
        out = data[cols].copy() if cols else data.copy()

        non_empty_cols = []
        for col in out.columns:
            s = out[col]
            if s.notna().any() and not s.astype(str).str.strip().eq("").all():
                non_empty_cols.append(col)
        return out[non_empty_cols].copy() if non_empty_cols else out

    return acareacao_rows(fila_df)


def acareacao_driver_summary_prefer_sheet(fila_df):
    df = acareacao_rows_prefer_sheet(fila_df)
    if df is None or df.empty:
        return pd.DataFrame()

    driver_col = first_col(df, [
        "ACAREACAO ENTREGADOR",
        "ENTREGADOR",
        "MOTORISTA",
        "NOME ENTREGADOR",
        "NOME DO ENTREGADOR",
        "NOME MOTORISTA",
        "RESPONSAVEL",
        "RESPONSÁVEL",
        "RESPONSAVEL TRATATIVA",
    ])

    if not driver_col:
        for col in df.columns:
            col_norm = normalize_text(col)
            if any(token in col_norm for token in ["ENTREGADOR", "MOTORISTA", "RESPONSAVEL", "DRIVER"]):
                driver_col = col
                break

    value_col = find_value_column_flexible(df)

    if not driver_col:
        return pd.DataFrame({
            "ENTREGADOR": ["Coluna de entregador não localizada"],
            "QTDE": [len(df)],
            "VALOR_TOTAL": [acareacao_total_value(df)],
        })

    base = df.copy()
    base["_ENTREGADOR"] = base[driver_col].fillna("Não informado").astype(str).str.strip()
    base["_ENTREGADOR"] = base["_ENTREGADOR"].replace("", "Não informado")
    base["_VALOR"] = money_series_flexible(base[value_col]) if value_col else 0

    count_col = "AWB" if "AWB" in base.columns else "_ENTREGADOR"

    return (
        base.groupby("_ENTREGADOR", dropna=False)
        .agg(QTDE=(count_col, "count"), VALOR_TOTAL=("_VALOR", "sum"))
        .reset_index()
        .rename(columns={"_ENTREGADOR": "ENTREGADOR"})
        .sort_values(["QTDE", "VALOR_TOTAL"], ascending=False)
    )


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
        title = "Detalhe — Backlog (atraso de entrega)"
        subtitle = "Cargas com atraso/SLA vencido, excluindo integração Eu Entrego x SK, Avarias / Salvados e Qualidade."
        df = backlog_atraso_df.copy() if "backlog_atraso_df" in globals() else overdue_delivery_rows(fila_filtrada)

    elif card_key == "backlog_eu_entregue":
        title = "Detalhe — Entregue no Eu Entrego x Pendente no SK"
        subtitle = "Cargas que constam como entregues/baixadas no Eu Entrego, mas continuam como PENDENTE ENTREGA no SK."
        df = entregue_eu_entrego_pendente_sk_rows(fila_filtrada)

    elif card_key == "qualidade":
        title = "Detalhe — Aguardando retorno da Qualidade"
        subtitle = "AWBs da planilha de Qualidade com RETORNO_QUALIDADE = PENDENTE. Não entram em Pendente de entrega nem no Backlog de atraso."
        df = qualidade_df.copy() if "qualidade_df" in globals() else aguardando_qualidade_rows(fila_filtrada)

    elif card_key == "insucesso_sem_pendencia":
        title = "Detalhe — Insucesso sem pendência"
        subtitle = "Cargas PENDENTE ENTREGA no SK, com insucesso no Eu Entrego, sem baixa/finalização no SK e fora da pendência da Torre."
        df = insucesso_sem_pendencia_df.copy() if "insucesso_sem_pendencia_df" in globals() else insucesso_sem_pendencia_rows(fila_filtrada)

    elif card_key == "sla_sem_rota":
        title = "Detalhe — SLA do dia sem rota"
        subtitle = "Cargas com SLA no dia analisado, sem rota/saída no dia e sem insucesso que exija pendência."
        df = sla_sem_rota_df.copy() if "sla_sem_rota_df" in globals() else sla_sem_rota_rows(fila_filtrada)

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
        df = acareacao_rows_prefer_sheet(fila_filtrada)

    elif card_key == "avaria":
        title = "Detalhe — Avarias / Salvados"
        subtitle = "Dados puxados da planilha Pendências da Torre: aba Avarias + Salvados aguardando aprovação."
        df = avaria_rows(fila_filtrada)

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

    if card_key == "insucesso_sem_pendencia":
        st.markdown("#### Resumo por motivo de insucesso")
        resumo_motivo = resumo_insucesso_por_motivo(detail_df)
        render_table(resumo_motivo, height=260)

        st.markdown("#### Resumo por entregador")
        resumo_entregador = resumo_insucesso_por_entregador(detail_df)
        render_table(resumo_entregador, height=260)

        st.markdown("#### Detalhe por AWB")
        render_table(detail_df.head(500), height=420)

        st.download_button(
            "Baixar Excel deste card",
            excel_insucesso_sem_pendencia(detail_df),
            file_name="card_insucesso_sem_pendencia.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        return

    if card_key == "acareacao":
        st.markdown("#### Entregadores responsáveis")
        resumo_ent = acareacao_driver_summary_prefer_sheet(fila_filtrada)
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


def render_motoristas_pareto(motoristas_df):
    """
    Renderiza Pareto 80/20 dos motoristas ofensores.
    Não altera dados/regras: usa o ranking já calculado em driver_offenders().
    """
    if motoristas_df is None or motoristas_df.empty:
        st.info("Sem dados suficientes para montar o Pareto de motoristas ofensores.")
        return

    data = motoristas_df.copy()

    motorista_col = first_col(data, ["MOTORISTA / ENTREGADOR", "ENTREGADOR", "MOTORISTA"])
    valor_col = first_col(data, ["TOTAL OCORRÊNCIAS", "TOTAL OCORRENCIAS", "AWBS", "INSUCESSOS", "RETORNOS"])

    if not motorista_col or not valor_col:
        st.info("Sem colunas suficientes para montar o Pareto de motoristas ofensores.")
        return

    data["_MOTORISTA_PARETO"] = data[motorista_col].fillna("Não informado").astype(str).str.strip()
    data["_MOTORISTA_PARETO"] = data["_MOTORISTA_PARETO"].replace("", "Não informado")
    data["_QTDE_PARETO"] = pd.to_numeric(data[valor_col], errors="coerce").fillna(0)

    data = data[data["_QTDE_PARETO"] > 0].copy()
    if data.empty:
        st.info("Sem volume suficiente para montar o Pareto de motoristas ofensores.")
        return

    data = (
        data.sort_values("_QTDE_PARETO", ascending=False)
        .head(15)
        .reset_index(drop=True)
    )
    total = float(data["_QTDE_PARETO"].sum())
    data["ACUMULADO"] = data["_QTDE_PARETO"].cumsum()
    data["PERCENTUAL_ACUMULADO"] = (data["ACUMULADO"] / total * 100).round(1)
    data["LINHA_80"] = 80

    base = alt.Chart(data).encode(
        x=alt.X(
            "_MOTORISTA_PARETO:N",
            sort="-y",
            title="Motorista / entregador",
            axis=alt.Axis(labelAngle=-35, labelLimit=120),
        )
    )

    bars = base.mark_bar(
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
        color="#0b63ce",
    ).encode(
        y=alt.Y("_QTDE_PARETO:Q", title="Ocorrências"),
        tooltip=[
            alt.Tooltip("_MOTORISTA_PARETO:N", title="Motorista"),
            alt.Tooltip("_QTDE_PARETO:Q", title="Ocorrências", format=",.0f"),
            alt.Tooltip("PERCENTUAL_ACUMULADO:Q", title="% acumulado", format=".1f"),
        ],
    )

    line = base.mark_line(
        color="#d97706",
        point=True,
        strokeWidth=3,
    ).encode(
        y=alt.Y(
            "PERCENTUAL_ACUMULADO:Q",
            title="% acumulado",
            scale=alt.Scale(domain=[0, 100]),
        ),
        tooltip=[
            alt.Tooltip("_MOTORISTA_PARETO:N", title="Motorista"),
            alt.Tooltip("PERCENTUAL_ACUMULADO:Q", title="% acumulado", format=".1f"),
        ],
    )

    rule = base.mark_rule(
        color="#ef4444",
        strokeDash=[6, 4],
    ).encode(
        y=alt.Y("LINHA_80:Q", title="% acumulado"),
    )

    chart = alt.layer(bars, line, rule).resolve_scale(
        y="independent"
    ).properties(
        height=360
    )

    st.markdown("#### Pareto 80/20 — motoristas ofensores")
    st.caption("Barras = volume de ocorrências. Linha laranja = percentual acumulado. Linha tracejada = referência de 80%.")
    st.altair_chart(chart, use_container_width=True)

    pareto_table = data[["_MOTORISTA_PARETO", "_QTDE_PARETO", "PERCENTUAL_ACUMULADO"]].rename(
        columns={
            "_MOTORISTA_PARETO": "MOTORISTA / ENTREGADOR",
            "_QTDE_PARETO": "OCORRÊNCIAS",
            "PERCENTUAL_ACUMULADO": "% ACUMULADO",
        }
    )
    render_table(pareto_table, height=260)




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
        format_excel_date_columns(writer, resumo, "RESUMO_BASE")

        kpis_df.to_excel(writer, sheet_name="RESUMO_DIRETORIA", index=False)
        format_excel_date_columns(writer, kpis_df, "RESUMO_DIRETORIA")

        motoristas_df.to_excel(writer, sheet_name="MOTORISTAS", index=False)
        format_excel_date_columns(writer, motoristas_df, "MOTORISTAS")

        retornos_df.to_excel(writer, sheet_name="RETORNOS_ABERTOS", index=False)
        format_excel_date_columns(writer, retornos_df, "RETORNOS_ABERTOS")

        pendcorp_df.to_excel(writer, sheet_name="TOP5_PEND_CORP", index=False)
        format_excel_date_columns(writer, pendcorp_df, "TOP5_PEND_CORP")

        # Quando disponíveis no escopo, adiciona abas gerenciais novas.
        if "acareacao_df" in globals():
            acareacao_df.to_excel(writer, sheet_name="ACAREACOES", index=False)
            format_excel_date_columns(writer, acareacao_df, "ACAREACOES")

        if "daily_df" in globals():
            daily_df.to_excel(writer, sheet_name="AWBS_POR_DIA", index=False)
            format_excel_date_columns(writer, daily_df, "AWBS_POR_DIA")

        if "alert_distribution_df" in globals():
            alert_distribution_df.to_excel(writer, sheet_name="DISTR_ALERTAS", index=False)
            format_excel_date_columns(writer, alert_distribution_df, "DISTR_ALERTAS")

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

    if st.button("Atualizar dados do Google", key="refresh_google_data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    menu_items = [
        ("visao", "⌂  Visão Geral"),
        ("backlog", "▣  Backlog"),
        ("pendencias", "Σ  Pendências"),
        ("sla_dia", "◷  SLA do Dia"),
        ("edi", "✈  EDI / First Mile"),
        ("acareacao", "▤  Acareações"),
        ("relatorio", "▤  Relatórios"),
        ("config", "⚙  Configurações"),
    ]

    if "menu_gerente" not in st.session_state:
        st.session_state["menu_gerente"] = "visao"

    if "detail_card" not in st.session_state:
        st.session_state["detail_card"] = ""


    if "edi_detail_card" not in st.session_state:
        st.session_state["edi_detail_card"] = ""

    if "bi_detail_card" not in st.session_state:
        st.session_state["bi_detail_card"] = ""

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
            <b>Central Operacional</b><br>
            Uso contínuo da Torre<br>
            Foco em ação
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# CARREGAMENTO
# =========================================================
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
acareacoes_detalhe = pack.get("ACAREACOES_DETALHE", pd.DataFrame())
avarias_detalhe = pack.get("AVARIAS_DETALHE", pd.DataFrame())
qualidade_detalhe = pack.get("QUALIDADE_DETALHE", pd.DataFrame())
bi_azul_resumo = pack.get("BI_AZUL_RESUMO", pd.DataFrame())
bi_azul_detalhe = pack.get("BI_AZUL_DETALHE", pd.DataFrame())
bi_azul_conferencia = pack.get("BI_AZUL_CONFERENCIA", pd.DataFrame())

periodo = summary_value(resumo, "Período analisado", "")
if not periodo:
    periodo = summary_value(resumo, "Data de análise", "")

atualizado = summary_value(resumo, "Atualizado em", "")

def datahora_local_operacao():
    try:
        return datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        return datetime.now()


def formatar_datahora_sync(valor=None):
    """
    Formata a última sincronização no padrão dd/mm/aa • HH:mm.
    Se o valor sincronizado não for confiável, usa a hora local do app.
    """
    txt = str(valor or "").strip()
    if txt:
        try:
            dt = pd.to_datetime(txt, errors="coerce")
            if pd.notna(dt):
                try:
                    if dt.tzinfo is None:
                        dt = dt.tz_localize("America/Sao_Paulo")
                    else:
                        dt = dt.tz_convert("America/Sao_Paulo")
                except Exception:
                    pass
                return dt.strftime("%d/%m/%y • %H:%M")
        except Exception:
            pass

    return datahora_local_operacao().strftime("%d/%m/%y • %H:%M")


def resumo_carga_cabecalho():
    """
    Informação visual discreta, sem alterar regra de negócio.
    Usa dados já carregados em memória.
    """
    partes = []

    try:
        if "fila" in globals() and fila is not None and not fila.empty:
            partes.append(f"{len(fila):,}".replace(",", ".") + " registros carregados")
    except Exception:
        pass

    try:
        fontes = 0
        for _df_name in ["fila", "edi_detalhe", "pendencia_movimentos", "acareacoes_detalhe", "avarias_detalhe", "qualidade_detalhe"]:
            _df = globals().get(_df_name)
            if _df is not None and hasattr(_df, "empty") and not _df.empty:
                fontes += 1
        if fontes:
            partes.append(f"{fontes} fontes processadas")
    except Exception:
        pass

    return " • ".join(partes) if partes else "Dados operacionais carregados"


atualizado_cabecalho = formatar_datahora_sync(atualizado)
info_carga_cabecalho = resumo_carga_cabecalho()


# =========================================================
# CABEÇALHO CORPORATIVO — CENTRAL OPERACIONAL
# =========================================================
today = date.today()
default_start = today - timedelta(days=7)

st.markdown('<div class="ops-header-shell">', unsafe_allow_html=True)

header_left, header_sync, header_button, header_period = st.columns(
    [3.45, 1.55, 1.35, 1.65],
    gap="small",
)

with header_left:
    st.markdown(
        """
        <div>
            <div class="ops-header-title">TORRE DE CONTROLE GDS</div>
            <div class="ops-header-subtitle">
                Central Operacional da Torre
                <span class="ops-info-icon">i</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with header_sync:
    st.markdown(
        f"""
        <div class="sync-card">
            <div class="sync-card-label">Última sincronização</div>
            <div class="sync-card-value">{atualizado_cabecalho}</div>
            <div class="sync-card-detail">{info_carga_cabecalho}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with header_button:
    st.markdown('<div class="ops-header-button-spacer"></div>', unsafe_allow_html=True)
    button_text = "⏳ Sincronizando..." if st.session_state.get("sync_feedback") == "running" else "🔄 Sincronizar Dados"

    if st.button(button_text, key="header_refresh_data", use_container_width=True):
        # Mesma funcionalidade já existente: limpar cache e recarregar dados.
        st.session_state["sync_feedback"] = "success"
        st.cache_data.clear()
        st.rerun()

    if st.session_state.get("sync_feedback") == "success":
        st.markdown(
            '<div class="sync-success-strip">✅ Dados sincronizados com sucesso</div>',
            unsafe_allow_html=True,
        )

with header_period:
    st.markdown('<div class="ops-header-control-label">Período</div>', unsafe_allow_html=True)
    date_range = st.date_input(
        "Período",
        value=None,
        format="DD/MM/YYYY",
        label_visibility="collapsed",
        help="Deixe em branco para ver tudo que está aberto. Selecione 1 dia para filtrar por SLA do dia ou um período para SLA no intervalo.",
    )

st.markdown('</div>', unsafe_allow_html=True)

fila_filtrada, filtro_msg = apply_date_filter(fila, date_range)

motoristas_df = driver_offenders(fila_filtrada)
retornos_df = open_returns(fila_filtrada)
pendcorp_df = top5_pendencia_corp(fila_filtrada)
acareacao_df = acareacao_rows_prefer_sheet(fila_filtrada)
avaria_df = avaria_rows(fila_filtrada)
resumo_avarias_qtd = number(summary_value(resumo, "Avarias / Salvados", len(avaria_df)))
daily_df = daily_awb_counts(fila_filtrada)

# Backlog precisa excluir casos que pertencem ao card Eu Entrego x SK.
backlog_atraso_df = overdue_delivery_rows(fila_filtrada)
resumo_entrega_atraso = len(backlog_atraso_df)
resumo_entregue_eu_pendente_sk = number(summary_value(resumo, "Entregue Eu Entrego x Pendente SK", len(entregue_eu_entrego_pendente_sk_rows(fila_filtrada))))
# Insucesso sem pendência precisa bater com o detalhe exibido.
insucesso_sem_pendencia_df = insucesso_sem_pendencia_rows(fila_filtrada)
resumo_insucesso_sem_pendencia = len(insucesso_sem_pendencia_df)

# Qualidade precisa existir antes dos cards.
# A quantidade do card usa o mesmo dataframe do detalhe.
qualidade_df = aguardando_qualidade_rows(fila_filtrada)
resumo_qualidade_qtd = len(qualidade_df)

# SLA do dia sem rota precisa refletir a FILA filtrada/detalhe atual.
# Não usa mais o RESUMO como fonte principal, para evitar número defasado.
sla_sem_rota_df = sla_sem_rota_rows(fila_filtrada)
resumo_sla_sem_rota = len(sla_sem_rota_df)
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
resumo_passivo_valor = pd.to_numeric(summary_value(resumo, "Valor passivo débito", summary_value(resumo, "Passivo de Débito", 0)), errors="coerce")
resumo_passivo_valor = 0 if pd.isna(resumo_passivo_valor) else float(resumo_passivo_valor)
resumo_passivo_qtd = number(summary_value(resumo, "Quantidade passivo débito", summary_value(resumo, "Processos passivo débito", 0)))
resumo_debitos_revertidos_valor = pd.to_numeric(summary_value(resumo, "Valor débito revertido", summary_value(resumo, "Débitos Revertidos", 0)), errors="coerce")
resumo_debitos_revertidos_valor = 0 if pd.isna(resumo_debitos_revertidos_valor) else float(resumo_debitos_revertidos_valor)
resumo_debitos_revertidos_qtd = number(summary_value(resumo, "Quantidade débito revertido", summary_value(resumo, "Processos revertidos", 0)))
resumo_percentual_reversao = pd.to_numeric(summary_value(resumo, "Percentual reversão", 0), errors="coerce")
resumo_percentual_reversao = 0 if pd.isna(resumo_percentual_reversao) else float(resumo_percentual_reversao)


alert_distribution_df = pd.DataFrame(
    [
        {"INDICADOR": "Backlog (atraso de entrega)", "QTDE": resumo_entrega_atraso},
        {"INDICADOR": "Entregue Eu Entrego x Pendente SK", "QTDE": resumo_entregue_eu_pendente_sk},
        {"INDICADOR": "Aguardando retorno da Qualidade", "QTDE": resumo_qualidade_qtd},
        {"INDICADOR": "Insucesso sem pendência", "QTDE": resumo_insucesso_sem_pendencia},
        {"INDICADOR": "SLA do dia sem rota", "QTDE": resumo_sla_sem_rota},
        {"INDICADOR": "Pendente desembarque CDSP2", "QTDE": resumo_lm_desembarque},
        {"INDICADOR": "3ª tentativa", "QTDE": resumo_terceira_tentativa},
        {"INDICADOR": "Retornos em aberto", "QTDE": len(retornos_df)},
        {"INDICADOR": "Acareações em aberto", "QTDE": resumo_acareacao_qtd},
        {"INDICADOR": "Avarias / Salvados", "QTDE": resumo_avarias_qtd},
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
        {"INDICADOR": "Backlog (atraso de entrega)", "VALOR": resumo_entrega_atraso},
        {"INDICADOR": "Entregue Eu Entrego x Pendente SK", "VALOR": resumo_entregue_eu_pendente_sk},
        {"INDICADOR": "Insucesso sem pendência", "VALOR": resumo_insucesso_sem_pendencia},
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
        {"INDICADOR": "Avarias / Salvados", "VALOR": resumo_avarias_qtd},
        {"INDICADOR": "Valor em acareação", "VALOR": summary_value(resumo, "Valor em acareação", 0)},
    ]
)


# =========================================================
# PÁGINAS
# =========================================================
menu = st.session_state["menu_gerente"]

if menu == "visao":
    st.markdown('<div class="section-title">Central de ação</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Prioridade operacional: atraso, SLA do dia, pendência, acareações e risco financeiro.</div>',
        unsafe_allow_html=True,
    )

    acareacao_qtd = resumo_acareacao_qtd
    _acareacao_valor_total = acareacao_total_value(acareacao_df)
    if _acareacao_valor_total <= 0:
        _acareacao_valor_total = pd.to_numeric(
            summary_value(resumo, "Valor em acareação", 0),
            errors="coerce",
        )
        _acareacao_valor_total = 0 if pd.isna(_acareacao_valor_total) else float(_acareacao_valor_total)
    acareacao_valor = brl(_acareacao_valor_total)

    # Sem nova regra: se a base ainda não trouxer prazo vencendo hoje, mostra 0.
    acareacao_vencendo_hoje = number(summary_value(resumo, "Acareações vencendo hoje", 0))

    saldo_dia = int(resumo_entraram_pendencia_hoje) - int(resumo_sairam_pendencia_hoje)

    primary_cards = [
        ("Backlog de Entrega", fmt_int(resumo_entrega_atraso), "Cargas em atraso com SLA vencido", "!", "#d92d20", "#fff0ef", "atraso", "normal"),
        ("SLA do Dia", fmt_int(resumo_sla_sem_rota), "Cargas que ainda precisam sair hoje", "◷", "#d97706", "#fff7e8", "sla_sem_rota", "normal"),
        ("Pendente Desembarque CDSP2", fmt_int(resumo_lm_desembarque), "Cargas aguardando desembarque até SLA do dia", "⇣", "#0f766e", "#f0fdfa", "lastmile_desembarque", "normal"),
        ("Pendências da Torre", fmt_int(resumo_total_pendencia), "Backlog atual da Torre", "Σ", "#b7791f", "#fff8e1", "pend_total", "pendencia"),
        ("Acareações", fmt_int(acareacao_qtd), f"Valor em aberto: {acareacao_valor}", "▤", "#0b63ce", "#eaf3ff", "acareacao", "acareacao"),
    ]

    secondary_cards = [
        ("Entregue Eu Entrego x SK", fmt_int(resumo_entregue_eu_pendente_sk), "Entregue no Eu Entrego e pendente no SK", "↔", "#be123c", "#fff1f2", "backlog_eu_entregue"),
        ("Aguardando retorno da Qualidade", fmt_int(resumo_qualidade_qtd), "RETORNO_QUALIDADE = PENDENTE", "Q", "#0b63ce", "#e7f0ff", "qualidade"),
        ("Insucesso sem Pendência", fmt_int(resumo_insucesso_sem_pendencia), "Direcionar para pendência", "!", "#d97706", "#fff7e8", "insucesso_sem_pendencia"),
        ("3ª Tentativa de Entrega", fmt_int(resumo_terceira_tentativa), "Resumo operacional sincronizado", "3ª", "#c2410c", "#fff7ed", "terceira"),
        ("Avarias / Salvados", fmt_int(resumo_avarias_qtd), "Avarias e salvados aguardando aprovação", "!", "#d92d20", "#fff0ef", "avaria"),
    ]

    def _render_card_item(item, idx=None):
        label, value, sub, icon, accent, soft, key = item[:7]
        card_type = item[7] if len(item) > 7 else "normal"

        if card_type == "pendencia":
            pendencia_operational_card(
                fmt_int(resumo_total_pendencia),
                fmt_int(resumo_entraram_pendencia_hoje),
                fmt_int(resumo_sairam_pendencia_hoje),
                saldo_dia,
                card_key=key,
            )
        elif card_type == "acareacao":
            acareacao_operational_card(
                fmt_int(acareacao_qtd),
                acareacao_valor,
                fmt_int(acareacao_vencendo_hoje),
                card_key=key,
            )
        else:
            operational_card(label, value, sub, icon, accent, soft, card_key=key)

        st.markdown('<div class="card-footer-button">', unsafe_allow_html=True)
        footer_label = "Visualizar detalhes →"
        if st.button(footer_label, key=f"abrir_{key}", use_container_width=True):
            if st.session_state.get("detail_card") == key:
                st.session_state["detail_card"] = ""
            else:
                st.session_state["detail_card"] = key
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    def _render_detail_if_row(row_keys):
        detail = st.session_state.get("detail_card", "")
        if detail and detail in row_keys:
            render_card_detail(detail, fila_filtrada, motoristas_df, retornos_df, acareacao_df, daily_df)

    # Linha 1 — cards críticos do piso/entrega.
    primary_row_1 = primary_cards[:3]
    cols = st.columns(3)
    for idx, item in enumerate(primary_row_1):
        with cols[idx]:
            _render_card_item(item, idx)

    _render_detail_if_row([item[6] for item in primary_row_1])

    st.markdown('<div class="card-row-spacer"></div>', unsafe_allow_html=True)

    # Linha 2 — pendência e acareação. Cards mais largos.
    primary_row_2 = primary_cards[3:]
    cols = st.columns(2)
    for idx, item in enumerate(primary_row_2):
        with cols[idx]:
            _render_card_item(item, idx)

    _render_detail_if_row([item[6] for item in primary_row_2])

    st.markdown('<div class="section-title">Outras frentes operacionais</div>', unsafe_allow_html=True)

    # Linha 3 — outras frentes.
    secondary_row_1 = secondary_cards[:3]
    cols = st.columns(3)
    for idx, item in enumerate(secondary_row_1):
        with cols[idx]:
            _render_card_item(item, idx)

    _render_detail_if_row([item[6] for item in secondary_row_1])

    st.markdown('<div class="card-row-spacer"></div>', unsafe_allow_html=True)

    # Linha 4 — outras frentes remanescentes.
    secondary_row_2 = secondary_cards[3:]
    cols = st.columns(2)
    for idx, item in enumerate(secondary_row_2):
        with cols[idx]:
            _render_card_item(item, idx)

    _render_detail_if_row([item[6] for item in secondary_row_2])



elif menu == "backlog":
    st.markdown("### Backlog de Entrega")
    st.caption("Cargas em atraso com SLA vencido. Mesma regra do card da Visão Geral.")
    render_card_detail("atraso", fila_filtrada, motoristas_df, retornos_df, acareacao_df, daily_df)


elif menu == "pendencias":
    st.markdown("### Pendências da Torre")
    st.caption("Pendências atuais, entradas do dia, saídas do dia e movimentação da Torre.")
    render_card_detail("pend_total", fila_filtrada, motoristas_df, retornos_df, acareacao_df, daily_df)


elif menu == "sla_dia":
    st.markdown("### SLA do Dia")
    st.caption("Cargas que precisam sair hoje conforme regra já existente.")
    render_card_detail("sla_sem_rota", fila_filtrada, motoristas_df, retornos_df, acareacao_df, daily_df)


elif menu == "passivo":
    st.markdown("### Passivo de Débito")
    st.caption("Visão financeira conforme dados já sincronizados no RESUMO. Sem nova regra operacional.")
    resumo_passivo = pd.DataFrame([
        {"INDICADOR": "Valor financeiro em aberto", "VALOR": brl(resumo_passivo_valor)},
        {"INDICADOR": "Quantidade de processos", "VALOR": fmt_int(resumo_passivo_qtd)},
    ])
    render_table(resumo_passivo, height=180)
    st.info("Detalhe analítico será exibido aqui quando a origem sincronizada trouxer a aba/tabela de passivo.")


elif menu == "debitos_revertidos":
    st.markdown("### Débitos Revertidos")
    st.caption("Valor recuperado e processos revertidos conforme dados já sincronizados no RESUMO.")
    resumo_revertidos = pd.DataFrame([
        {"INDICADOR": "Valor recuperado", "VALOR": brl(resumo_debitos_revertidos_valor)},
        {"INDICADOR": "Quantidade de processos revertidos", "VALOR": fmt_int(resumo_debitos_revertidos_qtd)},
        {"INDICADOR": "Percentual de reversão", "VALOR": f"{resumo_percentual_reversao:.1f}%"},
    ])
    render_table(resumo_revertidos, height=210)
    st.info("Detalhe analítico será exibido aqui quando a origem sincronizada trouxer a aba/tabela de débitos revertidos.")


elif menu == "motoristas":
    st.markdown("### Motoristas ofensores — Pareto")
    st.caption("Análise 80/20 dos entregadores/motoristas com maior concentração de insucessos e retornos.")
    render_motoristas_pareto(motoristas_df)

    st.markdown("#### Ranking detalhado")
    render_table(motoristas_df, height=420)

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
        "Visão simplificada do EDI: pendente de entrega por SLA, embarque atrasado, discrepância e desembarque com localização."
    )

    st.info(
        "Regra simplificada: embarque mostra apenas dias anteriores; SLA do dia atual não entra no embarque atrasado. "
        "Desembarque mostra onde a carga está e exclui entregue, baixado, discrepância e pendente de embarque."
    )

    edi_entrega_df = edi_rows_entrega_destino_sla(edi_detalhe)
    edi_emb_atrasado_df = edi_rows_embarque_atrasado(edi_detalhe)
    edi_discrepancia_df = edi_rows(edi_detalhe, "DISCREPÂNCIA")
    edi_desembarque_df = edi_rows_desembarque(edi_detalhe)

    edi_cards = [
        (
            "Pendente entrega destino",
            fmt_int(edi_count_df(edi_entrega_df)),
            "SLA vencido ou SLA do dia",
            "SLA",
            "#d97706",
            "#fff7e8",
            "edi_entrega_sla",
        ),
        (
            "Pendente embarque atrasado",
            fmt_int(edi_count_df(edi_emb_atrasado_df)),
            "Somente dias anteriores",
            "↗",
            "#2563eb",
            "#eff6ff",
            "edi_emb_atrasado",
        ),
        (
            "Discrepância",
            fmt_int(edi_count_df(edi_discrepancia_df)),
            "Divergências First Mile",
            "≠",
            "#7c3aed",
            "#f5f3ff",
            "edi_discrepancia",
        ),
        (
            "Pendente desembarque",
            fmt_int(edi_count_df(edi_desembarque_df)),
            "Exclui entregue/embarque/discrepância",
            "⇣",
            "#0f766e",
            "#f0fdfa",
            "edi_desembarque",
        ),
    ]

    cols = st.columns(4)
    for idx, item in enumerate(edi_cards):
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


elif menu == "bi_azul":
    st.markdown("### BI Azul — Cobrança das Bases")
    st.caption(
        "Relatório opcional do Power BI Azul por praça/base: TRES1, SAO12 e CDSP2. "
        "Usado para conferência de cobrança das bases, principalmente contra o EDI."
    )

    if bi_azul_detalhe is None or bi_azul_detalhe.empty:
        st.info("Nenhum relatório BI Azul foi sincronizado. Envie o arquivo no app operacional e clique em Sincronizar BI Azul agora.")

    cards_l1 = [
        ("BI TRES1", fmt_int(bi_count(bi_azul_detalhe, base="TRES1")), "AWBs no relatório TRES1", "T1", "#1d4ed8", "#eff6ff", "bi_tres1"),
        ("BI SAO12", fmt_int(bi_count(bi_azul_detalhe, base="SAO12")), "AWBs no relatório SAO12", "S12", "#2563eb", "#eff6ff", "bi_sao12"),
        ("BI CDSP2", fmt_int(bi_count(bi_azul_detalhe, base="CDSP2")), "AWBs no relatório CDSP2", "CD", "#0f766e", "#f0fdfa", "bi_cdsp2"),
        ("Resumo BI", fmt_int(len(bi_azul_resumo)), "Resumo por base", "Σ", "#334155", "#f8fafc", "bi_resumo"),
    ]

    divergencias_qtd = (
        len(bi_azul_conferencia[
            ~bi_azul_conferencia["RESULTADO_CONFERENCIA"].astype(str).eq("OK")
        ])
        if bi_azul_conferencia is not None
        and not bi_azul_conferencia.empty
        and "RESULTADO_CONFERENCIA" in bi_azul_conferencia.columns
        else 0
    )

    cards_l2 = [
        ("Divergências", fmt_int(divergencias_qtd), "BI x EDI", "!", "#d92d20", "#fff0ef", "bi_divergentes"),
        ("No BI e não no EDI", fmt_int(bi_count(bi_azul_conferencia, resultado="NO BI E NÃO NO EDI")), "Cobrado no BI, ausente no EDI", "BI", "#d97706", "#fff7e8", "bi_no_bi_nao_edi"),
        ("No EDI e não no BI", fmt_int(bi_count(bi_azul_conferencia, resultado="NO EDI E NÃO NO BI")), "No EDI, ausente no BI", "EDI", "#7c3aed", "#f5f3ff", "bi_no_edi_nao_bi"),
    ]

    for cards in [cards_l1, cards_l2]:
        cols = st.columns(len(cards))
        for idx, item in enumerate(cards):
            label, value, sub, icon, accent, soft, key = item
            with cols[idx]:
                kpi_card(label, value, sub, icon, accent, soft)
                button_label = "Aberto" if st.session_state.get("bi_detail_card") == key else "Abrir"
                if st.button(button_label, key=f"abrir_{key}", use_container_width=True):
                    if st.session_state.get("bi_detail_card") == key:
                        st.session_state["bi_detail_card"] = ""
                    else:
                        st.session_state["bi_detail_card"] = key
                    st.rerun()

    detail = st.session_state.get("bi_detail_card", "")
    if detail:
        render_bi_card_detail(detail)


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
            {"Aba": "ACAREACOES_DETALHE", "Linhas": len(acareacoes_detalhe)},
            {"Aba": "AVARIAS_DETALHE", "Linhas": len(avarias_detalhe)},
            {"Aba": "BI_AZUL_RESUMO", "Linhas": len(bi_azul_resumo)},
            {"Aba": "BI_AZUL_DETALHE", "Linhas": len(bi_azul_detalhe)},
            {"Aba": "BI_AZUL_CONFERENCIA", "Linhas": len(bi_azul_conferencia)},
            {"Filtro aplicado": filtro_msg, "Linhas após filtro": len(fila_filtrada)},
            {"Filtro aplicado": "AWBs por dia", "Linhas após filtro": len(daily_df)},
            {"Filtro aplicado": "Acareações em aberto", "Linhas após filtro": len(acareacao_df)},
        ]
    )
    render_table(status_df, height=220)

    st.info("Secrets necessários: MANAGER_SOURCE_URL e [gcp_service_account].")
