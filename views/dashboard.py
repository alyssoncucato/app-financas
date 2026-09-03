import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text

def render(user, conn_fin, categorias_despesas):
    st.subheader("Resumo Financeiro")

    try:
        df = pd.read_sql_query(
            text("SELECT * FROM transacoes WHERE usuario = :u"), 
            conn_fin, 
            params={"u": user}
        )
    except Exception:
        df = pd.DataFrame()

    if df.empty:
        st.info("Nenhum registro encontrado para este usuário. Faça importações na aba 'Importar com IA'.")
        return

    df['data'] = pd.to_datetime(df['data'], errors='coerce')
    df['mes_ano'] = df['data'].dt.strftime('%m/%Y')
    
    meses_disponiveis = sorted([m for m in df['mes_ano'].dropna().unique()], key=lambda x: datetime.strptime(x, '%m/%Y'), reverse=True)
    
    mes_atual_str = datetime.now().strftime('%m/%Y')

    default_index = 0
    if mes_atual_str in meses_disponiveis:
        default_index = meses_disponiveis.index(mes_atual_str) + 1
    elif meses_disponiveis:
        default_index = 1

    st.markdown("<br>", unsafe_allow_html=True)

    escolha_mes = st.selectbox(
        "📅 Mês:", 
        ["Todos os Meses"] + meses_disponiveis, 
        index=default_index if default_index < len(meses_disponiveis) + 1 else 0,
        key="select_mes_dashboard"
    )

    if escolha_mes != "Todos os Meses":
        df_filtrado = df[df['mes_ano'] == escolha_mes]
    else:
        df_filtrado = df

    aba_visao, aba_cc, aba_cartao = st.tabs(["📊 Visão Consolidada", "🏦 Conta Corrente", "💳 Cartão de Crédito"])

    with aba_visao:
        _render_painel(df_filtrado, categorias_despesas, "Consolidado")

    with aba_cc:
        df_cc = df_filtrado[df_filtrado['origem'] == 'EXTRATO_CONTA']
        _render_painel(df_cc, categorias_despesas, "Conta Corrente")

    with aba_cartao:
        df_cartao = df_filtrado[df_filtrado['origem'] == 'FATURA_CARTAO']
        _render_painel(df_cartao, categorias_despesas, "Cartão de Crédito")

def _render_painel(df_subset, categorias_despesas, tipo_visao):
    if df_subset.empty:
        st.warning(f"Nenhum lançamento encontrado para esta visão no período selecionado.")
        return

    if tipo_visao == "Cartão de Crédito":
        receitas = 0.0
        despesas = df_subset['valor'].sum()
        saldo = -despesas
    elif tipo_visao == "Conta Corrente":
        receitas = df_subset[df_subset['categoria'].isin(["Ganhos Fixos", "Ganhos Variáveis"])]['valor'].sum()
        despesas = df_subset[~df_subset['categoria'].isin(["Ganhos Fixos", "Ganhos Variáveis", "Ignorar"])]['valor'].sum()
        saldo = receitas - despesas
    else: # Consolidado
        receitas = df_subset[df_subset['categoria'].isin(["Ganhos Fixos", "Ganhos Variáveis"])]['valor'].sum()
        despesas = df_subset[~df_subset['categoria'].isin(["Ganhos Fixos", "Ganhos Variáveis", "Ignorar"]) & (df_subset['origem'] != 'FATURA_CARTAO')]['valor'].sum()
        
        total_cartao = df_subset[df_subset['origem'] == 'FATURA_CARTAO']['valor'].sum()
        despesas += total_cartao
        saldo = receitas - despesas

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Receitas", f"R$ {receitas:,.2f}")
    col2.metric("📉 Despesas", f"R$ {despesas:,.2f}")
    col3.metric("⚖️ Saldo", f"R$ {saldo:,.2f}", delta=f"R$ {saldo:,.2f}")

    st.markdown("---")

    cols_por_linha = 4
    cat_com_gastos = [c for c in categorias_despesas if df_subset[df_subset['categoria'] == c]['valor'].sum() > 0]
    outras_cats = [c for c in df_subset['categoria'].unique() if c not in categorias_despesas and c not in ["Ganhos Fixos", "Ganhos Variáveis", "Ignorar"]]
    todas_exibir = cat_com_gastos + outras_cats

    for i in range(0, len(todas_exibir), cols_por_linha):
        linha_cols = st.columns(cols_por_linha)
        for j in range(cols_por_linha):
            if i + j < len(todas_exibir):
                cat = todas_exibir[i + j]
                soma_cat = df_subset[df_subset['categoria'] == cat]['valor'].sum()
                with linha_cols[j]:
                    st.markdown(f"""
                        <div style="padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                            <span style="font-size: 14px; color: #aaa;">{cat}</span><br>
                            <span style="font-size: 20px; font-weight: bold;">R$ {soma_cat:,.2f}</span>
                        </div>
                    """, unsafe_allow_html=True)