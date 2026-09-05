import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text

def render(user, conn_fin, categorias_despesas, categorias_entradas):
    st.subheader("📊 Dashboard Financeiro Estruturado")
    
    try:
        query = text("SELECT * FROM transacoes WHERE LOWER(usuario) = LOWER(:u)")
        df = pd.read_sql_query(query, conn_fin, params={"u": user})
    except Exception as e:
        st.error(f"Erro ao carregar transações: {e}")
        return
    
    if df.empty:
        st.info("Nenhum lançamento encontrado. Importe extratos ou faturas para visualizar o dashboard.")
        return

    df['data_dt'] = pd.to_datetime(df['data'], errors='coerce')
    df['ano'] = df['data_dt'].dt.year.fillna(datetime.now().year).astype(int)
    df['mes_ano'] = df['data_dt'].dt.strftime('%m/%Y')
    
    if 'tipo' not in df.columns:
        df['tipo'] = "SAÍDA"
    df['tipo'] = df['tipo'].fillna("SAÍDA").str.upper()

    # --- MENU DE NAVEGAÇÃO PRINCIPAL ---
    st.markdown("### 🎯 Seleção de Visualização")
    
    col_n1, col_n2, col_n3 = st.columns(3)
    
    with col_n1:
        tipo_visao = st.selectbox(
            "1. Fonte de Dados:", 
            ["Visão Geral (Consolidada)", "💳 Cartão Nubank", "💳 Cartão Mercado Pago", "🏦 Extrato Conta Corrente"]
        )
    
    with col_n2:
        anos_disponiveis = sorted(list(df['ano'].unique()), reverse=True)
        if not anos_disponiveis:
            anos_disponiveis = [datetime.now().year]
        ano_sel = st.selectbox("2. Ano:", anos_disponiveis)

    df_ano = df[df['ano'] == ano_sel]

    if "Nubank" in tipo_visao or "Mercado Pago" in tipo_visao:
        df_filtrado = df_ano[df_ano['origem'] == 'FATURA_CARTAO']
    elif "Conta Corrente" in tipo_visao:
        df_filtrado = df_ano[df_ano['origem'] == 'EXTRATO_CONTA']
    else:
        df_filtrado = df_ano

    with col_n3:
        meses_ano = sorted(df_filtrado['mes_ano'].dropna().unique(), key=lambda x: datetime.strptime(x, '%m/%Y'))
        opcoes_mes = ["Todos os Meses do Ano"] + meses_ano
        mes_sel = st.selectbox("3. Mês:", opcoes_mes)

    if mes_sel != "Todos os Meses do Ano":
        df_final = df_filtrado[df_filtrado['mes_ano'] == mes_sel]
        titulo_periodo = f"Mês: {mes_sel} ({ano_sel})"
    else:
        df_final = df_filtrado
        titulo_periodo = f"Ano Consolidado: {ano_sel}"

    st.divider()
    st.markdown(f"### 📈 Métricas para: **{tipo_visao}** — *{titulo_periodo}*")

    if df_final.empty:
        st.warning(f"Nenhum registro encontrado para {tipo_visao} em {titulo_periodo}.")
        return

    # --- CÁLCULOS LÍQUIDOS REAIS ---
    receitas = df_final[(df_final['tipo'] == 'ENTRADA') & (~df_final['categoria'].isin(["Ignorar"]))]['valor'].sum()
    despesas = df_final[(df_final['tipo'] == 'SAÍDA') & (~df_final['categoria'].isin(["Ignorar"]))]['valor'].sum()
    saldo = receitas - despesas

    m1, m2, m3 = st.columns(3)
    if "Conta Corrente" in tipo_visao or "Visão Geral" in tipo_visao:
        m1.metric("💰 Entradas / Receitas", f"R$ {receitas:,.2f}")
    else:
        m1.metric("💳 Total de Gastos", f"R$ {despesas:,.2f}")
        
    m2.metric("📉 Total de Despesas", f"R$ {despesas:,.2f}")
    
    if "Conta Corrente" in tipo_visao or "Visão Geral" in tipo_visao:
        m3.metric("⚖️ Saldo do Período", f"R$ {saldo:,.2f}", delta=f"{saldo:,.2f}")
    else:
        m3.metric("📊 Qtd. Lançamentos", f"{len(df_final)} itens")

    st.divider()

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

        cor_liq = "#2ecc71" if liquido_cat >= 0 else "#e74c3c"
        
        with st.expander(f"📁 {cat} — Impacto Líquido: R$ {liquido_cat:,.2f} — (Entrou: R$ {t_entradas_cat:,.2f} | Saiu: R$ {t_saidas_cat:,.2f}) — ({len(df_cat_itens)} itens)", expanded=False):
            st.markdown(
                f"<span style='color:white;'><b>{cat}</b> — Impacto Líquido: "
                f"<span style='color:{cor_liq};'>R$ {liquido_cat:,.2f}</span> — "
                f"(Entrou: <span style='color:#2ecc71;'>R$ {t_entradas_cat:,.2f}</span> | "
                f"Saiu: <span style='color:#e74c3c;'>R$ {t_saidas_cat:,.2f}</span>) — ({len(df_cat_itens)} itens)</span>",
                unsafe_allow_html=True
            )
            st.divider()

            estabelecimentos = sorted(df_cat_itens['estabelecimento'].unique())
            
            for estab in estabelecimentos:
                df_estab_itens = df_cat_itens[df_cat_itens['estabelecimento'] == estab]
                t_estab = df_estab_itens['valor'].sum()
                
                with st.expander(f"🔹 **{estab}** — Subtotal: R$ {t_estab:,.2f} ({len(df_estab_itens)}x)"):
                    for _, row in df_estab_itens.iterrows():
                        data_formatada = pd.to_datetime(row['data']).strftime('%d/%m/%Y') if pd.notna(row['data']) else "Data não inf."
                        tipo_texto = "ENTRADA" if row['tipo'] == 'ENTRADA' else "SAÍDA"
                        val_cor = "#2ecc71" if row['tipo'] == 'ENTRADA' else "#e74c3c"
                        st.markdown(
                            f"&nbsp;&nbsp;&nbsp;&nbsp;• **Data:** {data_formatada} | **Tipo:** {tipo_texto} | "
                            f"**Valor:** <span style='color:{val_cor};'>R$ {row['valor']:,.2f}</span> | *Origem:* {row['origem']}",
                            unsafe_allow_html=True
                        )