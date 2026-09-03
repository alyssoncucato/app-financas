import streamlit as st
import pandas as pd
from datetime import datetime

def render(user, conn_fin, categorias_despesas):
    st.subheader("📊 Resumo Financeiro Mensal")
    
    df = pd.read_sql_query("SELECT * FROM transacoes WHERE usuario = ?", conn_fin, params=(user,))
    
    if not df.empty:
        df['data_dt'] = pd.to_datetime(df['data'], errors='coerce')
        df['mes_ano'] = df['data_dt'].dt.strftime('%m/%Y')
        
        # Pega todos os meses ordenados cronologicamente
        meses = sorted([m for m in df['mes_ano'].dropna().unique()], key=lambda x: datetime.strptime(x, '%m/%Y'))
        
        if meses:
            # Padrão: último mês com lançamentos
            default_idx = len(meses) - 1
            mes_sel = st.selectbox("📅 Selecione o Mês de Referência:", meses, index=default_idx)
            
            # Filtra dados do mês selecionado
            df_mes = df[df['mes_ano'] == mes_sel]
            
            st.markdown(f"### 📌 Visão Geral de {mes_sel}")
            
            # Separando Conta Corrente e Cartão de Crédito
            df_cc = df_mes[df_mes['origem'] == 'EXTRATO_CONTA']
            df_cartao = df_mes[df_mes['origem'] == 'FATURA_CARTAO']
            
            # --- BLOCO 1: CONTA CORRENTE / PIX ---
            with st.container():
                st.markdown("#### 🏦 Conta Corrente / Pix")
                ganhos_cc = df_cc[df_cc['categoria'].isin(['Ganhos Fixos', 'Ganhos Variáveis'])]['valor'].sum()
                desp_cc = df_cc[df_cc['categoria'].isin(categorias_despesas)]['valor'].sum()
                saldo_cc = ganhos_cc - desp_cc
                
                c1, c2, c3 = st.columns(3)
                c1.metric("💰 Entradas (Pix/Salário)", f"R$ {ganhos_cc:,.2f}")
                c2.metric("📉 Despesas na Conta", f"R$ {desp_cc:,.2f}")
                c3.metric("⚖️ Saldo da Conta", f"R$ {saldo_cc:,.2f}", delta=f"{saldo_cc:,.2f}")
            
            st.divider()

            # --- BLOCO 2: CARTÃO DE CRÉDITO ---
            with st.container():
                st.markdown("#### 💳 Cartão de Crédito")
                desp_cartao = df_cartao[df_cartao['categoria'].isin(categorias_despesas)]['valor'].sum()
                
                cc1, cc2 = st.columns(2)
                cc1.metric("💳 Total Fatura do Mês", f"R$ {desp_cartao:,.2f}")
                cc2.metric("📊 Comprometimento Geral", f"R$ {(desp_cc + desp_cartao):,.2f}")

            st.divider()

            # --- BLOCO 3: DETALHAMENTO POR CATEGORIA NO MÊS ---
            st.markdown("#### 🏷️ Despesas por Categoria neste Mês")
            
            if not df_mes.empty:
                for i in range(0, len(categorias_despesas), 4):
                    cols = st.columns(4)
                    for j, cat in enumerate(categorias_despesas[i:i+4]):
                        val_cat = df_mes[df_mes['categoria'] == cat]['valor'].sum()
                        if val_cat > 0:
                            cols[j].metric(cat, f"R$ {val_cat:,.2f}")
                        else:
                            cols[j].markdown(f"**{cat}**\nR$ 0,00")
            else:
                st.info("Nenhum lançamento para este mês.")
        else:
            st.info("Nenhuma data válida encontrada nos registros.")
    else:
        st.info("Nenhum registro encontrado para este usuário.")