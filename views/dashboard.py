import streamlit as st
import pandas as pd
from datetime import datetime

def render(user, conn_fin, categorias_despesas):
    st.subheader("📊 Dashboard Financeiro Estruturado")
    
    df = pd.read_sql_query("SELECT * FROM transacoes WHERE usuario = ?", conn_fin, params=(user,))
    
    if df.empty:
        st.info("Nenhum lançamento encontrado. Importe extratos ou faturas para visualizar o dashboard.")
        return

    df['data_dt'] = pd.to_datetime(df['data'], errors='coerce')
    df['ano'] = df['data_dt'].dt.year.fillna(datetime.now().year).astype(int)
    df['mes_ano'] = df['data_dt'].dt.strftime('%m/%Y')

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

    # --- CÁLCULOS ---
    if "Conta Corrente" in tipo_visao or "Visão Geral" in tipo_visao:
        receitas = df_final[df_final['categoria'].isin(['Ganhos Fixos', 'Ganhos Variáveis'])]['valor'].sum()
    else:
        receitas = 0.0

    despesas = df_final[df_final['categoria'].isin(categorias_despesas)]['valor'].sum()
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

    # --- GRÁFICOS ---
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("#### 📊 Despesas por Categoria")
        df_cat = df_final[df_final['categoria'].isin(categorias_despesas)].groupby('categoria')['valor'].sum().reset_index()
        df_cat = df_cat[df_cat['valor'] > 0]
        if not df_cat.empty:
            st.bar_chart(df_cat.set_index('categoria')['valor'], color="#ff4b4b")
        else:
            st.info("Sem despesas para exibir no gráfico.")

    with col_g2:
        st.markdown("#### 📅 Evolução ou Maiores Gastos")
        if mes_sel == "Todos os Meses do Ano":
            df_evolucao = df_filtrado[df_filtrado['categoria'].isin(categorias_despesas)].groupby('mes_ano')['valor'].sum().reset_index()
            if not df_evolucao.empty:
                df_evolucao['mes_ordem'] = pd.to_datetime(df_evolucao['mes_ano'], format='%m/%Y')
                st.line_chart(df_evolucao.sort_values('mes_ordem').set_index('mes_ano')['valor'])
            else:
                st.info("Sem dados para evolução.")
        else:
            df_maiores = df_final.nlargest(5, 'valor')[['data', 'descricao', 'valor', 'categoria']]
            st.dataframe(df_maiores, use_container_width=True, hide_index=True)

    st.divider()

    # --- ÁRVORE DETALHADA POR CATEGORIA -> ESTABELECIMENTO -> LANÇAMENTOS ---
    st.markdown("### 📂 Detalhamento em Árvore por Categoria (Expandível)")
    st.caption("Clique nas categorias abaixo para abrir, ver os estabelecimentos agrupados e checar cada dia e valor.")

    df_desp = df_final[df_final['categoria'].isin(categorias_despesas)].copy()

    if df_desp.empty:
        st.info("Nenhuma despesa detalhada para este filtro.")
        return

    # Padroniza a descrição para agrupar estabelecimentos parecidos
    df_desp['estabelecimento'] = df_desp['descricao'].str.strip().str.upper()

    # Itera sobre cada categoria existente nos dados
    categorias_presentes = sorted(df_desp['categoria'].unique())

    for cat in categorias_presentes:
        df_cat_itens = df_desp[df_desp['categoria'] == cat]
        total_cat = df_cat_itens['valor'].sum()

        # Nível 1: Categoria (Expander principal)
        with st.expander(f"📁 **{cat}** — Total: R$ {total_cat:,.2f} ({len(df_cat_itens)} itens)"):
            
            # Agrupa por estabelecimento dentro da categoria
            estabelecimentos = sorted(df_cat_itens['estabelecimento'].unique())
            
            for estab in estabelecimentos:
                df_estab_itens = df_cat_itens[df_cat_itens['estabelecimento'] == estab]
                total_estab = df_estab_itens['valor'].sum()

                # Nível 2: Estabelecimento (Sub-expander)
                with st.expander(f"🔹 **{estab}** — Subtotal: R$ {total_estab:,.2f} ({len(df_estab_itens)}x)"):
                    
                    # Nível 3: Lançamentos individuais (Data e Valor)
                    for _, row in df_estab_itens.iterrows():
                        data_formatada = pd.to_datetime(row['data']).strftime('%d/%m/%Y') if pd.notna(row['data']) else "Data não inf."
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• **Data:** {data_formatada} | **Valor:** `R$ {row['valor']:,.2f}` | *Origem:* {row['origem']}")