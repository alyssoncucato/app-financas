# --- PROCESSAMENTO LÍQUIDO POR CATEGORIA ---
    todas_as_cats = list(set(categorias_despesas + categorias_entradas))
    
    resumo_cat_list = []
    for cat in todas_as_cats:
        if cat == "Ignorar":
            continue
        df_cat_all = df_final[df_final['categoria'] == cat]
        if not df_cat_all.empty:
            t_saida = df_cat_all[df_cat_all['tipo'] == 'SAÍDA']['valor'].sum()
            t_entrada = df_cat_all[df_cat_all['tipo'] == 'ENTRADA']['valor'].sum()
            
            # Impacto Líquido Real: Entradas menos Saídas (quanto sobrou/movimentou de fato na categoria)
            valor_liquido = t_entrada - t_saida
            
            resumo_cat_list.append({
                'categoria': cat,
                'saida': t_saida,
                'entrada': t_entrada,
                'valor_liquido': valor_liquido,
                'qtd': len(df_cat_all)
            })
            
    df_resumo_cat = pd.DataFrame(resumo_cat_list)

    # --- GRÁFICOS ---
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("#### 📊 Impacto Líquido por Categoria")
        if not df_resumo_cat.empty:
            df_graf = df_resumo_cat[df_resumo_cat['valor_liquido'] != 0].set_index('categoria')['valor_liquido']
            if not df_graf.empty:
                st.bar_chart(df_graf)
            else:
                st.info("Todas as categorias estão balanceadas neste período.")
        else:
            st.info("Sem dados para exibir no gráfico.")

    with col_g2:
        st.markdown("#### 📅 Evolução ou Maiores Lançamentos")
        if mes_sel == "Todos os Meses do Ano":
            df_evolucao = df_final[df_final['tipo'] == 'SAÍDA'].groupby('mes_ano')['valor'].sum().reset_index()
            if not df_evolucao.empty:
                df_evolucao['mes_ordem'] = pd.to_datetime(df_evolucao['mes_ano'], format='%m/%Y')
                st.line_chart(df_evolucao.sort_values('mes_ordem').set_index('mes_ano')['valor'])
            else:
                st.info("Sem dados para evolução.")
        else:
            df_maiores = df_final.nlargest(5, 'valor')[['data', 'descricao', 'valor', 'tipo', 'categoria']]
            st.dataframe(df_maiores, use_container_width=True, hide_index=True)

    st.divider()

    # --- ÁRVORE DETALHADA POR CATEGORIA -> ESTABELECIMENTO -> LANÇAMENTOS ---
    st.markdown("### 📂 Detalhamento em Árvore por Categoria (Com Entradas e Saídas)")
    st.caption("Clique nas categorias abaixo para abrir, ver o fluxo de entradas/saídas, estabelecimentos e valores detalhados.")

    df_validos = df_final[df_final['categoria'] != "Ignorar"].copy()

    if df_validos.empty:
        st.info("Nenhum lançamento detalhado para este filtro.")
        return

    df_validos['estabelecimento'] = df_validos['descricao'].str.strip().str.upper()
    cats_presentes = sorted(df_validos['categoria'].unique())

    for cat in cats_presentes:
        df_cat_itens = df_validos[df_validos['categoria'] == cat]
        t_saidas_cat = df_cat_itens[df_cat_itens['tipo'] == 'SAÍDA']['valor'].sum()
        t_entradas_cat = df_cat_itens[df_cat_itens['tipo'] == 'ENTRADA']['valor'].sum()
        liquido_cat = t_entradas_cat - t_saidas_cat

        # Define a cor visual com base no impacto líquido (Verde se >= 0, Vermelho se < 0)
        cor_emoji = "🟢" if liquido_cat >= 0 else "🔴"
        
        label_expander = f"📁 **{cat}** — Impacto Líquido: {cor_emoji} **R$ {liquido_cat:,.2f}** *(Entrou: 🟢 R$ {t_entradas_cat:,.2f} | Saiu: 🔴 R$ {t_saidas_cat:,.2f})* — ({len(df_cat_itens)} itens)"

        with st.expander(label_expander):
            estabelecimentos = sorted(df_cat_itens['estabelecimento'].unique())
            
            for estab in estabelecimentos:
                df_estab_itens = df_cat_itens[df_cat_itens['estabelecimento'] == estab]
                t_estab = df_estab_itens['valor'].sum()
                
                with st.expander(f"🔹 **{estab}** — Subtotal: R$ {t_estab:,.2f} ({len(df_estab_itens)}x)"):
                    for _, row in df_estab_itens.iterrows():
                        data_formatada = pd.to_datetime(row['data']).strftime('%d/%m/%Y') if pd.notna(row['data']) else "Data não inf."
                        tipo_icone = "🟢 ENTRADA" if row['tipo'] == 'ENTRADA' else "🔴 SAÍDA"
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• **Data:** {data_formatada} | **Tipo:** {tipo_icone} | **Valor:** `R$ {row['valor']:,.2f}` | *Origem:* {row['origem']}")