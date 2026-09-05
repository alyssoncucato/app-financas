# --- ÁRVORE DETALHADA POR CATEGORIA -> ESTABELECIMENTO -> LANÇAMENTOS ---
    st.markdown("### 📂 Detalhamento em Árvore por Categoria (Com Entradas e Saídas)")
    st.caption("Clique nas categorias abaixo para abrir, ver o fluxo de entradas/saídas, estabelecimentos e valores detalhados.")

    df_validos = df_final[df_final['categoria'] != "Ignorar"].copy()

    if df_validos.empty:
        st.info("Nenhum lançamento detalhado para este filtro.")
        return

    df_validos['estabelecimento'] = df_validos['descricao'].str.strip().str.upper()
    cats_presentes = sorted(df_validos['unique'] if 'unique' in dir(df_validos['categoria']) else df_validos['categoria'].unique())

    for cat in cats_presentes:
        df_cat_itens = df_validos[df_validos['categoria'] == cat]
        t_saidas_cat = df_cat_itens[df_cat_itens['tipo'] == 'SAÍDA']['valor'].sum()
        t_entradas_cat = df_cat_itens[df_cat_itens['tipo'] == 'ENTRADA']['valor'].sum()
        liquido_cat = t_entradas_cat - t_saidas_cat

        # Define a cor HTML para o impacto líquido (Verde se >= 0, Vermelho se < 0)
        cor_liquido = "#2ecc71" if liquido_cat >= 0 else "#e74c3c"
        
        # Montagem do título limpo e formatado com HTML puro para evitar quebras do Streamlit
        label_expander = (
            f"📁 **{cat}** — Impacto Líquido: "
            f"<span style='color:{cor_liquido}; font-weight:bold;'>R$ {liquido_cat:,.2f}</span> "
            f"— (Entrou: <span style='color:#2ecc71;'>R$ {t_entradas_cat:,.2f}</span> | "
            f"Saiu: <span style='color:#e74c3c;'>R$ {t_saidas_cat:,.2f}</span>) — ({len(df_cat_itens)} itens)"
        )

        with st.expander(label_expander, expanded=False):
            estabelecimentos = sorted(df_cat_itens['estabelecimento'].unique())
            
            for estab in estabelecimentos:
                df_estab_itens = df_cat_itens[df_cat_itens['estabelecimento'] == estab]
                t_estab = df_estab_itens['valor'].sum()
                
                with st.expander(f"🔹 **{estab}** — Subtotal: R$ {t_estab:,.2f} ({len(df_estab_itens)}x)"):
                    for _, row in df_estab_itens.iterrows():
                        data_formatada = pd.to_datetime(row['data']).strftime('%d/%m/%Y') if pd.notna(row['data']) else "Data não inf."
                        tipo_icone = "🟢 ENTRADA" if row['tipo'] == 'ENTRADA' else "🔴 SAÍDA"
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• **Data:** {data_formatada} | **Tipo:** {tipo_icone} | **Valor:** `R$ {row['valor']:,.2f}` | *Origem:* {row['origem']}")