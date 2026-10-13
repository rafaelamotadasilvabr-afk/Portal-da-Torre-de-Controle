
    if base_ind is None or base_ind.empty:
        st.info("Nenhum dado de Passível a Débito sincronizado para exibir o painel de Indenização.")
    else:
        # Quantidades por STATUS PROCESSO (coluna B), considerando todas as bases.
        status_processo_ind = (
            base_ind.iloc[:, 1].fillna("").astype(str)
            .map(normalize_text).str.replace(r"\s+", " ", regex=True).str.strip()
        )

        render_indenizacao_layout(
        [
            ('Valor Total de processo', _money_br_ind(metrics_ind['valor_total_processo']), 'OFENSOR: CDSP2, SAO12 e compartilhados', '#0b63ce', '🏢'),
            ('Débito acatado — CDSP2 / SAO12', _money_br_ind(metrics_ind['valor_acatado']), 'Inclui compartilhados; sem descontos e sem reversões', '#7c3aed', '🏬'),
            ('Débito revertido', _money_br_ind(metrics_ind['valor_revertido']), f"{fmt_int(metrics_ind['qtd_revertido'])} registro(s) com DÉBITO REVERTIDO = SIM", '#0f766e', '↩️'),
            ('Desconto aplicado', _money_br_ind(metrics_ind['valor_desconto']), f"{fmt_int(metrics_ind['qtd_desconto'])} AWB(s) com HOUVE DESCONTO? = SIM", '#be123c', '−'),
        ],
        [
            ('Total monitorado', fmt_int(len(base_ind)), f"Valor total: {_money_br_ind(float(base_ind['_VALOR_INDENIZACAO'].sum()))}", '#08254e', 'Σ'),
            ('Processo em análise', fmt_int(int(status_processo_ind.eq('PROCESSO EM ANALISE').sum())), 'STATUS PROCESSO — todas as bases', '#0b63ce', '🔎'),
            ('Processo com documento pendente', fmt_int(int(status_processo_ind.isin({'FALTA DOCUMENTO', 'PROCESSO COM DOCUMENTO PENDENTE'}).sum())), 'STATUS PROCESSO — todas as bases', '#d97706', '📄'),
            ('Falta análise supervisora', fmt_int(metrics_ind['qtd_supervisao']), f"Coluna M vazia — todas as bases: {_money_br_ind(metrics_ind['valor_supervisao'])}", '#d97706', '🔎'),
        ]
        )

        with st.container(border=True):
            render_indenizacao_evolucao()

        with st.container(border=True):
            render_indenizacao_claim_type(base_ind)

        st.markdown("### Detalhamento da Indenização")

        aba = st.radio(
            "Selecionar visão",
            ["Débito acatado — CDSP2 / SAO12", "Débito revertido", "Desconto aplicado", "Falta análise supervisora", "Base completa"],
            horizontal=True,
        )

        mapa = {
            "Débito acatado — CDSP2 / SAO12": "acatado",
            "Débito revertido": "revertido",
            "Desconto aplicado": "desconto",
            "Falta análise supervisora": "supervisao",
            "Base completa": "todos",
        }

        detalhe = indenizacao_detail_rows(mapa[aba])
        st.caption(f"{fmt_int(len(detalhe))} registro(s) encontrado(s).")
        render_table(detalhe, height=460)



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
