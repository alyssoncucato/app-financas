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
            df_filtrado = df[df['mes_ano'] == mes_escolhido]

            tab_cc, tab_cartao, tab_todos = st.tabs(["🏦 Conta Corrente / Pix", "💳 Cartão de Crédito", "📁 Todos do Mês"])

            def render_editor(df_sub, key_sufixo):
                if not df_sub.empty:
                    df_editavel = df_sub[['id', 'data', 'descricao', 'valor', 'categoria', 'status_fatura', 'origem']].copy()
                    df_editavel['data'] = pd.to_datetime(df_editavel['data'], errors='coerce').dt.date

                    # Identifica visualmente o tipo
                    def identifica_tipo(cat):
                        if cat in categorias_entradas:
                            return "🟢 ENTRADA"
                        elif cat == "Ignorar":
                            return "⚪ IGNORAR"
                        else:
                            return "🔴 SAÍDA"

                    df_editavel['Tipo'] = df_editavel['categoria'].apply(identifica_tipo)

                    # Dividimos em duas colunas separadas para a tabela: uma para selecionar despesas e outra para entradas.
                    # Assim, quem é saída usa a coluna de despesas, e quem é entrada usa a coluna de entradas!
                    df_editavel['Categoria Despesa'] = df_editavel.apply(lambda r: r['categoria'] if r['categoria'] in categorias_despesas or r['categoria'] == "Ignorar" else categorias_despesas[0], axis=1)
                    df_editavel['Categoria Entrada'] = df_editavel.apply(lambda r: r['categoria'] if r['categoria'] in categorias_entradas else categorias_entradas[0], axis=1)

                    df_editavel = df_editavel[['id', 'data', 'descricao', 'Tipo', 'valor', 'Categoria Despesa', 'Categoria Entrada', 'status_fatura', 'origem']]

                    editor_result = st.data_editor(
                        df_editavel,
                        column_config={
                            "id": None,
                            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
                            "descricao": st.column_config.TextColumn("Estabelecimento / Descrição", width="medium", required=True),
                            "Tipo": st.column_config.TextColumn("Tipo", disabled=True, width="small"),
                            "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", required=True),
                            "Categoria Despesa": st.column_config.SelectboxColumn("Cat. Despesa (Se Saída)", options=list(set(categorias_despesas + ["Ignorar"])), required=True),
                            "Categoria Entrada": st.column_config.SelectboxColumn("Cat. Entrada (Se Entrada)", options=list(set(categorias_entradas)), required=True),
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
                                        # Define qual categoria salvar com base no tipo da linha original
                                        tipo_atual = row['Tipo']
                                        if "ENTRADA" in tipo_atual:
                                            cat_final = row['Categoria Entrada']
                                        else:
                                            cat_final = row['Categoria Despesa']

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
                                                "cat": cat_final,
                                                "sf": row['status_fatura'],
                                                "orig": row['origem'],
                                                "id": int(row['id'])
                                            }
                                        )
                            
                            for _, row in editor_result.iterrows():
                                tipo_atual = row['Tipo']
                                cat_final = row['Categoria Entrada'] if "ENTRADA" in tipo_atual else row['Categoria Despesa']
                                
                                if cat_final not in categorias_entradas and cat_final not in ["Ignorar", "Não sei"]:
                                    termo_limpo = str(row['descricao']).strip().upper()
                                    if len(termo_limpo) >= 3:
                                        connection.execute(
                                            text("""
                                                INSERT INTO regras_categorias (usuario, termo_chave, categoria_destino) 
                                                VALUES (:u, :t, :c)
                                                ON CONFLICT DO NOTHING
                                            """),
                                            {"u": user, "t": termo_limpo, "c": cat_final}
                                        )

                            st.success("Alterações salvas com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar alterações: {e}")
                else:
                    st.info(f"Nenhum registro encontrado para este filtro no mês de {mes_escolhido}.")

            with tab_cc:
                st.markdown(f"#### Movimentações de Conta Corrente - {mes_escolhido}")
                render_editor(df_filtrado[df_filtrado['origem'] == 'EXTRATO_CONTA'], "cc")

            with tab_cartao:
                st.markdown(f"#### Faturas de Cartão de Crédito - {mes_escolhido}")
                render_editor(df_filtrado[df_filtrado['origem'] == 'FATURA_CARTAO'], "cartao")

            with tab_todos:
                st.markdown(f"#### Todos os Registros - {mes_escolhido}")
                render_editor(df_filtrado, "todos")
        else:
            st.info("Nenhum mês válido encontrado.")
    else:
        st.info("Nenhum lançamento cadastrado.")