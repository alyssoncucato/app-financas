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
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            ano_sel = st.selectbox("📅 Filtrar por Ano:", anos_disponiveis)
            
        df_ano = df[df['ano'] == ano_sel]
        
        meses_ano = sorted(df_ano['mes_ano'].dropna().unique(), key=lambda x: datetime.strptime(x, '%m/%Y'))
        opcoes_periodo = ["Todos os Meses do Ano"] + meses_ano
        
        with col_f2:
            periodo_sel = st.selectbox("📌 Filtrar Período Específico:", opcoes_periodo)

        if periodo_sel == "Todos os Meses do Ano":
            df_filtrado = df_ano
            titulo_periodo = f"Ano Completo: {ano_sel}"
        else:
            df_filtrado = df_ano[df_ano['mes_ano'] == periodo_sel]
            titulo_periodo = f"Mês: {periodo_sel}"

        tab_cc, tab_cartao, tab_todos = st.tabs(["🏦 Conta Corrente / Pix", "💳 Cartão de Crédito", "📁 Todos do Período"])

        def render_editor(df_sub, key_sufixo):
            if not df_sub.empty:
                df_sub = df_sub.sort_values(by=['data', 'id'], ascending=[False, False]).copy()
                
                df_editavel = df_sub[['id', 'data', 'descricao', 'valor', 'categoria', 'status_fatura', 'origem', 'tipo']].copy()
                df_editavel['data'] = pd.to_datetime(df_editavel['data'], errors='coerce').dt.date

                def resolve_tipo(row):
                    tp = row.get('tipo')
                    cat = str(row.get('categoria', '')).strip()
                    desc = str(row.get('descricao', '')).strip().upper()
                    
                    if pd.notna(tp) and str(tp).strip():
                        if str(tp).upper() == "ENTRADA":
                            return "🟢 ENTRADA"
                        else:
                            return "🔴 SAÍDA"
                    else:
                        if cat in categorias_entradas or "JACKSON" in desc or "TERESINHA" in desc or "MARIA ISABEL" in desc:
                            return "🟢 ENTRADA"
                        return "🔴 SAÍDA"

                df_editavel['Tipo'] = df_editavel.apply(resolve_tipo, axis=1)
                
                # Adiciona coluna de checkbox para exclusão em massa
                df_editavel['Excluir'] = False

                df_editavel['origem'] = df_editavel['origem'].fillna('EXTRATO_CONTA').apply(lambda x: 'FATURA_CARTAO' if str(x).strip().upper() == 'FATURA_CARTAO' else 'EXTRATO_CONTA')
                df_editavel['status_fatura'] = df_editavel['status_fatura'].fillna('CONTA_CORRENTE').apply(lambda x: str(x).strip().upper() if str(x).strip().upper() in ['ABERTA', 'FECHADA', 'CONTA_CORRENTE'] else 'CONTA_CORRENTE')

                df_editavel = df_editavel[['Excluir', 'id', 'data', 'descricao', 'Tipo', 'valor', 'categoria', 'status_fatura', 'origem']]

                todas_opcoes = list(set(categorias_despesas + categorias_entradas + ["Ignorar"]))
                safe_periodo_key = str(periodo_sel).replace('/', '_').replace(' ', '_')

                with st.form(f"form_editor_{key_sufixo}_{safe_periodo_key}"):
                    editor_result = st.data_editor(
                        df_editavel,
                        column_config={
                            "Excluir": st.column_config.CheckboxColumn("🗑️ Excluir?", default=False, width="small"),
                            "id": None,
                            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", disabled=True),
                            "descricao": st.column_config.TextColumn("Estabelecimento / Descrição", width="large", disabled=True),
                            "Tipo": st.column_config.TextColumn("Tipo", disabled=True, width="small"),
                            "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", disabled=True),
                            "categoria": st.column_config.SelectboxColumn("Categoria", options=todas_opcoes, required=True),
                            "status_fatura": st.column_config.SelectboxColumn("Status", options=["ABERTA", "FECHADA", "CONTA_CORRENTE"], required=True),
                            "origem": st.column_config.SelectboxColumn("Origem", options=["FATURA_CARTAO", "EXTRATO_CONTA"], required=True),
                        },
                        hide_index=True,
                        num_rows="fixed",
                        key=f"editor_lanc_{key_sufixo}_{safe_periodo_key}"
                    )

                    col_b1, col_b2 = st.columns([2, 1])
                    with col_b1:
                        submitted = st.form_submit_button(f"💾 Salvar Alterações ({key_sufixo.upper()})", type="primary")
                    with col_b2:
                        btn_apagar_selecionados = st.form_submit_button("🗑️ Apagar Marcados", type="secondary")

                    if btn_apagar_selecionados:
                        try:
                            ids_para_apagar = []
                            for _, row in editor_result.iterrows():
                                if row.get('Excluir') == True and pd.notna(row.get('id')):
                                    ids_para_apagar.append(int(row['id']))

                            if ids_para_apagar:
                                with engine.connect() as connection:
                                    with connection.begin():
                                        connection.execute(
                                            text("DELETE FROM transacoes WHERE id = ANY(:ids) AND LOWER(usuario) = LOWER(:u)"),
                                            {"ids": ids_para_apagar, "u": user}
                                        )
                                st.success(f"{len(ids_para_apagar)} lançamentos selecionados foram apagados com sucesso!")
                                st.rerun()
                            else:
                                st.warning("Nenhum item foi marcado com a caixinha 'Excluir?' para apagar.")
                        except Exception as e:
                            st.error(f"Erro ao apagar itens selecionados: {e}")

                    if submitted:
                        try:
                            with engine.connect() as connection:
                                with connection.begin():
                                    for _, row in editor_result.iterrows():
                                        tipo_salvar = "ENTRADA" if "ENTRADA" in str(row['Tipo']) else "SAÍDA"
                                        registro_id = int(row['id'])
                                        origem_salvar = str(row['origem']).strip()
                                        status_salvar = str(row['status_fatura']).strip()
                                        
                                        connection.execute(
                                            text("""
                                                UPDATE transacoes 
                                                SET data = :d, descricao = :desc, valor = :v, categoria = :cat, status_fatura = :sf, origem = :orig, tipo = :tp
                                                WHERE id = :id
                                            """),
                                            {
                                                "d": str(row['data']),
                                                "desc": row['descricao'],
                                                "v": float(row['valor']),
                                                "cat": row['categoria'],
                                                "sf": status_salvar,
                                                "orig": origem_salvar,
                                                "tp": tipo_salvar,
                                                "id": registro_id
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