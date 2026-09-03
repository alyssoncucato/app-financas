import streamlit as st
import pandas as pd
from database import engine
from sqlalchemy import text
from datetime import datetime

def render(user, conn_fin, c_fin, categorias_despesas, categorias_entradas):
    st.subheader("📋 Lançamentos e Edição por Mês")

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
        df['mes_ano'] = df['data_dt'].dt.strftime('%m/%Y')
        
        meses = sorted([m for m in df['mes_ano'].dropna().unique()], key=lambda x: datetime.strptime(x, '%m/%Y'), reverse=True)
        
        if meses:
            mes_escolhido = st.selectbox("📅 Filtrar Lançamentos do Mês:", meses, key="sel_mes_lancamentos")
            df_mes = df[df['mes_ano'] == mes_escolhido]

            # Separa estritamente entre Entradas e Saídas com base nas categorias cadastradas
            df_entradas = df_mes[df_mes['categoria'].isin(categorias_entradas)].copy()
            df_saidas = df_mes[~df_mes['categoria'].isin(categorias_entradas)].copy()

            tab_saidas, tab_entradas, tab_todos = st.tabs([
                f"🔴 Saídas / Despesas ({len(df_saidas)})", 
                f"🟢 Entradas / Receitas ({len(df_entradas)})", 
                f"📁 Todos do Mês ({len(df_mes)})"
            ])

            def render_editor(df_sub, key_sufixo, opcoes_disponiveis):
                if not df_sub.empty:
                    df_editavel = df_sub[['id', 'data', 'descricao', 'valor', 'categoria', 'status_fatura', 'origem']].copy()
                    df_editavel['data'] = pd.to_datetime(df_editavel['data'], errors='coerce').dt.date

                    editor_result = st.data_editor(
                        df_editavel,
                        column_config={
                            "id": None,
                            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
                            "descricao": st.column_config.TextColumn("Estabelecimento / Descrição", width="large", required=True),
                            "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                            # Exibe estritamente apenas as opções permitidas para este contexto
                            "categoria": st.column_config.SelectboxColumn("Categoria", options=opcoes_disponiveis, required=True),
                            "status_fatura": st.column_config.SelectboxColumn("Status", options=["ABERTA", "FECHADA", "CONTA_CORRENTE"], required=True),
                            "origem": st.column_config.SelectboxColumn("Origem", options=["FATURA_CARTAO", "EXTRATO_CONTA"], required=True),
                        },
                        hide_index=True,
                        num_rows="fixed",
                        key=f"editor_lanc_{key_sufixo}_{mes_escolhido.replace('/', '_')}"
                    )

                    if st.button(f"💾 Salvar Alterações ({key_sufixo.upper()})", type="primary", key=f"btn_salvar_{key_sufixo}_{mes_escolhido.replace('/', '_')}"):
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
                                        connection.execute(
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
                    st.info(f"Nenhum registro encontrado nesta aba para o mês de {mes_escolhido}.")

            with tab_saidas:
                st.markdown(f"#### 📉 Saídas e Despesas - {mes_escolhido}")
                st.caption("Nesta aba aparecem apenas os lançamentos de gastos. O seletor de categorias exibe apenas as despesas.")
                render_editor(df_saidas, "saidas", list(set(categorias_despesas + ["Ignorar"])))

            with tab_entradas:
                st.markdown(f"#### 📈 Entradas e Receitas - {mes_escolhido}")
                st.caption("Nesta aba aparecem apenas os recebimentos. O seletor exibe apenas as categorias de entrada.")
                render_editor(df_entradas, "entradas", list(set(categorias_entradas)))

            with tab_todos:
                st.markdown(f"#### 📁 Todos os Registros - {mes_escolhido}")
                render_editor(df_mes, "todos", list(set(categorias_despesas + categorias_entradas + ["Ignorar"])))
        else:
            st.info("Nenhum mês válido encontrado.")
    else:
        st.info("Nenhum lançamento cadastrado.")