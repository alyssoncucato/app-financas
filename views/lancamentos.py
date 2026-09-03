import streamlit as st
import pandas as pd
from database import engine
from sqlalchemy import text
from datetime import datetime

def render(user, conn_fin, c_fin, categorias_despesas, categorias_entradas):
    st.subheader("📋 Lançamentos e Edição por Mês / Ano")

    with st.expander("⚠️ Opções Avançadas / Limpeza de Dados"):
        st.warning("Atenção: A ação abaixo apagará **todos** os lançamentos salvos permanentemente.")
        if st.button("🗑️ Apagar Todos os Lançamentos", type="secondary"):
            try:
                with engine.connect() as connection:
                    with connection.begin():
                        connection.execute(text("DELETE FROM transacoes WHERE LOWER(usuario) = LOWER(:u)"), {"u": user})
                st.success("Todos os lançamentos foram apagados com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao apagar: {e}")

    try:
        query = text("SELECT * FROM transacoes WHERE LOWER(usuario) = LOWER(:u)")
        df = pd.read_sql_query(query, conn_fin, params={"u": user})
    except Exception as e:
        st.error(f"Erro ao carregar lançamentos: {e}")
        return

    if not df.empty:
        df['data_dt'] = pd.to_datetime(df['data'], errors='coerce')
        df['ano'] = df['data_dt'].dt.year.fillna(datetime.now().year).astype(int)
        df['mes_ano'] = df['data_dt'].dt.strftime('%m/%Y')
        
        anos_disponiveis = sorted(list(df['ano'].unique()), reverse=True)
        
        # Filtros de Ano e Período lado a lado
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            ano_sel = st.selectbox("📅 Filtrar por Ano:", anos_disponiveis)
            
        df_ano = df[df['ano'] == ano_sel]
        
        meses_ano = sorted(df_ano['mes_ano'].dropna().unique(), key=lambda x: datetime.strptime(x, '%m/%Y'))
        opcoes_periodo = ["Todos os Meses do Ano"] + meses_ano
        
        with col_f2:
            periodo_sel = st.selectbox("📌 Filtrar Período Específico:", opcoes_periodo)

        # Define o dataframe filtrado com base na escolha
        if periodo_sel == "Todos os Meses do Ano":
            df_filtrado = df_ano
            titulo_periodo = f"Ano Completo: {ano_sel}"
        else:
            df_filtrado = df_ano[df_ano['mes_ano'] == periodo_sel]
            titulo_periodo = f"Mês: {periodo_sel}"

        tab_cc, tab_cartao, tab_todos = st.tabs(["🏦 Conta Corrente / Pix", "💳 Cartão de Crédito", "📁 Todos do Período"])

        def render_editor(df_sub, key_sufixo):
            if not df_sub.empty:
                df_editavel = df_sub[['id', 'data', 'descricao', 'valor', 'categoria', 'status_fatura', 'origem']].copy()
                df_editavel['data'] = pd.to_datetime(df_editavel['data'], errors='coerce').dt.date

                def identifica_tipo(cat):
                    if cat in categorias_entradas:
                        return "🟢 ENTRADA"
                    elif cat == "Ignorar":
                        return "⚪ IGNORAR"
                    else:
                        return "🔴 SAÍDA"

                df_editavel['Tipo'] = df_editavel['categoria'].apply(identifica_tipo)
                df_editavel = df_editavel[['id', 'data', 'descricao', 'Tipo', 'valor', 'categoria', 'status_fatura', 'origem']]

                todas_opcoes = list(set(categorias_despesas + categorias_entradas + ["Ignorar"]))

                with st.form(f"form_editor_{key_sufixo}_{str(periodo_sel).replace('/', '_')}"):
                    editor_result = st.data_editor(
                        df_editavel,
                        column_config={
                            "id": None,
                            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
                            "descricao": st.column_config.TextColumn("Estabelecimento / Descrição", width="large", required=True),
                            "Tipo": st.column_config.TextColumn("Tipo", disabled=True, width="small"),
                            "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                            "categoria": st.column_config.SelectboxColumn("Categoria", options=todas_opcoes, required=True),
                            "status_fatura": st.column_config.SelectboxColumn("Status", options=["ABERTA", "FECHADA", "CONTA_CORRENTE"], required=True),
                            "origem": st.column_config.SelectboxColumn("Origem", options=["FATURA_CARTAO", "EXTRATO_CONTA"], required=True),
                        },
                        hide_index=True,
                        num_rows="fixed",
                        key=f"editor_lanc_{key_sufixo}_{str(periodo_sel).replace('/', '_')}"
                    )

                    submitted = st.form_submit_button(f"💾 Salvar Alterações ({key_sufixo.upper()})", type="primary")

                    if submitted:
                        try:
                            with engine.connect() as connection:
                                with connection.begin():
                                    for _, row in editor_result.iterrows():
                                        connection.execute(
                                            text("""
                                                UPDATE transacoes 
                                                SET data = :d, descricao = :desc, valor = :v, categoria = :cat, status_fatura = :sf, origem = :orig 
                                                WHERE id = :id
                                            """),
                                            {
                                                "d": str(row['data']),
                                                "desc": row['descricao'],
                                                "v": float(row['valor']),
                                                "cat": row['categoria'],
                                                "sf": row['status_fatura'],
                                                "orig": row['origem'],
                                                "id": int(row['id'])
                                            }
                                        )
                            
                            for _, row in editor_result.iterrows():
                                if row['categoria'] not in categorias_entradas and row['categoria'] not in ["Ignorar", "Não sei"]:
                                    termo_limpo = str(row['descricao']).strip().upper()
                                    if len(termo_limpo) >= 3:
                                        with engine.connect() as conn_reg:
                                            conn_reg.execute(
                                                text("""
                                                    INSERT INTO regras_categorias (usuario, termo_chave, categoria_destino) 
                                                    VALUES (:u, :t, :c)
                                                    ON CONFLICT DO NOTHING
                                                """),
                                                {"u": user, "t": termo_limpo, "c": row['categoria']}
                                            )

                            st.success("Alterações salvas com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar alterações: {e}")
            else:
                st.info(f"Nenhum registro encontrado para este filtro ({titulo_periodo}).")

        with tab_cc:
            st.markdown(f"#### Movimentações de Conta Corrente — *{titulo_periodo}*")
            render_editor(df_filtrado[df_filtrado['origem'] == 'EXTRATO_CONTA'], "cc")

        with tab_cartao:
            st.markdown(f"#### Faturas de Cartão de Crédito — *{titulo_periodo}*")
            render_editor(df_filtrado[df_filtrado['origem'] == 'FATURA_CARTAO'], "cartao")

        with tab_todos:
            st.markdown(f"#### Todos os Registros — *{titulo_periodo}*")
            render_editor(df_filtrado, "todos")
    else:
        st.info("Nenhum lançamento cadastrado.")