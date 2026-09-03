import streamlit as st
import pandas as pd
from datetime import datetime

def render(user, conn_fin, categorias_despesas):
    st.subheader("Resumo Financeiro")
    df = pd.read_sql_query("SELECT * FROM transacoes WHERE usuario = ?", conn_fin, params=(user,))
    
    if not df.empty:
        # Seletor de sub-abas no Dashboard
        tab_geral, tab_cc_dash, tab_cartao_dash = st.tabs(["📊 Visão Consolidada", "🏦 Conta Corrente", "💳 Cartão de Crédito"])

        # Função auxiliar com sufixo único na chave para evitar conflito
        def exibir_metricas(df_subset, key_suffix):
            if not df_subset.empty:
                df_subset['data_dt'] = pd.to_datetime(df_subset['data'], errors='coerce')
                df_subset['mes_ano'] = df_subset['data_dt'].dt.strftime('%m/%Y')
                
                # Ordena os meses cronologicamente de forma crescente (ex: 12/2025, 01/2026, ..., 08/2026)
                meses = sorted([m for m in df_subset['mes_ano'].dropna().unique()], key=lambda x: datetime.strptime(x, '%m/%Y'))
                
                # Define o índice padrão para selecionar o último mês com lançamentos (o final da lista ordenada)
                default_index = len(meses) if meses else 0  # +1 considerando "Todos os Meses" na primeira posição

                # Lista completa de opções com "Todos os Meses" no início
                opcoes_mes = ["Todos os Meses"] + meses

                # Chave garantidamente única baseada no sufixo da aba e no total de linhas
                mes_sel = st.selectbox(
                    "📅 Mês:", 
                    opcoes_mes, 
                    index=default_index, 
                    key=f"sel_mes_{key_suffix}_{df_subset.shape[0]}"
                )
                
                df_v = df_subset if mes_sel == "Todos os Meses" else df_subset[df_subset['mes_ano'] == mes_sel]

                ganhos = df_v[df_v['categoria'].isin(['Ganhos Fixos', 'Ganhos Variáveis'])]['valor'].sum()
                desp = df_v[df_v['categoria'].isin(categorias_despesas)]['valor'].sum()
                saldo = ganhos - desp

                c1, c2, c3 = st.columns(3)
                c1.metric("💰 Receitas", f"R$ {ganhos:,.2f}")
                c2.metric("📉 Despesas", f"R$ {desp:,.2f}")
                c3.metric("⚖️ Saldo", f"R$ {saldo:,.2f}", delta=f"{saldo:,.2f}")

                st.divider()
                for i in range(0, len(categorias_despesas), 4):
                    cols = st.columns(4)
                    for j, cat in enumerate(categorias_despesas[i:i+4]):
                        cols[j].metric(cat, f"R$ {df_v[df_v['categoria'] == cat]['valor'].sum():,.2f}")
            else:
                st.info("Nenhum registro encontrado para este filtro.")

        with tab_geral:
            exibir_metricas(df, "geral")

        with tab_cc_dash:
            df_cc = df[df['origem'] == 'EXTRATO_CONTA']
            exibir_metricas(df_cc, "cc")

        with tab_cartao_dash:
            df_cartao = df[df['origem'] == 'FATURA_CARTAO']
            exibir_metricas(df_cartao, "cartao")
            
    else:
        st.info("Nenhum registro encontrado para este usuário.")