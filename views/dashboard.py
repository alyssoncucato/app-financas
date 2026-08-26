import streamlit as st
import pandas as pd

def render(user, conn_fin, categorias_despesas):
    st.subheader("Resumo Financeiro")
    df = pd.read_sql_query("SELECT * FROM transacoes WHERE usuario = ?", conn_fin, params=(user,))
    if not df.empty:
        df['data_dt'] = pd.to_datetime(df['data'], errors='coerce')
        df['mes_ano'] = df['data_dt'].dt.strftime('%m/%Y')
        meses = sorted([m for m in df['mes_ano'].dropna().unique()], reverse=True)
        mes_sel = st.selectbox("📅 Mês:", ["Todos os Meses"] + meses)
        df_v = df if mes_sel == "Todos os Meses" else df[df['mes_ano'] == mes_sel]

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
        st.info("Nenhum registro encontrado para este usuário.")