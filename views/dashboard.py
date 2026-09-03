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

    # --- MENU DE NAVEGAÇÃO PRINCIPAL (O que você quer ver?) ---
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

    # Filtra dados pelo ano selecionado primeiro
    df_ano = df[df['ano'] == ano_sel]

    # Refina a origem com base na escolha do usuário
    if "Nubank" in tipo_visao:
        # Se você diferencia os cartões por descrição ou origem, ajustamos aqui. 
        # Como o app usa 'FATURA_CARTAO', vamos filtrar o que for do Nubank ou geral de cartão se preferir
        df_filtrado = df_ano[(df_ano['origem'] == 'FATURA_CARTAO')]
    elif "Mercado Pago" in tipo_visao:
        df_filtrado = df_ano[(df_ano['origem'] == 'FATURA_CARTAO')] # Ajustável caso use tags na descrição
    elif "Conta Corrente" in tipo_visao:
        df_filtrado = df_ano[df_ano['origem'] == 'EXTRATO_CONTA']
    else:
        df_filtrado = df_ano # Consolidado

    with col_n3:
        # Pega os meses disponíveis dentro do ano selecionado
        meses_ano = sorted(df_filtrado['mes_ano'].dropna().unique(), key=lambda x: datetime.strptime(x, '%m/%Y'))
        opcoes_mes = ["Todos os Meses do Ano"] + meses_ano
        mes_sel = st.selectbox("3. Mês:", opcoes_mes)

    # Filtra por mês se selecionado específico
    if mes_sel != "Todos os Meses do Ano":
        df_final = df_filtrado[df_filtrado['mes_ano'] == mes_sel]
        titulo_periodo = f"Mês: {mes_sel} ({ano_sel})"
    else:
        df_final = df_filtrado
        titulo_periodo = f"Ano Consolidado: {ano_sel}"

    st.divider()
    st.markdown(f"### 📈 Métricas e Gráficos para: **{tipo_visao}** — *{titulo_periodo}*")

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

    # --- CARTÕES DE MÉTRICAS RÁPIDAS ---
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

    # --- GRÁFICOS VISUAIS (FÁCEIS DE VER) ---
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("#### 📊 Despesas por Categoria (Gráfico de Barras)")
        # Agrupa por categoria
        df_cat = df_final[df_final['categoria'].isin(categorias_despesas)].groupby('categoria')['valor'].sum().reset_index()
        df_cat = df_cat[df_cat['valor'] > 0]
        
        if not df_cat.empty:
            df_cat = df_cat.set_index('categoria')
            st.bar_chart(df_cat['valor'], color="#ff4b4b")
        else:
            st.info("Sem despesas registradas para gerar o gráfico de categorias.")

    with col_g2:
        st.markdown("#### 📅 Evolução Mensal de Gastos (Gráfico de Linha/Barra)")
        if mes_sel == "Todos os Meses do Ano":
            # Agrupa por mês para mostrar a evolução no ano
            df_evolucao = df_filtrado[df_filtrado['categoria'].isin(categorias_despesas)].groupby('mes_ano')['valor'].sum().reset_index()
            if not df_evolucao.empty:
                df_evolucao['mes_ordem'] = pd.to_datetime(df_evolucao['mes_ano'], format='%m/%Y')
                df_evolucao = df_evolucao.sort_values('mes_ordem').set_index('mes_ano')
                st.line_chart(df_evolucao['valor'])
            else:
                st.info("Sem dados suficientes para evolução mensal.")
        else:
            # Se for um mês específico, mostra os maiores gastos do mês em barras
            st.markdown(f"**Maiores lançamentos de {mes_sel}:**")
            df_maiores = df_final.nlargest(5, 'valor')[['data', 'descricao', 'valor', 'categoria']]
            st.dataframe(df_maiores, use_container_width=True, hide_index=True)